# syntax=docker/dockerfile:1

# --- Builder: resolve and install dependencies into a self-contained .venv --------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependency layer: cached until pyproject.toml / uv.lock actually change.
# --extra coref installs fastcoref, without which the Tier 2 `coreference` feature reports
# itself unavailable at runtime. The lock already resolves transformers to 4.57.x, which
# satisfies the extra's `transformers<5` bound, so this pulls nothing else down with it.
# Drop the flag to trade coreference for a smaller image and ~300MB less resident memory.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra coref

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra coref

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

# Separate layer: instantiating FCoref both downloads biu-nlp/f-coref into HF_HOME and
# proves the fastcoref install works, so an incompatibility fails the build here instead
# of degrading silently at runtime. Must match the --extra coref flag above; without the
# weights baked in, HF_HUB_OFFLINE=1 in the runtime stage would fail the load anyway.
RUN --mount=type=cache,target=/root/.cache/uv \
    .venv/bin/python -c "\
from fastcoref import FCoref; \
FCoref(model_name_or_path='biu-nlp/f-coref', device='cpu')"

# --- Runtime ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# TEXTROPY_ENVIRONMENT=production unmounts /docs, /redoc and /openapi.json. Override with
# `-e TEXTROPY_ENVIRONMENT=development` to get them back in a local container.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    TEXTROPY_ENVIRONMENT=production

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

# `fastapi run` binds 0.0.0.0:8000, disables reload, and enables --proxy-headers (needed
# behind the Caddy reverse proxy). `--workers` is left unset, i.e. one worker: each worker
# holds its own copy of the models (spec §9), so scaling workers multiplies RAM. Prefer
# async concurrency over worker count here.
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
