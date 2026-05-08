FROM python:3.13-slim AS builder

WORKDIR /build
RUN python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim

WORKDIR /app
RUN groupadd --gid 65532 nonroot \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin nonroot \
    && mkdir -p /app/models \
    && chown -R nonroot:nonroot /app

COPY --from=builder /build/.venv /app/.venv
COPY app/ ./app/

USER nonroot:nonroot
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8011
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8011"]
