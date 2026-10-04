"""Leak tests: the whole point of this repo, in executable form.

These tests don't check happy paths. They try to make the system leak
documents to users who must not see them, and assert it cannot.
"""
from rag_permissions.acl import Document, User, can_access, permission_filter
from rag_permissions.store import InMemoryStore


def _corpus() -> list[Document]:
    return [
        Document(id="d1", text="payments roadmap", acl={"alice", "team-payments"}),
        Document(id="d2", text="search roadmap", acl={"bob", "team-search"}),
        Document(id="d3", text="holiday schedule", acl={"team-payments", "team-search"}),
        Document(id="d4", text="layoff notes", acl={"carol"}),
        Document(id="d5", text="orphan", acl=set()),
    ]


def test_user_sees_only_their_slice() -> None:
    alice = User(id="alice", groups=frozenset({"team-payments"}))
    visible = {d.id for d in permission_filter(alice, _corpus())}
    assert visible == {"d1", "d3"}


def test_group_membership_grants_access() -> None:
    dave = User(id="dave", groups=frozenset({"team-search"}))
    docs = _corpus()
    assert can_access(dave, docs[1])  # d2 via team-search
    assert not can_access(dave, docs[0])  # d1 is payments-only


def test_empty_acl_is_fail_closed() -> None:
    # A document with no ACL must reach NOBODY, not everybody.
    carol = User(id="carol", groups=frozenset({"exec"}))
    assert not can_access(carol, _corpus()[4])


def test_revoked_group_membership_removes_access() -> None:
    bob = User(id="bob", groups=frozenset({"team-search"}))
    doc = Document(id="d", text="search roadmap", acl={"team-search"})
    assert can_access(bob, doc)
    bob_removed = User(id="bob", groups=frozenset())  # dropped from team-search
    assert not can_access(bob_removed, doc)


def test_store_never_surfaces_forbidden_docs() -> None:
    store = InMemoryStore()
    for doc in _corpus():
        store.add(doc)
    mallory = User(id="mallory", groups=frozenset())  # no permissions at all
    assert store.search(mallory, "roadmap layoff orphan", top_k=10) == []


def test_every_search_hit_passes_can_access() -> None:
    store = InMemoryStore()
    for doc in _corpus():
        store.add(doc)
    users = [
        User(id="alice", groups=frozenset({"team-payments"})),
        User(id="bob", groups=frozenset({"team-search"})),
        User(id="carol", groups=frozenset({"exec"})),
    ]
    for user in users:
        for hit in store.search(user, "roadmap", top_k=10):
            assert can_access(user, hit), f"LEAK: {user.id} retrieved {hit.id}"
