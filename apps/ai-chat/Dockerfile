FROM python:3.12-slim AS builder

WORKDIR /build
RUN python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim

WORKDIR /app
RUN groupadd --gid 65532 nonroot \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin nonroot \
    && chown -R nonroot:nonroot /app

COPY --from=builder /build/.venv /app/.venv
COPY app/ ./app/

USER nonroot:nonroot
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8012
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8012"]
