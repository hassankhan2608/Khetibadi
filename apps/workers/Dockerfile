FROM golang:1.26-alpine AS builder

WORKDIR /build

COPY go.work go.work.sum ./
COPY packages/go-shared/go.mod packages/go-shared/go.sum ./packages/go-shared/
COPY apps/workers/go.mod apps/workers/go.sum ./apps/workers/
RUN GOWORK=off go -C apps/workers mod download

COPY packages/go-shared ./packages/go-shared
COPY apps/workers ./apps/workers
RUN GOWORK=off CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
	go build -C apps/workers -ldflags="-s -w" -trimpath -o /app ./cmd/worker

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app /app

USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app"]
