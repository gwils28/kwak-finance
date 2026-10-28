# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
# 1 adds the forecast's foundation models (spec F-FCT-7): PyTorch for the processor and the
# weights of Chronos-2 and TimesFM 2.5, about 2.5 GB, checked against their checksums.
ARG KWAK_FOUNDATION_MODELS=0
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$KWAK_FOUNDATION_MODELS" = 1 ]; then extra="--extra foundation"; fi; \
    uv sync --frozen --no-dev --no-editable $extra
RUN if [ "$KWAK_FOUNDATION_MODELS" = 1 ]; then \
        /app/.venv/bin/python -m kwak_analytics.foundation fetch /app/models; \
    else mkdir /app/models; fi

FROM python:3.13-slim-bookworm
# LightGBM (the forecast's trees, spec §4.14) needs the OpenMP runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 kwak
COPY --from=build --chown=kwak:kwak /app/.venv /app/.venv
COPY --from=build --chown=kwak:kwak /app/models /app/models
# Read offline: nothing is downloaded when a forecast runs. An empty folder: no models.
ENV PATH="/app/.venv/bin:$PATH" KWAK_FOUNDATION_DIR=/app/models HF_HUB_OFFLINE=1
USER kwak
EXPOSE 8000
CMD ["uvicorn", "kwak_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
