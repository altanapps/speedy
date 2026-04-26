# Backend — Speedy retrieval service

Python + FastAPI + Postgres+pgvector. Hosts the Polymarket market index and the `/search` endpoint.

## Run locally

The Makefile drives a brew-native postgres + pgvector setup — no Docker required.

```bash
cd backend
make setup                       # brew installs postgres@17 + pgvector, creates the speedy db, runs migrations, creates .env
# edit .env and set OPENAI_API_KEY=sk-...
make refresh                     # one cycle: pulls active Polymarket markets + embeds them (~5–15 min the first time)
make serve                       # uvicorn on :8000 — leave running
```

The Makefile auto-sources `backend/.env` (gitignored) for `OPENAI_API_KEY`, optional `DATABASE_URL`, and `SPEEDY_SEARCH_THRESHOLD`. See `.env.example`.

`make doctor` prints a one-screen diagnostic if anything goes wrong (postgres not running, venv missing, no API key, etc.).

Health check:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

## Test

```bash
. .venv/bin/activate
DATABASE_URL=postgresql+asyncpg://speedy:speedy@localhost:5432/speedy pytest
ruff check .
```

DB-touching tests are skipped automatically when `DATABASE_URL` is unset.

## Migrations

```bash
. .venv/bin/activate
alembic revision -m "describe what changed"   # generate a new migration stub
alembic upgrade head                            # apply migrations (or `make migrate`)
alembic downgrade -1                            # roll one back
```

## Refresh job

Speedy's index is filled by polling the Polymarket Gamma API. One refresh cycle:

1. Page through `gamma-api.polymarket.com/markets?active=true&closed=false`.
2. Upsert every market by id (slug, question, description, end date, category, tags).
3. Compute a `source_hash` over the embedding inputs; for any market whose hash changed (or that has no embedding yet), call OpenAI `text-embedding-3-small` and store the vector + new hash atomically.
4. Mark anything not seen this cycle as `active = false`.

`source_hash` lives alongside the embedding (not the metadata), so a half-finished cycle reruns cleanly: a row whose hash is current but whose embed write was rolled back will get re-embedded on the next pass.

`make refresh` is one cycle. To loop it forever (5-min sleeps):

```bash
. .venv/bin/activate
DATABASE_URL=… speedy-refresh --loop
```

Or run it inside the API process by setting `SPEEDY_RUN_REFRESH=1` — the FastAPI lifespan starts a background task on boot and cancels it cleanly on shutdown.

## Deploy (Railway, optional)

Self-hosted-on-each-machine is the v0.1 default, but `railway.json` is checked in for when you want a shared instance. After `railway login`:

```bash
railway link        # first time only
railway up          # builds via Dockerfile, deploys, returns a URL
```

Health check on `/health` is wired into the Railway config; failed deploys auto-rollback.
