# Backend — Speedy retrieval service

Python + FastAPI + Postgres+pgvector. Hosts the Polymarket market index and the `/search` endpoint.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

## Test

```bash
pytest
ruff check .
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
