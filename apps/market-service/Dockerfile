FROM golang:1.26-alpine AS builder

WORKDIR /build

COPY go.work go.work.sum ./
COPY packages/go-shared/go.mod packages/go-shared/go.sum ./packages/go-shared/
COPY apps/market-service/go.mod apps/market-service/go.sum ./apps/market-service/
RUN GOWORK=off go -C apps/market-service mod download

COPY packages/go-shared ./packages/go-shared
COPY apps/market-service ./apps/market-service
RUN GOWORK=off CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
	go build -C apps/market-service -ldflags="-s -w" -trimpath -o /app ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app /app

USER nonroot:nonroot
EXPOSE 8002
ENTRYPOINT ["/app"]
