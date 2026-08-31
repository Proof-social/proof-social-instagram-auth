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
    r = validate_state(state=s, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)
    assert r.uid == "agencyUID"
    assert r.mode == "link"
    assert r.code == ""


def test_login_rejeitado_no_caminho_link():
    s = generate_state("uUID", "login")
    with pytest.raises(InvalidStateError):
        validate_state(state=s, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)


def test_login_uid_precisa_bater():
    s = generate_state("uUID", "login")
    assert validate_state(state=s, user_uid="uUID").uid == "uUID"
    with pytest.raises(InvalidStateError):
        validate_state(state=s, user_uid="OUTRO")


def test_link_com_code_round_trip():
    # Convite de agência: o code viaja assinado e volta intacto no callback.
    s = generate_state("agencyUID", "link", code="abc123XY")
    r = validate_state(state=s, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)
    assert r.uid == "agencyUID"
    assert r.mode == "link"
    assert r.code == "abc123XY"


def test_code_adulterado_rejeitado():
    # Trocar o code sem re-assinar deve falhar no HMAC (o code é assinado).
    s = generate_state("agencyUID", "link", code="codeA")
    raw = base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4)).decode()
    parts = raw.split("|")  # v1|uid|mode|code|nonce|ts|sig
    parts[3] = "codeB"
    tampered_raw = "|".join(parts)
    tampered = base64.urlsafe_b64encode(tampered_raw.encode()).rstrip(b"=").decode()
    with pytest.raises(InvalidStateError):
        validate_state(state=tampered, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)


def test_code_com_pipe_rejeitado_na_geracao():
    with pytest.raises(ValueError):
        generate_state("agencyUID", "link", code="a|b")


def test_compat_state_6_partes_sem_code():
    # State no formato anterior (v1|uid|mode|nonce|ts|sig), sem code, continua válido.
    raw = f"v1|midUID|link|{'n' * 32}|{int(time.time())}"
    sig = hmac.new(b"test-key-123", raw.encode(), hashlib.sha256).hexdigest()
    old = base64.urlsafe_b64encode(f"{raw}|{sig}".encode()).rstrip(b"=").decode()
    r = validate_state(state=old, expected_mode="link", ttl_seconds=STATE_LINK_TTL_SECONDS)
    assert r.uid == "midUID"
    assert r.code == ""


def test_compat_state_legado_5_partes():
    raw = f"v1|legacyUID|{'n' * 32}|{int(time.time())}"
    sig = hmac.new(b"test-key-123", raw.encode(), hashlib.sha256).hexdigest()
    legacy = base64.urlsafe_b64encode(f"{raw}|{sig}".encode()).rstrip(b"=").decode()
    r = validate_state(state=legacy, user_uid="legacyUID")
    assert r.uid == "legacyUID"
    assert r.mode == "login"
    assert r.code == ""


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
