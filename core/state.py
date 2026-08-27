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

STATE_TTL_SECONDS = 600  # 10 minutos — janela típica para concluir OAuth (fluxo logado)
STATE_LINK_TTL_SECONDS = 7 * 24 * 3600  # 7 dias — modo "link" (agência gera, cliente abre depois)
STATE_VERSION = "v1"
VALID_MODES = ("login", "link")


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


def generate_state(user_uid: str, mode: str = "login") -> str:
    """Gera state assinado para fluxo OAuth.

    Formato (após base64): `v1|<uid>|<mode>|<nonce>|<ts>|<hmac>`
    `mode`: "login" (fluxo logado, o usuário conecta a própria conta) ou "link"
    (agência gera o link, o cliente abre e conecta a conta dele — sem estar logado no Proof).
    O mode é ASSINADO: um state de login não pode ser reusado no callback público (modo link).
    """
    if not user_uid:
        raise ValueError("user_uid obrigatório")
    if mode not in VALID_MODES:
        raise ValueError(f"mode inválido: {mode!r}")

    nonce = uuid.uuid4().hex
    ts = str(int(time.time()))
    msg = f"{STATE_VERSION}|{user_uid}|{mode}|{nonce}|{ts}"
    sig = hmac.new(_signing_key(), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{msg}|{sig}"
    return _b64encode(raw.encode("utf-8"))


def validate_state(
    *,
    state: str,
    user_uid: Optional[str] = None,
    expected_mode: Optional[str] = None,
    ttl_seconds: int = STATE_TTL_SECONDS,
) -> str:
    """Valida state recebido no callback e RETORNA o uid do state. Levanta InvalidStateError.

    - Decodifica base64, confere versão, formato, HMAC.
    - `user_uid` (opcional): se dado, exige que o uid do state bata (fluxo logado). Se None,
      confia só na assinatura (fluxo link público) e devolve o uid do próprio state.
    - `expected_mode` (opcional): se dado, exige que o mode do state seja esse (ex: "link" no
      callback público — impede reusar um state de login lá).
    - `ttl_seconds`: janela temporal.

    Compat: aceita states legados de 5 partes (sem mode → tratados como "login").
    """
    if not state:
        raise InvalidStateError("state vazio")

    try:
        raw = _b64decode(state.strip()).decode("utf-8")
    except Exception as e:
        raise InvalidStateError(f"state base64 inválido: {e}")

    parts = raw.split("|")
    if len(parts) == 6:
        version, claimed_uid, mode, nonce, ts_str, sig = parts
        signed_msg = f"{version}|{claimed_uid}|{mode}|{nonce}|{ts_str}"
    elif len(parts) == 5:  # legado (pré-mode): trata como login
        version, claimed_uid, nonce, ts_str, sig = parts
        mode = "login"
        signed_msg = f"{version}|{claimed_uid}|{nonce}|{ts_str}"
    else:
        raise InvalidStateError(f"state com formato inesperado: {len(parts)} partes")

    if version != STATE_VERSION:
        raise InvalidStateError(f"versão de state não suportada: {version}")

    # Recomputa HMAC e compara em tempo constante.
    expected_sig = hmac.new(
        _signing_key(), signed_msg.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        raise InvalidStateError("HMAC do state não bate")

    # uid do state precisa bater com o autenticado (quando exigido).
    if user_uid is not None and claimed_uid != user_uid:
        raise InvalidStateError(
            f"state pertence a outro usuário (got={claimed_uid!r}, expected={user_uid!r})"
        )

    if expected_mode is not None and mode != expected_mode:
        raise InvalidStateError(
            f"state com mode inesperado (got={mode!r}, expected={expected_mode!r})"
        )

    # Janela temporal.
    try:
        ts = int(ts_str)
    except ValueError:
        raise InvalidStateError("ts inválido")

    age = int(time.time()) - ts
    if age < 0 or age > ttl_seconds:
        raise InvalidStateError(f"state expirado (age={age}s, ttl={ttl_seconds}s)")

    return claimed_uid
