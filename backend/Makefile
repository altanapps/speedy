.PHONY: help setup db venv install migrate refresh serve doctor set-keys show-keys clear-keys

# Source .env if it exists so OPENAI_API_KEY (and any overrides) carry across
# shells without the user re-exporting them.
ifneq (,$(wildcard .env))
include .env
export
endif

POSTGRES_FORMULA := postgresql@17
PGVECTOR_FORMULA := pgvector
PYTHON ?= python3.14
VENV := .venv
DB_NAME := speedy
DB_USER := speedy
DB_PASSWORD := speedy
DB_PORT := 5432
# Honor an explicit DATABASE_URL (e.g. from .env); otherwise default to local.
DATABASE_URL ?= postgresql+asyncpg://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_NAME)

help:  ## Print this help
	@awk 'BEGIN{FS=":.*##"; printf "\n  make \033[36m<target>\033[0m\n\n"} /^[a-z_-]+:.*##/{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: db venv install migrate env  ## One-shot first-time setup (everything below)
	@echo
	@echo "✓ Setup complete. Next:"
	@echo "    make set-keys       # store API + Polymarket keys in macOS Keychain"
	@echo "    make refresh        # populate the index (~5–15 min)"
	@echo "    make serve          # start the API on :8000"

env:  ## Create a .env from .env.example if absent (optional — Keychain is preferred)
	@if [ ! -f .env ]; then cp .env.example .env && echo "✓ created .env (Keychain via 'make set-keys' is preferred for secrets)"; else echo "✓ .env present"; fi

db:  ## Install postgres + pgvector via brew, create the speedy database
	@command -v brew >/dev/null 2>&1 || { echo "Homebrew is required: https://brew.sh"; exit 1; }
	@brew list --formula | grep -q '^$(POSTGRES_FORMULA)$$' || brew install $(POSTGRES_FORMULA)
	@brew list --formula | grep -q '^$(PGVECTOR_FORMULA)$$' || brew install $(PGVECTOR_FORMULA)
	@brew services start $(POSTGRES_FORMULA) >/dev/null
	@sleep 2
	@PG_BIN=$$(brew --prefix $(POSTGRES_FORMULA))/bin; \
	  if ! "$$PG_BIN/psql" -U $$USER -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$(DB_USER)'" | grep -q 1; then \
	    "$$PG_BIN/psql" -U $$USER -d postgres -c "CREATE ROLE $(DB_USER) LOGIN PASSWORD '$(DB_PASSWORD)' SUPERUSER"; \
	  fi; \
	  if ! "$$PG_BIN/psql" -U $$USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$(DB_NAME)'" | grep -q 1; then \
	    "$$PG_BIN/psql" -U $$USER -d postgres -c "CREATE DATABASE $(DB_NAME) OWNER $(DB_USER)"; \
	  fi
	@echo "✓ postgres + pgvector ready ($(DB_NAME) database, role $(DB_USER))"

venv:  ## Create the Python venv
	@if [ ! -d "$(VENV)" ]; then $(PYTHON) -m venv $(VENV); fi
	@echo "✓ venv at $(VENV)"

install: venv  ## Install backend dependencies into the venv
	@. $(VENV)/bin/activate && pip install --quiet --upgrade pip && pip install --quiet -e ".[dev]"
	@echo "✓ deps installed"

migrate:  ## Apply alembic migrations
	@. $(VENV)/bin/activate && DATABASE_URL=$(DATABASE_URL) alembic upgrade head
	@echo "✓ schema up to date"

refresh:  ## Pull active Polymarket markets + embed (needs OPENAI_API_KEY in Keychain or env)
	@. $(VENV)/bin/activate && DATABASE_URL=$(DATABASE_URL) speedy-refresh

serve:  ## Run uvicorn on :8000
	@. $(VENV)/bin/activate && DATABASE_URL=$(DATABASE_URL) uvicorn app.main:app --reload --port 8000

set-keys:  ## Store OpenAI / Anthropic / Polymarket keys in macOS Keychain
	@. $(VENV)/bin/activate && speedy-keys set

show-keys:  ## Show which Speedy keys are present in Keychain (no values)
	@. $(VENV)/bin/activate && speedy-keys show

clear-keys:  ## Delete all Speedy entries from Keychain
	@. $(VENV)/bin/activate && speedy-keys clear

doctor:  ## Print diagnostic info — useful when something's not working
	@echo "macOS:           $$(sw_vers -productVersion)"
	@echo "Homebrew:        $$(brew --version | head -n1)"
	@echo "Python ($(PYTHON)): $$(command -v $(PYTHON) && $(PYTHON) --version)"
	@echo "venv present:    $$([ -d $(VENV) ] && echo yes || echo no)"
	@echo "postgres@16:     $$(brew list --formula | grep -q '^$(POSTGRES_FORMULA)$$' && echo installed || echo MISSING)"
	@echo "pgvector:        $$(brew list --formula | grep -q '^$(PGVECTOR_FORMULA)$$' && echo installed || echo MISSING)"
	@echo "service running: $$(brew services list | awk '$$1=="$(POSTGRES_FORMULA)"{print $$2}')"
	@PG_BIN=$$(brew --prefix $(POSTGRES_FORMULA) 2>/dev/null)/bin; \
	  if [ -x "$$PG_BIN/psql" ]; then \
	    echo "speedy db:       $$("$$PG_BIN/psql" -U $$USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$(DB_NAME)'" 2>/dev/null | grep -q 1 && echo present || echo MISSING)"; \
	  fi
	@echo "secrets:"
	@if [ -n "$$OPENAI_API_KEY" ]; then echo "  OPENAI_API_KEY  set (env)"; fi
	@if [ -d $(VENV) ]; then \
	  . $(VENV)/bin/activate && speedy-keys show 2>/dev/null | sed 's/^/  /' || true; \
	else \
	  echo "  (run 'make install' to enable Keychain check)"; \
	fi
