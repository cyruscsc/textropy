# syntax=docker/dockerfile:1

# --- Builder: resolve and install dependencies into a self-contained .venv --------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependency layer: cached until pyproject.toml / uv.lock actually change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Bake the HF weights into the image so container start does not depend on the network.
# Comment this out to keep the image small and accept a slow, network-dependent first run.
ENV HF_HOME=/opt/hf
RUN --mount=type=cache,target=/root/.cache/uv \
    .venv/bin/python -c "\
from transformers import AutoModelForCausalLM, AutoTokenizer, \
    AutoModelForSequenceClassification; \
from sentence_transformers import SentenceTransformer; \
AutoTokenizer.from_pretrained('distilgpt2'); \
AutoModelForCausalLM.from_pretrained('distilgpt2'); \
AutoTokenizer.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
AutoModelForSequenceClassification.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# --- Runtime ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1

WORKDIR /app

RUN useradd --create-home --uid 10001 textropy

COPY --from=builder --chown=textropy:textropy /app/.venv /app/.venv
COPY --from=builder --chown=textropy:textropy /opt/hf /opt/hf
COPY --chown=textropy:textropy app ./app

USER textropy
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys,json; \
r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')); \
sys.exit(0 if r['ready'] else 1)"

# Single worker by default: each worker holds its own copy of the models (spec §9), so
# scaling workers multiplies RAM. Prefer async concurrency over worker count here.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "1", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
