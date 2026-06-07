FROM oven/bun:1.3-alpine AS deps

WORKDIR /app

COPY package.json bun.lock ./
COPY apps/dashboard/package.json apps/dashboard/package.json
COPY apps/whatsapp-bridge/package.json apps/whatsapp-bridge/package.json
COPY packages/types/package.json packages/types/package.json
COPY packages/ui/package.json packages/ui/package.json
RUN bun install --frozen-lockfile

FROM oven/bun:1.3-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S -G app app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json bun.lock ./
COPY apps/whatsapp-bridge ./apps/whatsapp-bridge

RUN mkdir -p /app/data/whatsapp && chown -R app:app /app

USER app

WORKDIR /app/apps/whatsapp-bridge

CMD ["bun", "run", "start"]
