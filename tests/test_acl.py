"""Leak tests: the whole point of this repo, in executable form.

These tests don't check happy paths. They try to make the system leak
documents to users who must not see them, and assert it cannot.
"""
import sys

sys.path.insert(0, "src")

from acl import Document, User, can_access, permission_filter
from store import InMemoryStore


def _corpus():
    return [
        Document(id="d1", text="payments roadmap", acl={"alice", "team-payments"}),
        Document(id="d2", text="search roadmap", acl={"bob", "team-search"}),
        Document(id="d3", text="holiday schedule", acl={"team-payments", "team-search"}),
        Document(id="d4", text="layoff notes", acl={"carol"}),
        Document(id="d5", text="orphan", acl=set()),
    ]


def test_user_cannot_see_others_docs():
    alice = User(id="alice", groups=frozenset({"team-payments"}))
    visible = {d.id for d in permission_filter(alice, _corpus())}
    assert visible == {"d1", "d3"}, f"alice saw wrong set: {visible}"


def test_group_membership_grants_access():
    dave = User(id="dave", groups=frozenset({"team-search"}))
    assert can_access(dave, _corpus()[1])  # d2 via team-search
    assert not can_access(dave, _corpus()[0])  # d1 is payments-only


def test_empty_acl_is_fail_closed():
    # A document with no ACL must reach NOBODY, not everybody.
    carol = User(id="carol", groups=frozenset({"exec"}))
    assert not can_access(carol, _corpus()[4])


def test_revoked_access_disappears():
    # Simulate group removal: user loses team-search, keeps nothing else.
    bob = User(id="bob", groups=frozenset())  # removed from team-search
    docs = _corpus()
    # d2's ACL still names bob directly, so it stays visible...
    assert can_access(bob, docs[1])
    # ...but a group-only doc must vanish once membership is gone.
    d3 = Document(id="d3x", text="x", acl={"team-search"})
    assert not can_access(bob, d3)


def test_store_enforces_before_ranking():
    store = InMemoryStore()
    for d in _corpus():
        store.add(d)
    mallory = User(id="mallory", groups=frozenset())
    hits = store.search(mallory, "roadmap layoff orphan", top_k=10)
    assert hits == [], f"mallory (no permissions) saw: {[h.id for h in hits]}"


def test_search_never_leaks_across_users():
    store = InMemoryStore()
    for d in _corpus():
        store.add(d)
    users = [
        User(id="alice", groups=frozenset({"team-payments"})),
        User(id="bob", groups=frozenset({"team-search"})),
        User(id="carol", groups=frozenset({"exec"})),
    ]
    for user in users:
        for hit in store.search(user, "roadmap", top_k=10):
            assert can_access(user, hit), f"LEAK: {user.id} retrieved {hit.id}"
