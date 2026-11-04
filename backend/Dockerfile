FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /srv

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
RUN useradd --system --uid 10001 happly && chown -R happly /srv
USER happly

# Dans le conteneur, l'API écoute sur toutes les interfaces ; l'exposition reste limitée
# à 127.0.0.1 côté machine par docker-compose.yml (ADR-0008).
CMD ["/srv/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
