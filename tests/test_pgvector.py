"""Integration tests against a real Postgres + pgvector.

Skipped unless DATABASE_URL is set. CI runs these against a pgvector
service container; locally, start one with:

    docker compose up -d
    DATABASE_URL=postgresql://postgres:demo@localhost:5432/postgres \\
        python -m pytest tests/ -q
"""
import os

import pytest

from rag_permissions.acl import Document, User, can_access
from rag_permissions.store import PgVectorStore

pytestmark = pytest.mark.integration


@pytest.fixture()
def store():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set")
    with PgVectorStore.connect(dsn) as s:
        s._conn.execute("TRUNCATE rag_docs")
        s._conn.commit()
        yield s


def _seed(store: PgVectorStore) -> None:
    store.add(Document(id="d1", text="payments roadmap", acl={"alice", "team-payments"}))
    store.add(Document(id="d2", text="search roadmap", acl={"bob", "team-search"}))
    store.add(Document(id="d3", text="holiday schedule", acl={"team-payments", "team-search"}))
    store.add(Document(id="d4", text="layoff notes", acl={"carol"}))
    store.add(Document(id="d5", text="orphan", acl=set()))


def test_pgvector_never_leaks_across_users(store: PgVectorStore) -> None:
    _seed(store)
    users = [
        User(id="alice", groups={"team-payments"}),
        User(id="bob", groups={"team-search"}),
        User(id="carol", groups={"exec"}),
        User(id="mallory", groups=set()),
    ]
    for user in users:
        for hit in store.search(user, "roadmap layoff", top_k=10):
            assert can_access(user, hit), f"LEAK: {user.id} retrieved {hit.id}"


def test_pgvector_user_sees_own_slice(store: PgVectorStore) -> None:
    _seed(store)
    alice = User(id="alice", groups={"team-payments"})
    visible = {d.id for d in store.search(alice, "roadmap", top_k=10)}
    assert visible <= {"d1", "d3"}
    assert "d4" not in visible and "d5" not in visible


def test_pgvector_empty_acl_reaches_nobody(store: PgVectorStore) -> None:
    _seed(store)
    carol = User(id="carol", groups={"exec"})
    visible = {d.id for d in store.search(carol, "orphan", top_k=10)}
    assert "d5" not in visible
