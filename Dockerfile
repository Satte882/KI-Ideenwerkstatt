FROM python:3.13.5-slim-bookworm AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13.5-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client curl ca-certificates rclone \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app . /app
RUN chmod +x /app/scripts/*.sh \
    && mkdir -p /app/staticfiles /app/var \
    && chown -R app:app /app/staticfiles /app/var
USER app
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["/app/scripts/start-web.sh"]
