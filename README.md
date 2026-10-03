# RAG Permissions Demo

Minimal, honest demonstration of the core idea from the talk
**"RAG is easy until permissions matter: enterprise search that respects every ACL."**

The point: enforce access control **at retrieval time**, not as a post-filter.
If a user cannot see a document, it must never enter the retrieval pipeline at all.

## The three patterns this demo shows

1. **ACLs travel with the vectors.** Every chunk carries its access control list
   as metadata at index time. No ACL on the chunk, no retrieval of the chunk.
2. **Permission check before ranking.** The candidate set is permission-filtered
   *before* similarity ranking, so ranking can never surface what the user
   may not see. (Post-filtering leaks via ranking scores and is slower.)
3. **Leak tests, not just happy-path tests.** `tests/test_acl.py` proves that
   users cannot reach documents outside their permissions, including edge cases:
   group membership changes, revoked access, and documents with empty ACLs.

## Quickstart

```bash
pip install -r requirements.txt
python src/demo.py
```

`demo.py` seeds a small corpus where different documents belong to different
users and groups, then runs the same query as three different users and shows
each one only ever sees their own slice.

To run against real pgvector instead of the in-memory store:

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=demo pgvector/pgvector:pg16
export DATABASE_URL=postgresql://postgres:demo@localhost:5432/postgres
python src/demo.py --backend pgvector
```

## Layout

- `src/acl.py` — the permission model: documents, users, groups, and the
  retrieval-time enforcement function. This is the heart of the demo.
- `src/store.py` — vector store with an in-memory backend for the demo and a
  pgvector backend for real runs. Both enforce ACLs identically.
- `src/demo.py` — the runnable story: seed, query as three users, show the slices.
- `tests/test_acl.py` — leak tests. The whole point in executable form.

## Roadmap

- [ ] Weaviate backend alongside pgvector
- [ ] Group-membership change propagation (stale permission windows)
- [ ] Latency comparison: pre-filter vs post-filter at 1M chunks
- [x] CI gate: the build fails if any leak test fails (`.github/workflows/ci.yml`)

## Companion reading

Blog post: *RAG is easy until permissions matter* (link when published).
Talk: MLOps World 2026, AI+IM Global Summit 2027 (proposed).
