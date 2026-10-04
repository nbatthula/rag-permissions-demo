"""Contract test: the ACL check must live in the SQL, not in Python.

This runs with no database. It pins the security contract of PgVectorStore:
forbidden rows are excluded by the WHERE clause, so they never leave
Postgres. If someone refactors search() and the ACL check slips out of the
SQL, this test fails.
"""
from rag_permissions.acl import Document, User
from rag_permissions.store import PgVectorStore


class FakeConnection:
    """Records queries instead of running them."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple | None = None):
        self.queries.append((sql, params or ()))
        return self

    def fetchall(self) -> list:
        return []

    def commit(self) -> None:
        pass


def _store_with_fake_conn() -> tuple[PgVectorStore, FakeConnection]:
    fake = FakeConnection()
    store = PgVectorStore.__new__(PgVectorStore)  # bypass __init__ (needs a DB)
    store._conn = fake
    store._embed = lambda text: [0.0] * 384
    return store, fake


def test_acl_check_lives_in_where_clause() -> None:
    store, fake = _store_with_fake_conn()
    user = User(id="alice", groups={"team-payments"})
    store.search(user, "roadmap", top_k=5)

    assert fake.queries, "search() issued no SQL at all"
    sql, params = fake.queries[-1]
    assert "acl &&" in sql, "ACL overlap check missing from WHERE clause"
    principals = params[0]
    assert "alice" in principals, "user id not passed as a query principal"
    assert "team-payments" in principals, "group not passed as a query principal"


def test_python_side_filter_is_still_applied() -> None:
    # Defense in depth: even if the DB returned a forbidden row, the
    # Python-side permission filter must drop it.
    store, _ = _store_with_fake_conn()

    class LeakyConn(FakeConnection):
        def fetchall(self) -> list:
            return [("d9", "secret doc", {"mallory"})]

    store._conn = LeakyConn()
    user = User(id="alice", groups={"team-payments"})
    assert store.search(user, "secret", top_k=5) == []


def test_user_groups_accept_plain_lists() -> None:
    user = User(id="alice", groups=["team-payments"])  # type: ignore[arg-type]
    assert user.groups == frozenset({"team-payments"})
    assert isinstance(user.groups, frozenset)


def test_document_without_embedding_is_fine() -> None:
    doc = Document(id="d", text="hello", acl={"alice"})
    assert doc.embedding is None
