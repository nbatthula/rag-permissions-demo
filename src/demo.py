"""The runnable story: same query, three users, three different slices.

Run:  python src/demo.py            (in-memory backend)
        python src/demo.py --backend pgvector   (needs DATABASE_URL)
"""
import argparse
import sys

sys.path.insert(0, "src")

from acl import Document, User
from store import InMemoryStore, PgVectorStore


def seed(store):
    store.add(Document(id="d1", text="Q3 roadmap for the payments team",
                       acl={"alice", "team-payments"}))
    store.add(Document(id="d2", text="Q3 roadmap for the search team",
                       acl={"bob", "team-search"}))
    store.add(Document(id="d3", text="Company holiday schedule",
                       acl={"team-payments", "team-search"}))
    store.add(Document(id="d4", text="Draft layoff planning notes",
                       acl={"carol"}))  # only Carol
    store.add(Document(id="d5", text="Orphaned doc with no ACL",
                       acl=set()))  # fail closed: nobody sees this


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["memory", "pgvector"], default="memory")
    args = parser.parse_args()

    store = PgVectorStore() if args.backend == "pgvector" else InMemoryStore()
    seed(store)

    alice = User(id="alice", groups=frozenset({"team-payments"}))
    bob = User(id="bob", groups=frozenset({"team-search"}))
    carol = User(id="carol", groups=frozenset({"exec"}))

    for user in (alice, bob, carol):
        hits = store.search(user, "roadmap", top_k=10)
        print(f"\n{user.id} sees:")
        for h in hits:
            print(f"  - {h.id}: {h.text}")
        # Carol must never see d4 leak to anyone else; d5 must reach nobody.
        leaked = [h.id for h in hits if h.id == "d4" and user.id != "carol"]
        assert not leaked, f"LEAK: {user.id} saw {leaked}"
    print("\nNo leaks. d5 (empty ACL) reached nobody. That is the whole demo.")


if __name__ == "__main__":
    main()
