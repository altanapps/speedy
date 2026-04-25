# Backend — Speedy retrieval service

Python + FastAPI + Postgres+pgvector. Hosts the Polymarket market index and the `/search` endpoint.

## Run locally

```bash
cd backend

# 1. Start Postgres + pgvector via docker-compose
docker compose up -d

# 2. Set up the Python env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Apply migrations
export DATABASE_URL=postgresql+asyncpg://speedy:speedy@localhost:5432/speedy
alembic upgrade head

# 4. Run the server
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

## Test

```bash
export DATABASE_URL=postgresql+asyncpg://speedy:speedy@localhost:5432/speedy
alembic upgrade head
pytest
ruff check .
```

DB-touching tests are skipped automatically when `DATABASE_URL` is unset.

## Migrations

```bash
alembic revision -m "describe what changed"   # generate a new migration stub
alembic upgrade head                            # apply migrations
alembic downgrade -1                            # roll one back
```

## Deploy (Railway)

`railway.json` is checked in. After `railway login`:

```bash
railway link        # first time only, links this directory to a Railway project
railway up          # builds via Dockerfile, deploys, returns a URL
```

Health check on `/health` is wired into the Railway config; failed deploys auto-rollback.

## Refresh job

Speedy's index is filled by polling the Polymarket Gamma API. One refresh cycle:

1. Page through `gamma-api.polymarket.com/markets?active=true&closed=false`.
2. Upsert every market by id (slug, question, description, end date, category, tags).
3. Compute a `source_hash` over the embedding inputs; for any market whose hash changed (or that has no embedding yet), call OpenAI `text-embedding-3-small` and store the vector + new hash atomically.
4. Mark anything not seen this cycle as `active = false`.

`source_hash` lives alongside the embedding (not the metadata), so a half-finished cycle reruns cleanly: a row whose hash is current but whose embed write was rolled back will get re-embedded on the next pass.

Run it:

```bash
export OPENAI_API_KEY=sk-...
export DATABASE_URL=postgresql+asyncpg://speedy:speedy@localhost:5432/speedy
speedy-refresh           # one cycle
speedy-refresh --loop    # forever, 5-min sleeps
```

Or run it inside the API process by setting `SPEEDY_RUN_REFRESH=1` — the FastAPI lifespan starts a background task on boot and cancels it cleanly on shutdown. Fine for one Railway replica; if you scale out, move it to its own service.

## Search

`POST /search` — top-1 semantic match against active markets.

```
POST /search
{
  "highlight": "Powell signaled patience on rate cuts",
  "surrounding_context": "...optional context from the page...",
  "page_title": "FT.com — Fed minutes"
}

200 OK
{
  "match": {
    "id": "...",
    "slug": "...",
    "question": "...",
    "description": "...",
    "end_date": "2026-05-07T20:00:00Z",
    "category": "Macro",
    "tags": ["fed"]
  },
  "score": 0.71,
  "threshold": 0.55
}
```

If no active market clears the threshold, the response is `{"match": null, "score": null, "threshold": ...}` — the overlay's job to render the "no tradeable market" UX.

The threshold is cosine similarity (range `[-1, 1]`); configure via `SPEEDY_SEARCH_THRESHOLD` (default `0.55`). Tune against the `eval/` set once it has fixtures.

## Status

Subsequent PRs add:

- LLM rerank (Haiku) over the top-N pgvector candidates (v0.2)
