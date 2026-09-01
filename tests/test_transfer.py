"""§4.61 — transferência de conta entre agências (core.tenancy). Firestore fake (com update/delete)."""
import pytest
from google.api_core import exceptions as gexc

from core import tenancy


class _Snap:
    def __init__(self, key, data): self._key, self._d = key, data
    @property
    def exists(self): return self._d is not None
    def to_dict(self): return dict(self._d) if self._d is not None else None
    @property
    def id(self): return self._key


class _DocRef:
    def __init__(self, coll, key): self.coll, self.key = coll, key
    def get(self): return _Snap(self.key, self.coll.store.get(self.key))
    def set(self, data, merge=False):
        if merge and self.key in self.coll.store:
            self.coll.store[self.key].update(dict(data))
        else:
            self.coll.store[self.key] = dict(data)
    def create(self, data):
        if self.key in self.coll.store:
            raise gexc.AlreadyExists(self.key)
        self.coll.store[self.key] = dict(data)
    def update(self, data): self.coll.store.setdefault(self.key, {}).update(dict(data))
    def delete(self): self.coll.store.pop(self.key, None)


class _Query:
    def __init__(self, coll, filters): self.coll, self.filters = coll, filters
    def where(self, field, op, value): return _Query(self.coll, self.filters + [(field, op, value)])
    def stream(self):
        for k, v in list(self.coll.store.items()):
            if all(v.get(f) == val for (f, o, val) in self.filters if o == "=="):
                yield _Snap(k, v)


class _Coll:
    def __init__(self, store): self.store = store
    def document(self, key): return _DocRef(self, key)
    def where(self, field, op, value): return _Query(self, [(field, op, value)])


class _Batch:
    def __init__(self): self.ops = []
    def set(self, ref, data): self.ops.append((ref, data))
    def commit(self):
        for ref, data in self.ops: ref.set(data)


class _FakeDB:
    def __init__(self): self.colls = {}
    def collection(self, name): return self.colls.setdefault(name, _Coll({}))
    def batch(self): return _Batch()


@pytest.fixture
def db(): return _FakeDB()


def test_transferencia_move_posse_e_devolve_antiga(db):
    # u1 (agência A) conecta IG100; u2 tenta e é recusado; transfere pra u2.
    a1 = tenancy.claim_account_for_uid(db, "u1", "IG100")
    with pytest.raises(tenancy.AccountAlreadyClaimed):
        tenancy.claim_account_for_uid(db, "u2", "IG100")
    old = tenancy.transfer_account(db, "u2", "IG100")
    a2 = tenancy.resolve_agency_id(db, "u2")
    assert old and old["old_agency_id"] == a1 and old["old_connected_by_uid"] == "u1"
    assert tenancy._account_owner(db, "IG100") == a2 and a2 != a1   # posse agora é da nova


def test_transferencia_para_mesma_agencia_e_noop(db):
    tenancy.claim_account_for_uid(db, "u1", "IG100")
    assert tenancy.transfer_account(db, "u1", "IG100") is None   # já é dessa agência


def test_transferencia_respeita_teto_da_agencia_nova(db):
    # u2 (free, teto 1) já tem uma conta → não pode receber a transferência de outra
    tenancy.claim_account_for_uid(db, "u1", "IG100")
    tenancy.claim_account_for_uid(db, "u2", "IG200")   # free teto 1, ok
    with pytest.raises(tenancy.PlanLimitReached):
        tenancy.transfer_account(db, "u2", "IG100")
    assert tenancy._account_owner(db, "IG100") == tenancy.resolve_agency_id(db, "u1")   # não moveu


def test_account_owner_info(db):
    a1 = tenancy.claim_account_for_uid(db, "u1", "IG100")
    info = tenancy.account_owner_info(db, "IG100")
    assert info == {"agency_id": a1, "connected_by_uid": "u1"}
    assert tenancy.account_owner_info(db, "IG_INEXISTENTE") is None


def test_agency_name(db):
    aid = "ag-x"
    db.collection(tenancy.COLLECTION_AGENCIES).document(aid).set({"agency_id": aid, "name": "Studio X"})
    assert tenancy.agency_name(db, aid) == "Studio X"
    assert tenancy.agency_name(db, None) == ""
    assert tenancy.agency_name(db, "nao-existe") == ""


def test_remove_account_from_integration(db):
    db.collection("integrations").document("u1").set({"instagram_accounts": [
        {"id": "IG100", "username": "@a"}, {"id": "IG200", "username": "@b"}]})
    tenancy.remove_account_from_integration(db, "u1", "IG100")
    accs = db.collection("integrations").document("u1").get().to_dict()["instagram_accounts"]
    assert [a["id"] for a in accs] == ["IG200"]
    # idempotente / sem doc não quebra
    tenancy.remove_account_from_integration(db, "u1", "IG100")
    tenancy.remove_account_from_integration(db, "sem-doc", "IG100")
