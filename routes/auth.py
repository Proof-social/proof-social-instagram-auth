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
import os
import secrets
import time
import uuid
from collections import defaultdict
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from google.cloud import firestore

from core import tenancy
from core.instagram_config import get_instagram_config
from core.security import save_access_token, verify_firebase_token
from core.state import generate_state, validate_state, InvalidStateError, STATE_LINK_TTL_SECONDS
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

# Scopes do Instagram Login API. SÓ o que o Proof usa de fato — pedir permissão não-usada
# é motivo comum de reprovação no App Review (e manage_messages é a mais escrutinada da Meta).
# - basic: id, username, account_type, /media, /me
# - manage_insights: profile + media insights (/insights)
# - content_publish: agendar/publicar post e story (fila instagram-publish)
# manage_comments e manage_messages REMOVIDOS (não usados; ler comment é só a métrica de
# contagem, via basic/insights). Se um dia entrar automação de DM/comentário, re-adicionar
# aqui + App Review próprio pra essas permissões.
INSTAGRAM_SCOPES = [
    "instagram_business_basic",
    "instagram_business_manage_insights",
    "instagram_business_content_publish",
]

INSTAGRAM_AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_GRAPH_LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
INSTAGRAM_GRAPH_ME_URL = "https://graph.instagram.com/v20.0/me"

# --- Encurtador de link de conexão (modo agência) ---
# O auth_url do OAuth é gigante (state + scopes) e não dá pra mandar pro cliente. Guardamos ele em
# pp_connect_links/{code} e servimos /auth/c/{code} → 302 pro auth_url. TTL = o do state link (7d).
CONNECT_LINKS_COLLECTION = "pp_connect_links"
# Convite nomeado por cliente (modalidade de agência). Mesmo `code` do short-link liga os dois docs:
# pp_connect_links/{code} = auth_url (interno); pp_agency_invites/{code} = metadados + status (produto).
AGENCY_INVITES_COLLECTION = "pp_agency_invites"
AUTH_PUBLIC_URL = os.getenv(
    "AUTH_PUBLIC_URL",
    "https://proof-social-instagram-auth-200656387414.us-central1.run.app",
).rstrip("/")

# --- Modalidade de agência: dispara o pipeline server-side no proof-platform após a conexão ---
# O platform orquestra catálogo → dossiê → auto-confirm → scoring. Token compartilhado
# (== INTERNAL_SERVICE_TOKEN do platform). Sem token → o trigger é abortado (logado), não falha o OAuth.
PLATFORM_INTERNAL_URL = os.getenv(
    "PLATFORM_INTERNAL_URL",
    "https://proof-platform-200656387414.us-central1.run.app",
).rstrip("/")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "")


async def _trigger_agency_pipeline(agency_uid: str, ig_account_id: str, code: str) -> None:
    """Dispara o pipeline server-side no proof-platform (modalidade de agência). Best-effort:
    NUNCA falha o callback OAuth por causa disto (a conexão já foi persistida). Loga em erro.
    O platform responde rápido (só marca 'processing' + enfileira), então awaitar é barato."""
    if not INTERNAL_SERVICE_TOKEN:
        logger.error("trigger do pipeline de agência abortado: INTERNAL_SERVICE_TOKEN vazio")
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PLATFORM_INTERNAL_URL}/internal/agency/client-connected",
                json={"agency_uid": agency_uid, "ig_account_id": ig_account_id, "invite_code": code},
                headers={"X-Internal-Token": INTERNAL_SERVICE_TOKEN},
            )
            if resp.status_code != 200:
                logger.error("platform /internal/agency/client-connected → %s: %s",
                             resp.status_code, resp.text[:300])
    except Exception:
        logger.exception("falha ao disparar pipeline de agência (agency=%s ig=%s)",
                         agency_uid, ig_account_id)


def _create_short_connect_link(code: str, auth_url: str) -> str:
    """Guarda o auth_url sob {code} e devolve o link curto (/auth/c/{code}) pra agência mandar
    pro cliente. O {code} é gerado antes do state (pra ser assinado dentro dele) e reusado aqui."""
    firestore.Client().collection(CONNECT_LINKS_COLLECTION).document(code).set({
        "auth_url": auth_url,
        "created_at": firestore.SERVER_TIMESTAMP,
        "expires_at": int(time.time()) + STATE_LINK_TTL_SECONDS,
    })
    return f"{AUTH_PUBLIC_URL}/auth/c/{code}"


def _create_agency_invite(
    code: str, agency_uid: str, client_name: str, client_email: str, connect_link: str,
) -> None:
    """Cria o doc de convite (produto). Status nasce 'pending'; o callback marca 'connected',
    e o pipeline server-side (Fase 2) marca 'ready'. A home da agência lê isto em realtime.
    Guarda `connect_link` (não é segredo) pra agência copiar de novo um convite pendente."""
    firestore.Client().collection(AGENCY_INVITES_COLLECTION).document(code).set({
        "code": code,
        "agency_uid": agency_uid,
        "client_name": client_name,
        "client_email": client_email,
        "connect_link": connect_link,
        "status": "pending",
        "ig_account_id": None,
        "ig_username": None,
        "created_at": firestore.SERVER_TIMESTAMP,
        "connected_at": None,
        "ready_at": None,
        "error_motivo": None,
    })


def _mark_invite_connected(code: str, ig_account_id: str, ig_username: Optional[str]) -> None:
    """Marca o convite como conectado quando o cliente conclui o OAuth. Idempotente e defensivo:
    nunca deixa o callback falhar por causa disto (a conexão em si já foi persistida)."""
    try:
        firestore.Client().collection(AGENCY_INVITES_COLLECTION).document(code).set({
            "status": "connected",
            "ig_account_id": ig_account_id,
            "ig_username": ig_username,
            "connected_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    except Exception as e:
        logger.error("Falha ao marcar convite %s como conectado: %s", code, e, exc_info=True)


async def get_user_uid(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorização não fornecido")
    try:
        return await verify_firebase_token(authorization)
    except ValueError as e:
        # Sem isso, ValueError vira 500. Convertendo para 401 padronizado.
        raise HTTPException(status_code=401, detail=f"Token inválido: {e}")


async def get_user_uid_optional(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Como get_user_uid, mas retorna None se NÃO houver token (em vez de 401). Usado no
    callback: o fluxo logado manda o bearer; o fluxo link (cliente) não manda — aí o uid
    vem do state assinado. Se vier um token, ele TEM que ser válido (senão 401)."""
    if not authorization:
        return None
    try:
        return await verify_firebase_token(authorization)
    except ValueError as e:
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

        # Convite nomeado (modalidade de agência): no modo link COM nome + email, cria um convite
        # rastreável. Sem nome/email, o modo link continua sendo o link genérico antigo (retrocompat
        # com o botão "Gerar link" do onboarding). Se vier só um dos dois → 400 (evita convite meia-boca).
        # O code é gerado ANTES do state pra ser assinado dentro dele — assim o callback sabe qual
        # convite marcar como conectado (o cliente não pode adulterá-lo).
        invite_code: Optional[str] = None
        client_name = (request.client_name or "").strip()
        client_email = (request.client_email or "").strip()
        if request.link_mode and (client_name or client_email):
            if not client_name or not client_email:
                raise HTTPException(
                    status_code=400,
                    detail="client_name e client_email são obrigatórios juntos no convite nomeado",
                )
            if "@" not in client_email or "." not in client_email.split("@")[-1]:
                raise HTTPException(status_code=400, detail="client_email inválido")
            invite_code = secrets.token_urlsafe(6)  # ~8 chars, URL-safe — id do convite E do short-link

        try:
            state = generate_state(
                user_uid,
                mode="link" if request.link_mode else "login",
                code=invite_code or "",
            )
        except HTTPException:
            raise
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
        # Sempre usa o OAuth URL direto, sem prefixar logout.
        # Por quê: o logout?next=<oauth_url> quebrava a chain quando havia
        # verificação por email no meio. IG fazia logout, redirecionava pro
        # OAuth, mas no meio do flow de login (verificação por email) o
        # state do OAuth se perdia → user terminava na home do IG sem
        # voltar pro Proof. O parâmetro `force_authentication=1` já força
        # reentrada de credenciais; pra trocar de conta, user usa a opção
        # "Trocar de conta" da própria tela do Meta.
        auth_url = f"{INSTAGRAM_AUTHORIZE_URL}?{urlencode(params)}"
        _ = request.force_new_account  # mantido na request pra compat; ignorado

        # Modo link (agência): encurta o auth_url num link curto (mesmo `code` liga os dois docs)
        # e cria o convite nomeado guardando esse link pra mandar pro cliente.
        if request.link_mode and invite_code:
            auth_url = _create_short_connect_link(invite_code, auth_url)
            _create_agency_invite(invite_code, user_uid, client_name, client_email, connect_link=auth_url)

        logger.info(
            "Instagram OAuth URL gerada user_uid=%s redirect_uri=%s link_mode=%s",
            user_uid, request.redirect_uri, request.link_mode,
        )
        return InstagramLoginResponse(auth_url=auth_url, code=invite_code)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao gerar URL Instagram OAuth: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


@router.get("/c/{code}")
async def resolve_connect_link(code: str):
    """Resolve o link curto do modo agência → 302 pro OAuth do Instagram. Página amigável se
    inválido/expirado. Sem auth: é um link público que a agência manda pro cliente."""
    snap = firestore.Client().collection(CONNECT_LINKS_COLLECTION).document(code).get()
    data = snap.to_dict() if snap.exists else None
    if not data or int(time.time()) > int(data.get("expires_at", 0)):
        return HTMLResponse(
            "<html><head><meta charset='utf-8'></head>"
            "<body style='font-family:system-ui;text-align:center;padding:64px;color:#425466'>"
            "<h2 style='color:#121E66'>Link inválido ou expirado</h2>"
            "<p>Peça um novo link de conexão para a agência.</p></body></html>",
            status_code=410,
        )
    return RedirectResponse(data["auth_url"], status_code=302)


@router.post("/instagram/process-callback", response_model=InstagramCallbackResponse)
async def instagram_process_callback(
    request: InstagramCallbackRequest,
    user_uid_opt: Optional[str] = Depends(get_user_uid_optional),
):
    """Processa callback OAuth Instagram Login API e configura integração.

    Dois modos:
    - Logado (bearer presente): o usuário conecta a PRÓPRIA conta. uid vem do bearer e o state
      precisa bater com ele (TTL curto).
    - Link (sem bearer): a agência gerou o link e mandou pro cliente. O cliente abre e conecta a
      conta dele sem estar logado no Proof; o uid vem do state assinado (mode="link", TTL longo).
      O portão de unicidade (WS2) garante que a conta cai na agência certa e não é sequestrada.

    Body: {"code": "...", "state": "...", "redirect_uri": "..."}
    """
    # Limpa fragmento `#_=_` que Meta às vezes adiciona.
    cleaned_state = (request.state or "").split("#")[0].rstrip("_=").strip()

    try:
        if user_uid_opt:
            st = validate_state(state=cleaned_state, user_uid=user_uid_opt)
        else:
            st = validate_state(
                state=cleaned_state,
                expected_mode="link",
                ttl_seconds=STATE_LINK_TTL_SECONDS,
            )
    except InvalidStateError as e:
        logger.warning("OAuth state inválido reason=%s", e)
        raise HTTPException(status_code=400, detail=f"State inválido ou expirado: {e}")

    user_uid = st.uid
    invite_code = st.code  # "" no fluxo de login; preenchido no convite de agência (modo link)

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

            try:
                long_token, expires_in = await _exchange_short_for_long_token(
                    client, app_secret, short_token,
                )
            except HTTPException as exch_err:
                # "Unsupported request - method type: get" (code 100) na troca long-lived.
                #
                # DIAGNÓSTICO 2026-07-08: para contas de TERCEIROS, a causa real desse erro
                # é que as permissões instagram_business_* do app Meta estão em Standard
                # Access ("Pronto para teste"), não Advanced Access. Em Standard Access só
                # contas com papel no app (admin/dev/Instagram Tester) conseguem usar o
                # token; qualquer cliente externo autoriza (code→short OK) mas o token nasce
                # inerte no graph.instagram.com e QUALQUER GET com ele (inclusive /me) é
                # rejeitado. Ou seja: o cliente PODE já ser Profissional e mesmo assim
                # falhar. NÃO classifique este erro como "conta pessoal/inelegível".
                #
                # TENSÃO com _is_transient_meta_error: aquela função trata o MESMO erro
                # (code 100 + "unsupported request") como transitório e faz retry, na
                # hipótese de glitch de roteamento da Meta. O retry é mantido de propósito;
                # se ele esgotar e cairmos aqui, o cenário provável é falta de Advanced
                # Access, não conta pessoal. As duas hipóteses convivem — não removê-las.
                detail_str = str(exch_err.detail or "")
                app_sem_advanced_access = (
                    "unsupported request" in detail_str.lower()
                    or "method type: get" in detail_str.lower()
                )
                # Best-effort: tenta ler username/tipo (geralmente também falha aqui).
                # account_type só distingue conta pessoal DE FATO — e não é o caso comum.
                uname, acc_type = "", ""
                try:
                    diag = await _fetch_instagram_profile(client, short_token)
                    uname = diag.get("username") or ""
                    acc_type = str(diag.get("account_type") or "").upper()
                except Exception:
                    pass
                conta_pessoal = bool(acc_type) and acc_type not in (
                    "BUSINESS", "MEDIA_CREATOR", "CREATOR",
                )
                logger.error(
                    "short→long FALHOU user_uid=%s conta=@%s account_type=%s "
                    "app_sem_advanced_access=%s conta_pessoal=%s :: %s",
                    user_uid, uname or "?", acc_type or "DESCONHECIDO",
                    app_sem_advanced_access, conta_pessoal, detail_str,
                )
                if conta_pessoal:
                    # Sinal DEFINITIVO de conta pessoal — é o único caso que o PRÓPRIO usuário
                    # resolve. Mensagem acionável (não "tente mais tarde").
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "personal_account",
                            "message": (
                                "Sua conta do Instagram precisa ser Profissional (Business ou "
                                "Criador). No app do Instagram: Configurações → Tipo de conta e "
                                "ferramentas → Mudar para conta profissional. Depois volte e tente "
                                "conectar de novo."
                            ),
                        },
                    )
                if app_sem_advanced_access:
                    # Standard Access (App Review pendente) — pendência NOSSA. Uma conta profissional
                    # pode falhar aqui; NÃO classificar como conta pessoal (ver comentário acima).
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "app_access_pending",
                            "message": (
                                "Ainda não conseguimos conectar contas externas — nosso acesso à API "
                                "do Instagram está em liberação junto à Meta. Se você é testador, "
                                "confirme que foi adicionado como tester no app; senão, tente mais "
                                "tarde ou fale com o suporte."
                            ),
                        },
                    )
                raise exch_err

            profile = await _fetch_instagram_profile(client, long_token)

        new_account_id = str(profile.get("id") or ig_user_id)
        new_account_username = profile.get("username") or ""

        # Portão multi-tenant (WS2): a conta só pode pertencer a UMA agência (unicidade
        # global) e o plano tem teto de contas. Roda ANTES de gravar token/conta — se
        # recusar, nada é persistido. Reconexão da própria conta é no-op (segue o refresh).
        try:
            tenancy.claim_account_for_uid(db, user_uid, new_account_id)
        except tenancy.AccountAlreadyClaimed:
            logger.warning(
                "conexão recusada (conta já é de outra agência) user_uid=%s ig_id=%s",
                user_uid, new_account_id,
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "account_already_claimed",
                    "message": (
                        "Essa conta do Instagram já está conectada a outra conta Proof. Se ela é "
                        "sua, desconecte na outra conta primeiro; se acha que é engano, fale com o "
                        "suporte."
                    ),
                },
            )
        except tenancy.PlanLimitReached as e:
            logger.warning(
                "conexão recusada (teto de plano) user_uid=%s ig_id=%s teto=%s",
                user_uid, new_account_id, e,
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "plan_limit",
                    "message": (
                        "Você atingiu o limite de contas do seu plano. Faça upgrade em "
                        "Configurações → Assinatura para conectar mais contas."
                    ),
                },
            )

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
        # Convite de agência (modo link): marca o convite como conectado assim que o cliente
        # conclui o OAuth e dispara o pipeline server-side no platform (catálogo → dossiê →
        # auto-confirm → score). O trigger é best-effort — não falha o OAuth se o platform cair.
        if invite_code:
            _mark_invite_connected(invite_code, new_account_id, new_account_username or None)
            await _trigger_agency_pipeline(user_uid, new_account_id, invite_code)

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

    Retorna (short_token, ig_user_id). Faz retry em erro transitório da Meta
    (vide _is_transient_meta_error); NÃO retenta code já usado / secret errado.
    """
    last_body: dict = {}
    for attempt in range(1, _LONG_TOKEN_MAX_ATTEMPTS + 1):
        try:
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
        except httpx.RequestError as e:
            logger.warning(
                "code→short_token tentativa %d/%d falhou no transporte: %s",
                attempt, _LONG_TOKEN_MAX_ATTEMPTS, e,
            )
            if attempt < _LONG_TOKEN_MAX_ATTEMPTS:
                await asyncio.sleep(_LONG_TOKEN_BACKOFF_S[attempt - 1])
                continue
            raise HTTPException(status_code=400, detail=f"Erro de rede ao trocar code por token: {e}")

        if resp.status_code == 200:
            payload = resp.json()
            short_token = payload.get("access_token")
            ig_user_id = str(payload.get("user_id") or "")
            if not short_token:
                raise HTTPException(status_code=400, detail="Resposta sem access_token")
            # Diagnóstico: QUAL conta IG autorizou (ig_user_id/IGSID) + escopos concedidos.
            # Se graph.instagram.com depois rejeitar o token ("Unsupported request"), isto
            # revela se autorizou a conta ERRADA (navegador logado em outra) ou se faltou
            # escopo — sem depender do /me (que falha p/ token inelegível).
            logger.info(
                "code→short OK (try %d): ig_user_id=%s permissions=%s",
                attempt, ig_user_id, payload.get("permissions"),
            )
            return short_token, ig_user_id

        last_body = resp.json() if resp.content else {}
        error_msg = last_body.get("error_message") or last_body.get("error", {}).get("message", "")
        # Code reusage: IG retorna "Authorization code has been used" — erro
        # PERMANENTE, não retenta; devolve a integração existente se houver.
        if "has been used" in str(error_msg).lower() and existing_doc and existing_doc.exists:
            data = existing_doc.to_dict() or {}
            logger.warning("Código já usado; devolvendo integração existente")
            response_data = _build_response_from_doc(data, message="Integração já configurada.")
            # Lança HTTPException pra interromper o fluxo principal
            raise HTTPException(status_code=200, detail=response_data.model_dump())

        transient = _is_transient_meta_error(resp.status_code, last_body)
        logger.error(
            "IG /oauth/access_token retornou %d (tentativa %d/%d, transitório=%s): %s",
            resp.status_code, attempt, _LONG_TOKEN_MAX_ATTEMPTS, transient, last_body,
        )
        if transient and attempt < _LONG_TOKEN_MAX_ATTEMPTS:
            await asyncio.sleep(_LONG_TOKEN_BACKOFF_S[attempt - 1])
            continue
        break

    raise HTTPException(
        status_code=400,
        detail=f"Erro ao trocar code por token: {last_body}",
    )


# Retry da troca short→long. O endpoint graph.instagram.com/access_token às vezes
# recusa a MESMA requisição GET com "Unsupported request - method type: get"
# (IGApiException code 100) ou 5xx — glitch transitório de roteamento da Meta: a
# requisição idêntica passa (200) segundos depois. Sem retry, o user vê
# "Erro ao processar integração" e fica travado no signup. Confirmado em log:
# mesma URL/método/secret deu 200 às 18:50 e 400 às 23:16 do mesmo dia.
# O mesmo limite/backoff é reusado pelas outras duas chamadas Graph do callback
# (_exchange_code_for_short_token e _fetch_instagram_profile), que sofrem do
# mesmo soluço transitório.
_LONG_TOKEN_MAX_ATTEMPTS = 3
_LONG_TOKEN_BACKOFF_S = (0.6, 1.5)  # espera antes das tentativas 2 e 3


def _is_transient_meta_error(status_code: int, body: dict) -> bool:
    """True se o erro da Meta é transitório (vale retry). NÃO retenta erro
    permanente (token inválido=190, permissão, secret errado)."""
    if status_code >= 500:
        return True
    err = (body or {}).get("error") or {}
    code = err.get("code")
    msg = str(err.get("message") or "").lower()
    # code 100 + "unsupported request - method type: get" = glitch de roteamento
    if code == 100 and "unsupported request" in msg:
        return True
    # codes documentados como transitórios: 1 (unknown), 2 (service indisponível)
    if code in (1, 2):
        return True
    return False


async def _exchange_short_for_long_token(
    client: httpx.AsyncClient,
    app_secret: str,
    short_token: str,
) -> tuple[str, int]:
    """GET graph.instagram.com/access_token?grant_type=ig_exchange_token.

    Retorna (long_token, expires_in_seconds). Faz retry em erro transitório da
    Meta (vide _is_transient_meta_error).
    """
    last_body: dict = {}
    for attempt in range(1, _LONG_TOKEN_MAX_ATTEMPTS + 1):
        try:
            resp = await client.get(
                INSTAGRAM_GRAPH_LONG_TOKEN_URL,
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": app_secret,
                    "access_token": short_token,
                },
            )
        except httpx.RequestError as e:
            logger.warning(
                "ig_exchange_token tentativa %d/%d falhou no transporte: %s",
                attempt, _LONG_TOKEN_MAX_ATTEMPTS, e,
            )
            if attempt < _LONG_TOKEN_MAX_ATTEMPTS:
                await asyncio.sleep(_LONG_TOKEN_BACKOFF_S[attempt - 1])
                continue
            raise HTTPException(status_code=400, detail=f"Erro de rede ao converter token: {e}")

        if resp.status_code == 200:
            payload = resp.json()
            long_token = payload.get("access_token")
            expires_in = int(payload.get("expires_in") or 0)
            if not long_token:
                raise HTTPException(status_code=400, detail="Resposta sem long-lived token")
            if attempt > 1:
                logger.info("ig_exchange_token OK na tentativa %d (erro transitório superado)", attempt)
            return long_token, expires_in

        last_body = resp.json() if resp.content else {}
        transient = _is_transient_meta_error(resp.status_code, last_body)
        logger.error(
            "ig_exchange_token retornou %d (tentativa %d/%d, transitório=%s): %s",
            resp.status_code, attempt, _LONG_TOKEN_MAX_ATTEMPTS, transient, last_body,
        )
        if transient and attempt < _LONG_TOKEN_MAX_ATTEMPTS:
            await asyncio.sleep(_LONG_TOKEN_BACKOFF_S[attempt - 1])
            continue
        break

    raise HTTPException(
        status_code=400,
        detail=f"Erro ao converter pra long-lived token: {last_body}",
    )


async def _fetch_instagram_profile(
    client: httpx.AsyncClient,
    long_token: str,
) -> dict:
    """GET graph.instagram.com/v20.0/me — busca id, username, account_type, etc.

    Faz retry em erro transitório da Meta (vide _is_transient_meta_error); NÃO
    retenta token inválido (code 190) / permissão.
    """
    last_body: dict = {}
    for attempt in range(1, _LONG_TOKEN_MAX_ATTEMPTS + 1):
        try:
            resp = await client.get(
                INSTAGRAM_GRAPH_ME_URL,
                params={
                    "fields": "id,username,account_type,followers_count,media_count,profile_picture_url,name",
                    "access_token": long_token,
                },
            )
        except httpx.RequestError as e:
            logger.warning(
                "/me tentativa %d/%d falhou no transporte: %s",
                attempt, _LONG_TOKEN_MAX_ATTEMPTS, e,
            )
            if attempt < _LONG_TOKEN_MAX_ATTEMPTS:
                await asyncio.sleep(_LONG_TOKEN_BACKOFF_S[attempt - 1])
                continue
            raise HTTPException(status_code=400, detail=f"Erro de rede ao buscar perfil Instagram: {e}")

        if resp.status_code == 200:
            if attempt > 1:
                logger.info("/me OK na tentativa %d (erro transitório superado)", attempt)
            return resp.json()

        last_body = resp.json() if resp.content else {}
        transient = _is_transient_meta_error(resp.status_code, last_body)
        logger.error(
            "/me retornou %d (tentativa %d/%d, transitório=%s): %s",
            resp.status_code, attempt, _LONG_TOKEN_MAX_ATTEMPTS, transient, last_body,
        )
        if transient and attempt < _LONG_TOKEN_MAX_ATTEMPTS:
            await asyncio.sleep(_LONG_TOKEN_BACKOFF_S[attempt - 1])
            continue
        break

    raise HTTPException(
        status_code=400,
        detail=f"Erro ao buscar perfil Instagram: {last_body}",
    )


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
