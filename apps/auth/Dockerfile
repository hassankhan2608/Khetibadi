FROM golang:1.26-alpine AS builder

WORKDIR /build

COPY go.work go.work.sum ./
COPY packages/go-shared/go.mod packages/go-shared/go.sum ./packages/go-shared/
COPY apps/auth/go.mod apps/auth/go.sum ./apps/auth/
RUN GOWORK=off go -C apps/auth mod download

COPY packages/go-shared ./packages/go-shared
COPY apps/auth ./apps/auth
RUN GOWORK=off CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
	go build -C apps/auth -ldflags="-s -w" -trimpath -o /app ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app /app

USER nonroot:nonroot
EXPOSE 8000
ENTRYPOINT ["/app"]
