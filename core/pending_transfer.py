"""Transferência de conta entre agências — stash server-side da conexão pendente.

Quando o cliente conecta uma conta que JÁ pertence a outra agência, não é mais beco-sem-saída (409):
guardamos aqui a conexão já autorizada (token + conta + convite) por pouco tempo e mandamos o cliente
pra uma tela "manter ou transferir". Se confirmar, o /transfer/confirm efetiva; senão expira/some.

O token IG fica no doc por no máx. 15min e é apagado no confirm/cancel — mesma sensibilidade do token
que já seria salvo no connect, só que efêmero.
"""
from __future__ import annotations

import secrets
import time

from google.cloud import firestore

COLLECTION = "pp_pending_transfers"
TTL_SECONDS = 900   # 15 min


def create(db: firestore.Client, data: dict) -> str:
    token = secrets.token_urlsafe(24)
    db.collection(COLLECTION).document(token).set({**data, "created_at": firestore.SERVER_TIMESTAMP})
    return token


def get(db: firestore.Client, token: str) -> dict | None:
    if not token:
        return None
    ref = db.collection(COLLECTION).document(token)
    snap = ref.get()
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    ca = d.get("created_at")
    try:
        if ca and (time.time() - ca.timestamp()) > TTL_SECONDS:
            ref.delete()
            return None
    except Exception:  # noqa: BLE001 — se o timestamp não resolver, deixa passar (o confirm revalida)
        pass
    return d


def delete(db: firestore.Client, token: str) -> None:
    try:
        db.collection(COLLECTION).document(token).delete()
    except Exception:  # noqa: BLE001
        pass
