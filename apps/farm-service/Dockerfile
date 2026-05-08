FROM golang:1.26-alpine AS builder

WORKDIR /build

COPY go.work go.work.sum ./
COPY packages/go-shared/go.mod packages/go-shared/go.sum ./packages/go-shared/
COPY apps/farm-service/go.mod apps/farm-service/go.sum ./apps/farm-service/
RUN GOWORK=off go -C apps/farm-service mod download

COPY packages/go-shared ./packages/go-shared
COPY apps/farm-service ./apps/farm-service
RUN GOWORK=off CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
	go build -C apps/farm-service -ldflags="-s -w" -trimpath -o /app ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app /app

USER nonroot:nonroot
EXPOSE 8001
ENTRYPOINT ["/app"]
