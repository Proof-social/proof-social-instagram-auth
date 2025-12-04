"""
Endpoints de autenticação OAuth Instagram/Meta
"""

import logging
import uuid
import httpx
from fastapi import APIRouter, HTTPException, Header, Depends, Response, Response
from typing import Optional
from urllib.parse import urlencode
import json
from schemas.instagram import (
    InstagramLoginRequest,
    InstagramLoginResponse,
    InstagramCallbackRequest,
    InstagramCallbackResponse,
    InstagramAccount,
    InstagramPage
)
from core.security import (
    verify_firebase_token,
    get_meta_config,
    save_access_token
)
from google.cloud import firestore
import os
from urllib.parse import urlencode
import json

logger = logging.getLogger(__name__)
router = APIRouter()

# Permissões Instagram/Meta necessárias
INSTAGRAM_SCOPES = [
    "pages_show_list",
    "ads_management",
    "ads_read",
    "instagram_basic",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "instagram_content_publish",
    "instagram_manage_messages",
    "pages_read_engagement",
    "pages_manage_ads",
    "instagram_branded_content_ads_brand",
    "instagram_manage_events"
]


async def get_user_uid(authorization: Optional[str] = Header(None)) -> str:
    """Dependency para validar Firebase token e retornar user_uid"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorização não fornecido")
    return await verify_firebase_token(authorization)


@router.post("/instagram/login", response_model=InstagramLoginResponse)
async def instagram_login(
    request: InstagramLoginRequest,
    user_uid: str = Depends(get_user_uid)
):
    """
    Gera URL de autorização Meta/Instagram OAuth
    
    Args:
        request: Contém redirect_uri
        user_uid: Extraído do token Firebase
        
    Returns:
        URL de autorização Meta
    """
    try:
        # Busca configurações Meta
        config = await get_meta_config(user_uid)
        app_id = config["app_id"]
        
        # Gera URL de autorização
        scopes = ",".join(INSTAGRAM_SCOPES)
        state = user_uid  # Usa user_uid como state para validação
        
        auth_url = (
            f"https://www.facebook.com/v20.0/dialog/oauth?"
            f"client_id={app_id}&"
            f"redirect_uri={request.redirect_uri}&"
            f"state={state}&"
            f"response_type=code&"
            f"scope={scopes}"
        )
        
        logger.info(f"URL de autorização gerada para user_uid: {user_uid}")
        
        return InstagramLoginResponse(auth_url=auth_url)
        
    except Exception as e:
        logger.error(f"Erro ao gerar URL de autorização: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar URL de autorização: {str(e)}")


@router.post("/instagram/process-callback", response_model=InstagramCallbackResponse)
async def instagram_process_callback(
    request: InstagramCallbackRequest,
    user_uid: str = Depends(get_user_uid)
):
    """
    Processa callback OAuth e configura integração Instagram
    
    Args:
        request: Contém code e state do callback
        user_uid: Extraído do token Firebase
        
    Returns:
        Dados da integração configurada
    """
    try:
        # Valida state
        if request.state != user_uid:
            raise HTTPException(
                status_code=400,
                detail="State não corresponde ao usuário autenticado"
            )
        
        # Busca configurações Meta
        config = await get_meta_config(user_uid)
        app_id = config["app_id"]
        app_secret = config["app_secret"]
        
        # Troca code por access_token
        async with httpx.AsyncClient() as client:
            # 1. Trocar code por access_token de curta duração
            token_response = await client.get(
                "https://graph.facebook.com/v20.0/oauth/access_token",
                params={
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "redirect_uri": request.redirect_uri,
                    "code": request.code
                }
            )
            
            if token_response.status_code != 200:
                error_data = token_response.json() if token_response.content else {}
                raise HTTPException(
                    status_code=400,
                    detail=f"Erro ao trocar code por token: {error_data}"
                )
            
            token_data = token_response.json()
            short_lived_token = token_data.get("access_token")
            
            if not short_lived_token:
                raise HTTPException(
                    status_code=400,
                    detail="Token de acesso não retornado pela API Meta"
                )
            
            # 2. Converter para token de longa duração
            long_token_response = await client.get(
                "https://graph.facebook.com/v20.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": short_lived_token
                }
            )
            
            if long_token_response.status_code != 200:
                error_data = long_token_response.json() if long_token_response.content else {}
                raise HTTPException(
                    status_code=400,
                    detail=f"Erro ao converter para token de longa duração: {error_data}"
                )
            
            long_token_data = long_token_response.json()
            long_lived_token = long_token_data.get("access_token", short_lived_token)
            
            # 3. Salvar token no Secret Manager
            await save_access_token(user_uid, long_lived_token)
            
            # 4. Buscar páginas do usuário
            pages_response = await client.get(
                "https://graph.facebook.com/v20.0/me/accounts",
                params={
                    "access_token": long_lived_token,
                    "fields": "id,name,instagram_business_account{id,username}"
                }
            )
            
            pages = []
            instagram_accounts = []
            
            if pages_response.status_code == 200:
                pages_data = pages_response.json()
                for page_data in pages_data.get("data", []):
                    page = InstagramPage(
                        id=page_data["id"],
                        name=page_data.get("name", "")
                    )
                    
                    # Verifica se tem conta Instagram conectada
                    if "instagram_business_account" in page_data:
                        ig_account_data = page_data["instagram_business_account"]
                        ig_account = InstagramAccount(
                            id=ig_account_data["id"],
                            username=ig_account_data.get("username"),
                            name=page_data.get("name")
                        )
                        page.instagram_business_account = ig_account
                        instagram_accounts.append(ig_account)
                    
                    pages.append(page)
            
            # 5. Gerar API key única
            api_key = str(uuid.uuid4())
            
            # 6. Salvar integração no Firestore
            db = firestore.Client()
            integration_ref = db.collection("integrations").document(user_uid)
            integration_ref.set({
                "user_uid": user_uid,
                "platform": "instagram",
                "api_key": api_key,
                "status": "active",
                "created_at": firestore.SERVER_TIMESTAMP,
                "instagram_accounts": [
                    {
                        "id": acc.id,
                        "username": acc.username,
                        "name": acc.name
                    } for acc in instagram_accounts
                ],
                "pages": [
                    {
                        "id": page.id,
                        "name": page.name,
                        "instagram_business_account_id": page.instagram_business_account.id if page.instagram_business_account else None
                    } for page in pages
                ]
            })
            
            logger.info(f"Integração Instagram configurada para user_uid: {user_uid}")
            
            # Preparar dados para incluir na URL de callback
            callback_data = {
                "api_key": api_key,
                "instagram_accounts": [
                    {
                        "id": acc.id,
                        "username": acc.username or "",
                        "name": acc.name or ""
                    } for acc in instagram_accounts
                ],
                "pages": [
                    {
                        "id": page.id,
                        "name": page.name,
                        "instagram_business_account": {
                            "id": page.instagram_business_account.id,
                            "username": page.instagram_business_account.username or "",
                            "name": page.instagram_business_account.name or ""
                        } if page.instagram_business_account else None
                    } for page in pages
                ],
                "message": "Integração Instagram configurada com sucesso",
                "status": "success"
            }
            
            # Codificar dados como JSON na query string
            data_json = json.dumps(callback_data)
            encoded_data = urlencode({"data": data_json})
            
            # Construir URL de callback com os dados
            callback_url = f"{request.redirect_uri}?{encoded_data}"
            
            # Redirecionar para a URL de callback com os dados
            return Response(
                status_code=302,
                headers={"Location": callback_url}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar callback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar callback: {str(e)}"
        )

