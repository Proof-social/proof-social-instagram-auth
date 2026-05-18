"""Configuração do Instagram Login API (não-Facebook Login).

Lê IG_APP_ID e IG_APP_SECRET do Secret Manager. Diferentes credenciais
do Facebook Login: o produto "Instagram" no Meta App Dashboard tem
client_id/secret próprios.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from google.cloud import secretmanager

logger = logging.getLogger(__name__)


def _get_secret(secret_id: str) -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "theproofsocial")
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8").strip()


@lru_cache(maxsize=1)
def get_instagram_config() -> dict:
    """Retorna {app_id, app_secret} do Instagram Login API.

    Cache em-processo (16h-ish de uptime Cloud Run). Não cacheia em disco.
    """
    try:
        app_id = _get_secret("proof-social-instagram-app-id")
        app_secret = _get_secret("proof-social-instagram-app-secret")
        return {"app_id": app_id, "app_secret": app_secret}
    except Exception as e:
        logger.error("Falha ao buscar credenciais Instagram do Secret Manager: %s", e)
        raise RuntimeError(
            "proof-social-instagram-app-id / proof-social-instagram-app-secret "
            "não encontrados no Secret Manager"
        ) from e
