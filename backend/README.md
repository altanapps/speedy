# Backend — Speedy retrieval service

Python + FastAPI + Postgres+pgvector. Hosts the Polymarket market index and the `/search` endpoint.

## Run locally

The Makefile drives a brew-native postgres + pgvector setup — no Docker required.

```bash
cd backend
make setup                       # brew installs postgres@17 + pgvector, creates the speedy db, runs migrations
make set-keys                    # interactive: stores OpenAI / Anthropic / Polymarket keys in macOS Keychain
make refresh                     # one cycle: pulls active Polymarket markets + embeds them (~5–15 min the first time)
make serve                       # uvicorn on :8000 — leave running
```

Secrets live in macOS Keychain under the service name `speedy`. Inspect with `make show-keys` (never prints values), wipe with `make clear-keys`. `.env` still works as an override for CI / Docker / one-off runs — env wins over Keychain when both are set.

`make doctor` prints a one-screen diagnostic if anything goes wrong (postgres not running, venv missing, no API key, etc.).

### LLM rerank (recommended)

`/search` runs in two modes:

- **Embedding-only** (default if `ANTHROPIC_API_KEY` is unset): pgvector top-1 with a cosine-similarity threshold gate. Threshold tunable via `SPEEDY_SEARCH_THRESHOLD` (default `0.55`).
- **Embedding + rerank** (when `ANTHROPIC_API_KEY` is set): pgvector top-10 → `claude-haiku-4-5` disambiguator → top-1. Bypasses the cosine threshold; trusts the reranker's "none of these is good" judgment. Cost: ~$0.001 per search.

Run `make set-keys` and paste an Anthropic key when prompted (or skip to leave embedding-only). PRD §6.3 v0.2 retrieval path; biggest expected gain on ambiguous queries (*"Powell"* → which Powell?).

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
