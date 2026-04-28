FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Default CMD for `docker run` locally. Railway overrides this via the
# `startCommand` in railway.json so `alembic upgrade head` runs before uvicorn.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
