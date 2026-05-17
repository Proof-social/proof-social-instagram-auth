"""
Proof Social - Instagram OAuth API
API para autenticação OAuth com Meta/Instagram.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _allowed_origins() -> list[str]:
    """CSV de origens permitidas via env. Vazio = bloqueio."""
    raw = os.getenv("ALLOWED_CORS_ORIGINS", "").strip()
    if not raw:
        logger.warning(
            "ALLOWED_CORS_ORIGINS vazio — CORS bloqueia origens externas. "
            "Definir em produção."
        )
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="Proof Social Instagram Auth API",
    description="API para autenticação OAuth com Meta/Instagram",
    version="1.1.0",
)

# CORS restritivo. Sem allow_origins=["*"]: aceita explicitamente origens conhecidas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@app.get("/")
async def root():
    return {
        "message": "Proof Social Instagram Auth API",
        "version": "1.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Liveness probe — sempre 200 se processo vivo."""
    return {"status": "healthy"}


@app.get("/readyz")
async def readyz():
    """Readiness probe — verifica que envs core estão definidas.

    Sem checar Firestore/Secret Manager em todo readyz para evitar latência
    constante; o app falha rápido na primeira request real se algo quebrar.
    """
    missing = [
        k for k in ("GOOGLE_CLOUD_PROJECT", "OAUTH_STATE_SIGNING_KEY")
        if not os.getenv(k) and k != "OAUTH_STATE_SIGNING_KEY"
    ]
    # OAUTH_STATE_SIGNING_KEY tem fallback para FACEBOOK_APP_SECRET no core/state.py
    if not os.getenv("OAUTH_STATE_SIGNING_KEY") and not os.getenv("FACEBOOK_APP_SECRET"):
        missing.append("OAUTH_STATE_SIGNING_KEY (ou FACEBOOK_APP_SECRET)")
    if missing:
        return {"ready": False, "missing_envs": missing}
    return {"ready": True}
