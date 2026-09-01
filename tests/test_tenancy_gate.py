"""Portão multi-tenant no ponto de conexão (WS2) — com Firestore fake.

Cobre o contrato que a rota depende: unicidade global (uma conta, uma agência), teto de plano,
e a auto-provisão de agência pra tester legado. `.create()` levanta AlreadyExists (a trava).
Espelha o fake do proof-platform (tests/test_tenancy.py) — os dois repos compartilham o formato.
"""
import pytest
from google.api_core import exceptions as gexc

from core import tenancy


# --------------------------------------------------------------------------- fake Firestore

class _Snap:
    def __init__(self, key, data):
        self._key, self._d = key, data
    @property
    def exists(self):
        return self._d is not None
    def to_dict(self):
        return dict(self._d) if self._d is not None else None
    @property
    def id(self):
        return self._key


class _DocRef:
    def __init__(self, coll, key):
        self.coll, self.key = coll, key
    def get(self):
        return _Snap(self.key, self.coll.store.get(self.key))
    def set(self, data, merge=False):
        if merge and self.key in self.coll.store:
            self.coll.store[self.key].update(dict(data))
        else:
            self.coll.store[self.key] = dict(data)
    def create(self, data):
        if self.key in self.coll.store:
            raise gexc.AlreadyExists(self.key)
        self.coll.store[self.key] = dict(data)


class _Query:
    def __init__(self, coll, filters):
        self.coll, self.filters = coll, filters
    def where(self, field, op, value):
        return _Query(self.coll, self.filters + [(field, op, value)])
    def stream(self):
        for k, v in list(self.coll.store.items()):
            if all(v.get(f) == val for (f, o, val) in self.filters if o == "=="):
                yield _Snap(k, v)


class _Coll:
    def __init__(self, store):
        self.store = store
    def document(self, key):
        return _DocRef(self, key)
    def where(self, field, op, value):
        return _Query(self, [(field, op, value)])


class _Batch:
    def __init__(self):
        self.ops = []
    def set(self, ref, data):
        self.ops.append((ref, data))
    def commit(self):
        for ref, data in self.ops:
            ref.set(data)


class _FakeDB:
    def __init__(self):
        self.colls = {}
    def collection(self, name):
        return self.colls.setdefault(name, _Coll({}))
    def batch(self):
        return _Batch()


@pytest.fixture
def db():
    return _FakeDB()


# --------------------------------------------------------------------------- casos

def test_primeira_conexao_provisiona_agencia_e_registra(db):
    agency_id = tenancy.claim_account_for_uid(db, "u1", "IG100")
    assert agency_id  # agência criada na hora (tester sem cadastro)
    assert tenancy.resolve_agency_id(db, "u1") == agency_id
    assert tenancy._account_owner(db, "IG100") == agency_id


def test_reconexao_mesma_conta_e_noop(db):
    a = tenancy.claim_account_for_uid(db, "u1", "IG100")
    a2 = tenancy.claim_account_for_uid(db, "u1", "IG100")  # refresh de token
    assert a == a2


def test_conta_de_outro_uid_e_recusada(db):
    tenancy.claim_account_for_uid(db, "u1", "IG100")
    with pytest.raises(tenancy.AccountAlreadyClaimed):
        tenancy.claim_account_for_uid(db, "u2", "IG100")


def test_teto_free_bloqueia_segunda_conta(db):
    tenancy.claim_account_for_uid(db, "u1", "IG1")   # free → teto 1
    with pytest.raises(tenancy.PlanLimitReached):
        tenancy.claim_account_for_uid(db, "u1", "IG2")


def test_agencia_com_teto_maior_conecta_varias(db):
    # simula agência já cadastrada com plano start (teto 3)
    aid = "ag-start"
    db.collection(tenancy.COLLECTION_AGENCIES).document(aid).set({
        "agency_id": aid, "owner_uid": "u9", "plan": "start", "accounts_limit": 3,
    })
    db.collection(tenancy.COLLECTION_AGENCY_MEMBERS).document(f"{aid}_u9").set({
        "agency_id": aid, "uid": "u9", "role": "owner",
    })
    for ig in ("IG1", "IG2", "IG3"):
        tenancy.claim_account_for_uid(db, "u9", ig)
    assert tenancy._count_accounts(db, aid) == 3
    with pytest.raises(tenancy.PlanLimitReached):
        tenancy.claim_account_for_uid(db, "u9", "IG4")
