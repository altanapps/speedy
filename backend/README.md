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

## Status

Bare scaffold. Subsequent PRs add:

- Polymarket Gamma client + nightly + 5-min refresh job (PR 4)
- pgvector schema + OpenAI embedding pipeline (PR 4)
- `/search` endpoint with confidence threshold (PR 5)
