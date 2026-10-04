"""Runnable story: same query, three users, three different slices.

    pip install -e .
    python examples/demo.py [--backend pgvector]   # pgvector needs DATABASE_URL
"""
from __future__ import annotations

import argparse

from rag_permissions.acl import Document, User
from rag_permissions.store import InMemoryStore, PgVectorStore


def seed(store: InMemoryStore | PgVectorStore) -> None:
    store.add(
        Document(id="d1", text="Q3 roadmap for the payments team",
                 acl={"alice", "team-payments"})
    )
    store.add(
        Document(id="d2", text="Q3 roadmap for the search team",
                 acl={"bob", "team-search"})
    )
    store.add(
        Document(id="d3", text="Company holiday schedule",
                 acl={"team-payments", "team-search"})
    )
    store.add(Document(id="d4", text="Draft layoff planning notes", acl={"carol"}))
    store.add(Document(id="d5", text="Orphaned doc with no ACL", acl=set()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["memory", "pgvector"], default="memory")
    args = parser.parse_args()

    store: InMemoryStore | PgVectorStore = (
        PgVectorStore.connect() if args.backend == "pgvector" else InMemoryStore()
    )
    try:
        seed(store)

        users = [
            User(id="alice", groups=frozenset({"team-payments"})),
            User(id="bob", groups=frozenset({"team-search"})),
            User(id="carol", groups=frozenset({"exec"})),
        ]
        for user in users:
            hits = store.search(user, "roadmap", top_k=10)
            print(f"\n{user.id} sees:")
            for hit in hits:
                print(f"  - {hit.id}: {hit.text}")
            leaked = [h.id for h in hits if h.id == "d4" and user.id != "carol"]
            assert not leaked, f"LEAK: {user.id} saw {leaked}"
        print("\nNo leaks. d5 (empty ACL) reached nobody. That is the whole demo.")
    finally:
        if isinstance(store, PgVectorStore):
            store.close()


if __name__ == "__main__":
    main()
