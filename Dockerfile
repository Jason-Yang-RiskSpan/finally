# syntax=docker/dockerfile:1.7

# ---- Stage 1: build the Next.js static export ----
FROM node:20-slim AS frontend-build

WORKDIR /build

# Lockfiles first so the npm install layer caches across source-only edits.
COPY frontend/package.json frontend/package-lock.json* frontend/npm-shrinkwrap.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Now bring in the rest of the frontend source and build the static export.
COPY frontend/ ./
RUN npm run build

# Next.js with `output: 'export'` writes the static export to ./out (Next 14+).
RUN set -eux; \
    if [ -d out ]; then \
        mv out /export; \
    elif [ -d .next/out ]; then \
        mv .next/out /export; \
    else \
        echo "ERROR: Next.js export directory not found (expected ./out)"; \
        ls -la; \
        exit 1; \
    fi


# ---- Stage 2: assemble the Python runtime image ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/root/.local/bin:${PATH}"

# System deps: curl is needed to install uv and to run a healthcheck from inside
# the container (we don't ship a separate healthcheck binary).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (official installer).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Lockfile + project metadata first so the dependency layer caches across source edits.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./

# Sync runtime deps from the lockfile (frozen = lockfile is the source of truth).
# We pass --no-install-project so this layer doesn't need the source code yet —
# the project itself is installed in a later step after sources are copied.
RUN uv sync --frozen --no-dev --no-install-project

# Backend application source.
COPY backend/app ./app
COPY backend/db ./db

# Install the project itself now that sources are present.
RUN uv sync --frozen --no-dev

# Copy the built static frontend from stage 1 into the path the backend serves from.
COPY --from=frontend-build /export ./static

# Runtime SQLite directory. NOTE: the backend's `db/` Python package occupies
# `/app/db`, so the persistent volume is mounted at `/app/data` instead.
# The backend should read FINALLY_DB_PATH (or default to /app/data/finally.db).
RUN mkdir -p /app/data
ENV FINALLY_DB_PATH=/app/data/finally.db

EXPOSE 8000

# Default env: simulator mode (no MASSIVE_API_KEY), real LLM unless overridden.
ENV LLM_MOCK=false

CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
