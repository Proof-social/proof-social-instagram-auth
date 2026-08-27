"""Testes do OAuth state (core/state.py) — modo login vs link + compat + HMAC.

O modo é ASSINADO no state: um state de login não pode ser reusado no callback público
(modo link). O caminho link valida sem exigir uid externo (o uid vem do próprio state).
"""
import base64
import hashlib
import hmac
import os
import time

import pytest

os.environ.setdefault("OAUTH_STATE_SIGNING_KEY", "test-key-123")

from core.state import (  # noqa: E402
    generate_state,
    validate_state,
    InvalidStateError,
    STATE_LINK_TTL_SECONDS,
)


def test_link_valida_no_caminho_publico_retorna_uid():
    s = generate_state("agencyUID", "link")
    assert validate_state(state=s, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS) == "agencyUID"


def test_login_rejeitado_no_caminho_link():
    s = generate_state("uUID", "login")
    with pytest.raises(InvalidStateError):
        validate_state(state=s, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)


def test_login_uid_precisa_bater():
    s = generate_state("uUID", "login")
    assert validate_state(state=s, user_uid="uUID") == "uUID"
    with pytest.raises(InvalidStateError):
        validate_state(state=s, user_uid="OUTRO")


def test_compat_state_legado_5_partes():
    raw = f"v1|legacyUID|{'n' * 32}|{int(time.time())}"
    sig = hmac.new(b"test-key-123", raw.encode(), hashlib.sha256).hexdigest()
    legacy = base64.urlsafe_b64encode(f"{raw}|{sig}".encode()).rstrip(b"=").decode()
    assert validate_state(state=legacy, user_uid="legacyUID") == "legacyUID"


def test_hmac_adulterado_rejeitado():
    s = generate_state("uUID", "link")
    with pytest.raises(InvalidStateError):
        validate_state(state=s[:-4] + "AAAA", expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)


def test_expirado_rejeitado():
    # gera com ts no passado adulterando não dá (HMAC); usa TTL 0 pra forçar expiração
    s = generate_state("uUID", "login")
    time.sleep(1)
    with pytest.raises(InvalidStateError):
        validate_state(state=s, user_uid="uUID", ttl_seconds=0)
