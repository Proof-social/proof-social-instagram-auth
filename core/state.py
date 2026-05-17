"""OAuth state com HMAC + nonce + TTL.

A versão antiga usava `state = user_uid` direto — um valor estável e potencialmente
vazado em logs/URLs. Isso permite ataque CSRF onde o atacante engana o usuário
a clicar num link OAuth com `state=meu_uid&code=...`, vinculando a conta Meta do
atacante na sessão da vítima.

Esta versão:
- Gera state = `b64(uid|nonce|ts|hmac_sha256(secret, uid|nonce|ts))`
- Valida: HMAC bate, ts dentro do TTL (10min default), uid bate com o autenticado.
- Inutilizável fora da janela ou por outro user.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 600  # 10 minutos — janela típica para concluir OAuth
STATE_VERSION = "v1"


class InvalidStateError(Exception):
    """State recebido é inválido (HMAC errado, expirado, ou para outro user)."""


def _signing_key() -> bytes:
    """Chave HMAC para assinar state. Falha fechado se ausente."""
    key = os.getenv("OAUTH_STATE_SIGNING_KEY", "").strip()
    if not key:
        # Fallback temporário: derivar de FACEBOOK_APP_SECRET. Não ideal mas
        # melhor que vazio (manter os fluxos OAuth funcionando enquanto a env
        # nova é configurada).
        app_secret = os.getenv("FACEBOOK_APP_SECRET", "").strip()
        if not app_secret:
            raise InvalidStateError(
                "OAUTH_STATE_SIGNING_KEY ou FACEBOOK_APP_SECRET é obrigatório"
            )
        key = app_secret
    return key.encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


def generate_state(user_uid: str) -> str:
    """Gera state assinado para fluxo OAuth.

    Formato (após base64): `v1|<uid>|<nonce>|<ts>|<hmac>`
    """
    if not user_uid:
        raise ValueError("user_uid obrigatório")

    nonce = uuid.uuid4().hex
    ts = str(int(time.time()))
    msg = f"{STATE_VERSION}|{user_uid}|{nonce}|{ts}"
    sig = hmac.new(_signing_key(), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{msg}|{sig}"
    return _b64encode(raw.encode("utf-8"))


def validate_state(*, state: str, user_uid: str, ttl_seconds: int = STATE_TTL_SECONDS) -> None:
    """Valida state recebido no callback. Levanta InvalidStateError em qualquer falha.

    - Decodifica base64.
    - Confere versão, formato, HMAC.
    - Confere que `uid` no state == `user_uid` autenticado.
    - Confere que ts está dentro da janela `ttl_seconds`.
    """
    if not state:
        raise InvalidStateError("state vazio")

    try:
        raw = _b64decode(state.strip()).decode("utf-8")
    except Exception as e:
        raise InvalidStateError(f"state base64 inválido: {e}")

    parts = raw.split("|")
    if len(parts) != 5:
        raise InvalidStateError(f"state com formato inesperado: {len(parts)} partes")

    version, claimed_uid, nonce, ts_str, sig = parts
    if version != STATE_VERSION:
        raise InvalidStateError(f"versão de state não suportada: {version}")

    # Recomputa HMAC e compara em tempo constante.
    expected_msg = f"{version}|{claimed_uid}|{nonce}|{ts_str}"
    expected_sig = hmac.new(
        _signing_key(), expected_msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        raise InvalidStateError("HMAC do state não bate")

    # uid do state precisa bater com o autenticado.
    if claimed_uid != user_uid:
        raise InvalidStateError(
            f"state pertence a outro usuário (got={claimed_uid!r}, expected={user_uid!r})"
        )

    # Janela temporal.
    try:
        ts = int(ts_str)
    except ValueError:
        raise InvalidStateError("ts inválido")

    age = int(time.time()) - ts
    if age < 0 or age > ttl_seconds:
        raise InvalidStateError(f"state expirado (age={age}s, ttl={ttl_seconds}s)")
