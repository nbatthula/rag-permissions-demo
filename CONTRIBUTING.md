# Contributing

Small, focused repo. A few ground rules:

## Running the checks

```bash
pip install -e ".[test]"
ruff check src tests examples
python -m pytest tests/ -q
```

The pgvector integration tests are skipped unless `DATABASE_URL` is set:

```bash
docker compose up -d
DATABASE_URL=postgresql://postgres:demo@localhost:5432/postgres python -m pytest tests/ -q
```

## What every PR needs

- **Leak tests for permission changes.** If you touch `acl.py` or the
  permission path in `store.py`, add or update an adversarial test in
  `tests/test_acl.py` that tries to make the system leak and asserts it
  cannot. The no-DB contract test in `tests/test_sql_contract.py` pins that
  the ACL check stays in the SQL `WHERE` clause.
- **Ruff-clean.** CI runs `ruff check src tests examples`.
- **No company data.** Examples stay synthetic.

## Design notes

- Permission enforcement happens *before* ranking, never after. Keep it that way.
- `PgVectorStore` constructors do no I/O; use `PgVectorStore.connect()`.
- The demo embedder (`insecure_demo_embed`) is intentionally labeled: it is a
  stand-in so the pgvector path runs without an API key, not a real embedder.
