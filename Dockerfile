# Image unique pour l'API et le worker (même code, commande différente).
#
# Pas dans l'image, fourni au runtime :
#   - l'auth codex : bind-mount d'un dossier hôte → /home/app/.codex (comme x-med) ;
#   - la config et les secrets : variables d'environnement (cf. .env.example).

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Node 22 puis le CLI codex, ÉPINGLÉ : le format de `codex exec --json` est
# parsé par app/codex_cli.py, et les slugs de modèles gpt-5.6-* exigent une
# version récente. Version testée : 0.149.1.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @openai/codex@0.149.1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# uid 1001 = geekette sur l'hôte : le bind-mount de l'auth codex reste
# lisible/inscriptible des deux côtés.
RUN useradd -m -u 1001 app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8810

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8810"]
