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

## How it works

```
                        ┌─────────────────────────────┐
  query + user ────────▶│ 1. PERMISSION FILTER FIRST  │──▶ forbidden docs never
                        │    WHERE acl && principals  │    leave the database
                        └──────────────┬──────────────┘
                                       │ allowed docs only
                                       ▼
                        ┌─────────────────────────────┐
                        │ 2. RANK within the allowed  │──▶ top-k the user
                        │    set (vector similarity)  │    may actually see
                        └─────────────────────────────┘
```

Post-filtering (rank first, hide forbidden docs after) is the common
mistake: ranking scores leak information about documents the user must not
know exist, and you pay to rank documents you will discard.

## Quickstart

```bash
pip install -e .
python examples/demo.py
```

`demo.py` seeds a small corpus where different documents belong to different
users and groups, then runs the same query as three different users and shows
each one only ever sees their own slice.

To run against real pgvector instead of the in-memory store:

```bash
docker compose up -d
export DATABASE_URL=postgresql://postgres:demo@localhost:5432/postgres
pip install -e ".[pgvector]"
python examples/demo.py --backend pgvector
```

Note: the pgvector path uses a clearly-labeled demo-only pseudo-embedder
(`insecure_demo_embed`) so it runs without an embedding model or API key.
It carries no semantic meaning; swap in a real embedding model for serious use.
The permission logic is identical either way, which is the point.

## Layout

- `src/rag_permissions/acl.py` — the permission model: documents, users,
  groups, and the retrieval-time enforcement function. This is the heart of
  the demo.
- `src/rag_permissions/scoring.py` — relevance scoring, deliberately separated
  from permission logic. Swap the scorer without touching permissions.
- `src/rag_permissions/store.py` — vector stores with identical permission
  semantics: an in-memory backend for the demo and a pgvector backend that
  pushes the ACL check into the SQL `WHERE` clause (with a GIN index so the
  check stays fast). Constructors do no I/O; use `PgVectorStore.connect()`.
- `examples/demo.py` — the runnable story: seed, query as three users, show
  the slices.
- `tests/test_acl.py` — leak tests. The whole point in executable form.

## Roadmap

- [x] CI gate: the build fails if any leak test fails (`.github/workflows/ci.yml`)
- [ ] Weaviate backend alongside pgvector
- [ ] Group-membership change propagation (stale permission windows)
- [ ] Latency comparison: pre-filter vs post-filter at 1M chunks

## Companion reading

Blog post: *RAG is easy until permissions matter* (link when published).
Talk: MLOps World 2026, AI+IM Global Summit 2027 (proposed).

## License

MIT. See [LICENSE](LICENSE).
