FROM oven/bun:1.3-alpine AS builder

WORKDIR /build

COPY package.json bun.lock turbo.json ./
COPY apps/dashboard/package.json ./apps/dashboard/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ui/package.json ./packages/ui/package.json
RUN bun install --frozen-lockfile

COPY apps/dashboard ./apps/dashboard
COPY packages/types ./packages/types
COPY packages/ui ./packages/ui
RUN bun run build --filter=@khetibadi/dashboard

FROM nginx:1.27-alpine

COPY apps/dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/apps/dashboard/dist /usr/share/nginx/html

EXPOSE 80
