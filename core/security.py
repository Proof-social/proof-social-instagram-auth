"""
Validação de segurança e autenticação Firebase
"""

import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth
from google.cloud import secretmanager
import os

logger = logging.getLogger(__name__)

# Inicializar Firebase Admin SDK
try:
    if not firebase_admin._apps:
        # Tenta usar credenciais do ambiente ou arquivo
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
            firebase_admin.initialize_app(cred)
        else:
            # Usa credenciais padrão do GCP
            firebase_admin.initialize_app()
except Exception as e:
    logger.warning(f"Firebase Admin SDK não inicializado: {e}")


async def verify_firebase_token(authorization: str) -> str:
    """
    Valida token Firebase Auth e retorna user_uid
    
    Args:
        authorization: Header Authorization no formato "Bearer {token}"
        
    Returns:
        user_uid: ID do usuário do Firebase
        
    Raises:
        ValueError: Se o token for inválido ou não fornecido
    """
    if not authorization:
        raise ValueError("Token de autorização não fornecido")
    
    try:
        # Remove "Bearer " do início
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        
        # Verifica o token
        decoded_token = auth.verify_id_token(token)
        user_uid = decoded_token.get("uid")
        
        if not user_uid:
            raise ValueError("Token não contém user_uid")
        
        logger.info(f"Token Firebase validado para user_uid: {user_uid}")
        return user_uid
        
    except auth.InvalidIdTokenError as e:
        logger.error(f"Token Firebase inválido: {e}")
        raise ValueError(f"Token inválido: {e}")
    except Exception as e:
        logger.error(f"Erro ao validar token Firebase: {e}")
        raise ValueError(f"Erro ao validar token: {e}")


def get_secret_manager_client():
    """Retorna cliente do Secret Manager"""
    return secretmanager.SecretManagerServiceClient()


async def get_meta_config(user_uid: str) -> dict:
    """
    Busca configurações Meta do Secret Manager
    
    Args:
        user_uid: ID do usuário
        
    Returns:
        dict com app_id e app_secret
    """
    client = get_secret_manager_client()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "proof-social")
    
    try:
        # Busca App ID
        app_id_name = f"projects/{project_id}/secrets/proof-social-meta-app-id/versions/latest"
        app_id_response = client.access_secret_version(request={"name": app_id_name})
        app_id = app_id_response.payload.data.decode("UTF-8")
        
        # Busca App Secret
        app_secret_name = f"projects/{project_id}/secrets/proof-social-meta-app-secret/versions/latest"
        app_secret_response = client.access_secret_version(request={"name": app_secret_name})
        app_secret = app_secret_response.payload.data.decode("UTF-8")
        
        return {
            "app_id": app_id,
            "app_secret": app_secret
        }
    except Exception as e:
        logger.error(f"Erro ao buscar configurações Meta: {e}")
        raise ValueError(f"Erro ao buscar configurações: {e}")


async def save_access_token(user_uid: str, access_token: str):
    """
    Salva access token no Secret Manager
    
    Args:
        user_uid: ID do usuário
        access_token: Token de acesso do Meta
    """
    client = get_secret_manager_client()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "proof-social-ai")
    secret_id = f"proof-social-instagram-{user_uid}"
    
    try:
        # Verifica se o secret já existe
        parent = f"projects/{project_id}"
        try:
            client.get_secret(request={"name": f"{parent}/secrets/{secret_id}"})
        except Exception:
            # Cria o secret se não existir
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
        
        # Adiciona nova versão do secret
        client.add_secret_version(
            request={
                "parent": f"{parent}/secrets/{secret_id}",
                "payload": {"data": access_token.encode("UTF-8")},
            }
        )
        
        logger.info(f"Token salvo no Secret Manager para user_uid: {user_uid}")
    except Exception as e:
        logger.error(f"Erro ao salvar token no Secret Manager: {e}")
        raise ValueError(f"Erro ao salvar token: {e}")

