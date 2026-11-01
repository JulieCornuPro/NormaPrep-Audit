# Image unique : l'API (FastAPI) sert aussi l'interface web compilée.

# ---- 1. Interface web ---------------------------------------------------------
FROM node:22-alpine AS interface
WORKDIR /interface
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. API -------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 1000 npa \
    && mkdir -p /var/lib/npa && chown npa:npa /var/lib/npa && chmod 700 /var/lib/npa
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Droit d'exécution explicite : il peut se perdre lors d'un clone sous Windows.
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh
COPY --from=interface /interface/dist /app/interface

USER npa
EXPOSE 8000

# Prépare les clés, applique les migrations, puis lance la commande (l'API par défaut).
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
