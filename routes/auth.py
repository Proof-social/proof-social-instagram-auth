"""Endpoints de autenticação OAuth Instagram (Instagram Login API).

Migrado de Facebook Login for Business → Instagram Login API.

Vantagens:
- User não precisa de Facebook Page nem Business Manager
- Autoriza direto no instagram.com
- Scopes Instagram-only (mais simples no App Review)

Requer:
- Instagram account Business ou Creator (conta pessoal nunca funciona)
- Produto "Instagram" habilitado no Meta App Dashboard (client_id próprio)

Doc: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from google.cloud import firestore

from core.instagram_config import get_instagram_config
from core.security import save_access_token, verify_firebase_token
from core.state import generate_state, validate_state, InvalidStateError
from schemas.instagram import (
    InstagramAccount,
    InstagramCallbackRequest,
    InstagramCallbackResponse,
    InstagramLoginRequest,
    InstagramLoginResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Lock por código pra evitar processar o mesmo code 2x (React Strict Mode).
processing_codes: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

# Scopes do Instagram Login API. Cobertura para o que o Proof precisa:
# - basic: id, username, account_type
# - manage_insights: profile + media insights
# - manage_comments: ler/responder comments
# - manage_messages: DMs (futuro)
# - content_publish: publish (futuro, exige App Review)
INSTAGRAM_SCOPES = [
    "instagram_business_basic",
    "instagram_business_manage_insights",
    "instagram_business_manage_comments",
    "instagram_business_manage_messages",
    "instagram_business_content_publish",
]

INSTAGRAM_AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH_LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
INSTAGRAM_GRAPH_ME_URL = "https://graph.instagram.com/v20.0/me"


async def get_user_uid(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorização não fornecido")
    try:
        return await verify_firebase_token(authorization)
    except ValueError as e:
        # Sem isso, ValueError vira 500. Convertendo para 401 padronizado.
        raise HTTPException(status_code=401, detail=f"Token inválido: {e}")


@router.post("/instagram/login", response_model=InstagramLoginResponse)
async def instagram_login(
    request: InstagramLoginRequest,
    user_uid: str = Depends(get_user_uid),
):
    """Gera URL de autorização Instagram Login API.

    Body: {"redirect_uri": "..."}
    Retorna: {"auth_url": "https://www.instagram.com/oauth/authorize?..."}
    """
    try:
        config = get_instagram_config()
        try:
            state = generate_state(user_uid)
        except Exception as e:
            logger.error("Falha ao gerar state OAuth: %s", e)
            raise HTTPException(
                status_code=503,
                detail="Server misconfigured: OAUTH_STATE_SIGNING_KEY ausente",
            )

        params = {
            "enable_fb_login": "0",
            "force_authentication": "1",
            "client_id": config["app_id"],
            "redirect_uri": request.redirect_uri,
            "response_type": "code",
            "scope": ",".join(INSTAGRAM_SCOPES),
            "state": state,
        }
        auth_url = f"{INSTAGRAM_AUTHORIZE_URL}?{urlencode(params)}"

        logger.info(
            "Instagram OAuth URL gerada user_uid=%s redirect_uri=%s",
            user_uid, request.redirect_uri,
        )
        return InstagramLoginResponse(auth_url=auth_url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao gerar URL Instagram OAuth: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@router.post("/instagram/process-callback", response_model=InstagramCallbackResponse)
async def instagram_process_callback(
    request: InstagramCallbackRequest,
    user_uid: str = Depends(get_user_uid),
):
    """Processa callback OAuth Instagram Login API e configura integração.

    Body: {"code": "...", "state": "...", "redirect_uri": "..."}
    """
    # Limpa fragmento `#_=_` que Meta às vezes adiciona.
    cleaned_state = (request.state or "").split("#")[0].rstrip("_=").strip()

    try:
        validate_state(state=cleaned_state, user_uid=user_uid)
    except InvalidStateError as e:
        logger.warning("OAuth state inválido user_uid=%s reason=%s", user_uid, e)
        raise HTTPException(status_code=400, detail=f"State inválido ou expirado: {e}")

    db = firestore.Client()
    integration_ref = db.collection("integrations").document(user_uid)
    existing = integration_ref.get()

    config = get_instagram_config()
    app_id = config["app_id"]
    app_secret = config["app_secret"]

    code_key = f"{user_uid}:{request.code}"
    async with processing_codes[code_key]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            short_token, ig_user_id = await _exchange_code_for_short_token(
                client, app_id, app_secret, request.code, request.redirect_uri,
                existing_doc=existing,
            )

            long_token, expires_in = await _exchange_short_for_long_token(
                client, app_secret, short_token,
            )

            profile = await _fetch_instagram_profile(client, long_token)

        new_account_id = str(profile.get("id") or ig_user_id)
        new_account_username = profile.get("username") or ""

        # Idempotência: se já existe doc COM ESSA MESMA conta criada há < 5min,
        # retorna sem fazer nada. Proteção contra React Strict Mode em dev OU
        # double-click no botão. Não atrapalha multi-conta porque compara id.
        if existing.exists:
            data = existing.to_dict() or {}
            created_at = data.get("created_at")
            already_has_this = any(
                str(a.get("id")) == new_account_id
                for a in (data.get("instagram_accounts") or [])
            )
            if (
                already_has_this
                and isinstance(created_at, _dt_module().datetime)
                and (_dt_module().datetime.now(_dt_module().timezone.utc) - created_at).total_seconds() < 300
            ):
                logger.info(
                    "Reconexão dedupe user_uid=%s ig_id=%s — retornando estado atual",
                    user_uid, new_account_id,
                )
                return _build_response_from_doc(data, message="Integração já configurada.")

        api_key = str(uuid.uuid4())
        await save_access_token(api_key, long_token)

        # Monta o objeto da nova conta a partir do profile do IG.
        new_account_doc = {
            "id": new_account_id,
            "username": new_account_username,
            "name": profile.get("name") or new_account_username or "",
            "account_type": profile.get("account_type", "BUSINESS"),
            "followers_count": profile.get("followers_count", 0),
            "media_count": profile.get("media_count", 0),
            "profile_picture_url": profile.get("profile_picture_url") or "",
            "active": True,
            # Token por conta: cada conta IG tem seu próprio long-lived token.
            # api_key aponta pra esse token específico em secret/storage.
            "api_key": api_key,
            "token_expires_in_seconds": expires_in,
        }

        # MERGE: se já existe doc, preserva as outras contas. Adiciona/atualiza
        # a conta nova pelo id. Caso seja primeira conexão, cria do zero.
        if existing.exists:
            data = existing.to_dict() or {}
            existing_accounts = data.get("instagram_accounts") or []
            # Substitui se já existe (refresh de token), senão append.
            merged = [a for a in existing_accounts if str(a.get("id")) != new_account_id]
            merged.append(new_account_doc)

            integration_ref.update({
                "instagram_accounts": merged,
                # api_key root do doc fica apontando pra última conta conectada
                # (compat com código legado que lê integration.api_key direto).
                # Code novo deve preferir account.api_key.
                "api_key": api_key,
                "status": "active",
                "updated_at": firestore.SERVER_TIMESTAMP,
                "token_expires_in_seconds": expires_in,
            })
            logger.info(
                "Instagram account adicionada (merge) user_uid=%s ig_id=%s @%s total_accounts=%d",
                user_uid, new_account_id, new_account_username, len(merged),
            )
        else:
            integration_ref.set({
                "user_uid": user_uid,
                "platform": "instagram",
                "auth_provider": "instagram_login_api",
                "api_key": api_key,
                "status": "active",
                "created_at": firestore.SERVER_TIMESTAMP,
                "instagram_accounts": [new_account_doc],
                "token_expires_in_seconds": expires_in,
            })
            logger.info(
                "Instagram integration criada user_uid=%s ig_id=%s @%s",
                user_uid, new_account_id, new_account_username,
            )

        account = InstagramAccount(
            id=new_account_id,
            username=new_account_username,
            name=new_account_username,
        )
        # Refetch pra incluir TODAS as contas no response (importante pro
        # frontend atualizar a lista no appState).
        final = integration_ref.get().to_dict() or {}
        all_accounts = [
            InstagramAccount(
                id=str(a.get("id")),
                username=a.get("username"),
                name=a.get("name") or a.get("username"),
            )
            for a in (final.get("instagram_accounts") or [])
        ]
        return InstagramCallbackResponse(
            api_key=api_key,
            instagram_accounts=all_accounts or [account],
            message="Integração Instagram configurada com sucesso",
            status="success",
        )


# --------------------------------------------------------------------------- #
# Helpers HTTP                                                                #
# --------------------------------------------------------------------------- #


async def _exchange_code_for_short_token(
    client: httpx.AsyncClient,
    app_id: str,
    app_secret: str,
    code: str,
    redirect_uri: str,
    *,
    existing_doc,
) -> tuple[str, str]:
    """POST x-www-form-urlencoded para api.instagram.com/oauth/access_token.

    Retorna (short_token, ig_user_id).
    """
    resp = await client.post(
        INSTAGRAM_TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        body = resp.json() if resp.content else {}
        error_msg = body.get("error_message") or body.get("error", {}).get("message", "")
        # Code reusage: IG retorna "Authorization code has been used"
        if "has been used" in str(error_msg).lower() and existing_doc and existing_doc.exists:
            data = existing_doc.to_dict() or {}
            logger.warning("Código já usado; devolvendo integração existente")
            response_data = _build_response_from_doc(data, message="Integração já configurada.")
            # Lança HTTPException pra interromper o fluxo principal
            raise HTTPException(status_code=200, detail=response_data.model_dump())
        logger.error("IG /oauth/access_token retornou %d: %s", resp.status_code, body)
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao trocar code por token: {body}",
        )

    payload = resp.json()
    short_token = payload.get("access_token")
    ig_user_id = str(payload.get("user_id") or "")
    if not short_token:
        raise HTTPException(status_code=400, detail="Resposta sem access_token")
    return short_token, ig_user_id


async def _exchange_short_for_long_token(
    client: httpx.AsyncClient,
    app_secret: str,
    short_token: str,
) -> tuple[str, int]:
    """GET graph.instagram.com/access_token?grant_type=ig_exchange_token.

    Retorna (long_token, expires_in_seconds).
    """
    resp = await client.get(
        INSTAGRAM_GRAPH_LONG_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
    )
    if resp.status_code != 200:
        body = resp.json() if resp.content else {}
        logger.error("ig_exchange_token retornou %d: %s", resp.status_code, body)
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao converter pra long-lived token: {body}",
        )
    payload = resp.json()
    long_token = payload.get("access_token")
    expires_in = int(payload.get("expires_in") or 0)
    if not long_token:
        raise HTTPException(status_code=400, detail="Resposta sem long-lived token")
    return long_token, expires_in


async def _fetch_instagram_profile(
    client: httpx.AsyncClient,
    long_token: str,
) -> dict:
    """GET graph.instagram.com/v20.0/me — busca id, username, account_type, etc."""
    resp = await client.get(
        INSTAGRAM_GRAPH_ME_URL,
        params={
            "fields": "id,username,account_type,followers_count,media_count,profile_picture_url,name",
            "access_token": long_token,
        },
    )
    if resp.status_code != 200:
        body = resp.json() if resp.content else {}
        logger.error("/me retornou %d: %s", resp.status_code, body)
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao buscar perfil Instagram: {body}",
        )
    return resp.json()


def _build_response_from_doc(data: dict, *, message: str) -> InstagramCallbackResponse:
    accounts_data = data.get("instagram_accounts", [])
    accounts = [
        InstagramAccount(
            id=acc.get("id", ""),
            username=acc.get("username"),
            name=acc.get("name") or acc.get("username"),
        )
        for acc in accounts_data
    ]
    return InstagramCallbackResponse(
        api_key=data.get("api_key", ""),
        instagram_accounts=accounts,
        message=message,
        status="success",
    )


def _dt_module():
    """Import lazy de datetime — evita warning de Pyright sobre uso top-level."""
    import datetime as _dt
    return _dt
