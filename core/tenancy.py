"""Portão multi-tenant no ponto de conexão de conta IG (WS2).

Este serviço é o ÚNICO lugar onde uma conta IG é escrita e o token nasce — logo é o portão
natural pra duas garantias de servidor (nunca no cliente):

  1. **Unicidade global (premissa 2):** uma conta IG pertence a UMA agência. A trava é a chave do
     doc no registro `pp_account_registry/{ig_account_id}` — o `.create()` falha se já existe.
  2. **Teto de plano (premissa 3):** a agência não conecta mais contas que o `accounts_limit`.

CONTRATO ESPELHADO: o modelo canônico mora no `proof-platform/modules/tenancy/repo.py`. Os dois
repos colam pelo MESMO Firestore (não por API), então este helper reimplementa o mesmo formato de
doc e a mesma lógica de claim. Qualquer mudança de contrato tem que andar nos dois. Ver
`refatoracao-multitenant.md`.

Sem fallback silencioso: colisão de conta ou estouro de teto vira erro visível (exceções abaixo,
mapeadas pra HTTP na rota).
"""
from __future__ import annotations

import uuid

from google.api_core import exceptions as gexc
from google.cloud import firestore

# --- coleções (idênticas às do proof-platform/core/config.py) ---
COLLECTION_AGENCIES = "pp_agencies"
COLLECTION_AGENCY_MEMBERS = "pp_agency_members"
COLLECTION_ACCOUNT_REGISTRY = "pp_account_registry"

# Teto de contas por plano. `custom` = None → usa o accounts_limit gravado na agência.
PLAN_ACCOUNT_LIMITS: dict[str, int | None] = {
    "free": 1, "individual": 1, "start": 3, "scale": 10, "custom": None,
}


class TenancyError(Exception):
    """Base."""


class AccountAlreadyClaimed(TenancyError):
    """Conta IG já pertence a OUTRA agência (unicidade global)."""


class PlanLimitReached(TenancyError):
    """Teto de contas do plano atingido."""


def _member_doc_id(agency_id: str, uid: str) -> str:
    return f"{agency_id}_{uid}"


def resolve_agency_id(db: firestore.Client, uid: str) -> str | None:
    """De qual agência este uid é membro? None se nenhum vínculo (dono primeiro)."""
    if not uid:
        return None
    q = db.collection(COLLECTION_AGENCY_MEMBERS).where("uid", "==", uid)
    members = sorted(
        (m.to_dict() or {} for m in q.stream()),
        key=lambda d: 0 if d.get("role") == "owner" else 1,
    )
    for m in members:
        if m.get("agency_id"):
            return str(m["agency_id"])
    return None


def get_or_create_agency(db: firestore.Client, uid: str) -> str:
    """Agência do uid; se ainda não tem (cadastro via WS3 não rodou, ou tester legado),
    provisiona uma agência `individual`/`free` (teto 1). Idempotente na prática — o signup
    (WS3) normalmente cria antes; aqui é a rede de segurança pra conexão não travar."""
    existing = resolve_agency_id(db, uid)
    if existing:
        return existing
    agency_id = uuid.uuid4().hex
    batch = db.batch()
    batch.set(db.collection(COLLECTION_AGENCIES).document(agency_id), {
        "agency_id": agency_id, "owner_uid": uid, "type": "individual",
        "name": "", "plan": "free", "accounts_limit": PLAN_ACCOUNT_LIMITS["free"],
        "stripe_customer_id": "", "stripe_subscription_id": "",
        "created_at": firestore.SERVER_TIMESTAMP, "updated_at": firestore.SERVER_TIMESTAMP,
    })
    batch.set(db.collection(COLLECTION_AGENCY_MEMBERS).document(_member_doc_id(agency_id, uid)), {
        "agency_id": agency_id, "uid": uid, "role": "owner",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    batch.commit()
    return agency_id


def _account_owner(db: firestore.Client, ig_account_id: str) -> str | None:
    snap = db.collection(COLLECTION_ACCOUNT_REGISTRY).document(str(ig_account_id)).get()
    if not snap.exists:
        return None
    return (snap.to_dict() or {}).get("agency_id") or None


def _count_accounts(db: firestore.Client, agency_id: str) -> int:
    q = db.collection(COLLECTION_ACCOUNT_REGISTRY).where("agency_id", "==", agency_id)
    return sum(1 for _ in q.stream())


def claim_account_for_uid(db: firestore.Client, uid: str, ig_account_id: str) -> str:
    """Registra a conta IG sob a agência do uid. Garante unicidade + teto. Retorna o agency_id.

    Idempotente: reconectar uma conta que já é da própria agência é no-op (refresh de token segue).
    Estoura AccountAlreadyClaimed (outra agência) ou PlanLimitReached (teto).
    """
    acc = str(ig_account_id)
    if not acc:
        raise TenancyError("ig_account_id obrigatório")

    agency_id = get_or_create_agency(db, uid)
    owner = _account_owner(db, acc)
    if owner is not None:
        if owner == agency_id:
            # já é dessa agência — reconexão/refresh. RE-HABILITA se estava desabilitada (§4.62):
            # a reconexão é justamente como o cliente traz de volta uma conta que a agência desligou.
            db.collection(COLLECTION_ACCOUNT_REGISTRY).document(acc).set({"active": True}, merge=True)
            return agency_id
        raise AccountAlreadyClaimed(acc)

    ag = db.collection(COLLECTION_AGENCIES).document(agency_id).get()
    limit = (ag.to_dict() or {}).get("accounts_limit") if ag.exists else None
    if limit and _count_accounts(db, agency_id) >= int(limit):
        raise PlanLimitReached(str(limit))

    reg_ref = db.collection(COLLECTION_ACCOUNT_REGISTRY).document(acc)
    try:
        reg_ref.create({
            "instagram_account_id": acc, "agency_id": agency_id,
            "connected_by_uid": uid, "connected_at": firestore.SERVER_TIMESTAMP,
            "active": True,   # §4.62 — conta nasce habilitada; a agência pode desligar depois
        })
    except gexc.AlreadyExists:
        # corrida: alguém registrou entre o get e o create
        if _account_owner(db, acc) == agency_id:
            return agency_id
        raise AccountAlreadyClaimed(acc)
    return agency_id


def account_owner_info(db: firestore.Client, ig_account_id: str) -> dict | None:
    """Dono atual da conta: {agency_id, connected_by_uid} ou None (não registrada)."""
    snap = db.collection(COLLECTION_ACCOUNT_REGISTRY).document(str(ig_account_id)).get()
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    return {"agency_id": d.get("agency_id"), "connected_by_uid": d.get("connected_by_uid")}


def agency_name(db: firestore.Client, agency_id: str | None) -> str:
    """Nome da agência (pra mostrar 'sua conta está com a Agência X'). '' se não achar."""
    if not agency_id:
        return ""
    snap = db.collection(COLLECTION_AGENCIES).document(agency_id).get()
    return ((snap.to_dict() or {}).get("name") or "") if snap.exists else ""


def transfer_account(db: firestore.Client, uid: str, ig_account_id: str) -> dict | None:
    """TRANSFERE a conta pra a agência do `uid` (força), tirando-a da agência antiga (fresh start —
    os dados derivados da antiga ficam sob o uid dela; a nova re-analisa do zero). Sobrescreve o
    registro de posse. Retorna {old_agency_id, old_connected_by_uid} da antiga, ou None se já era
    desta agência / não tinha dono. Respeita o teto de plano da agência NOVA."""
    acc = str(ig_account_id)
    if not acc:
        raise TenancyError("ig_account_id obrigatório")
    new_agency = get_or_create_agency(db, uid)
    reg_ref = db.collection(COLLECTION_ACCOUNT_REGISTRY).document(acc)
    snap = reg_ref.get()
    old = snap.to_dict() if snap.exists else None
    old_agency_id = (old or {}).get("agency_id")
    old_uid = (old or {}).get("connected_by_uid")
    if old_agency_id == new_agency:
        return None   # já é desta agência
    ag = db.collection(COLLECTION_AGENCIES).document(new_agency).get()
    limit = (ag.to_dict() or {}).get("accounts_limit") if ag.exists else None
    if limit and _count_accounts(db, new_agency) >= int(limit):
        raise PlanLimitReached(str(limit))
    reg_ref.set({
        "instagram_account_id": acc, "agency_id": new_agency, "connected_by_uid": uid,
        "connected_at": firestore.SERVER_TIMESTAMP, "active": True,   # §4.62 — nasce habilitada
        "transferred_from": old_agency_id, "transferred_at": firestore.SERVER_TIMESTAMP,
    })
    return {"old_agency_id": old_agency_id, "old_connected_by_uid": old_uid} if old_agency_id else None


def remove_account_from_integration(db: firestore.Client, old_uid: str | None, ig_account_id: str) -> None:
    """Tira a conta IG do doc integrations/{old_uid} — a conexão saiu da agência antiga, então ela
    deixa de listar a conta como conectada (o painel dela mostra 'desconectada')."""
    if not old_uid:
        return
    ref = db.collection("integrations").document(old_uid)
    snap = ref.get()
    if not snap.exists:
        return
    accs = (snap.to_dict() or {}).get("instagram_accounts") or []
    kept = [a for a in accs if str(a.get("id")) != str(ig_account_id)]
    if len(kept) != len(accs):
        ref.update({"instagram_accounts": kept, "updated_at": firestore.SERVER_TIMESTAMP})
