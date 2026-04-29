// Package main is the entrypoint for the market-service.
//
// Phase 2 skeleton: structured logging, env-driven config, shared request ID
// and request logger middleware, a /health endpoint, and graceful shutdown.
// Domain handlers (AGMARKNET prices, alerts) are wired in subsequent commits.
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/rs/zerolog/log"

	"github.com/khetibadi/go-shared/config"
	"github.com/khetibadi/go-shared/middleware"
	"github.com/khetibadi/go-shared/response"
)

const (
	serviceName    = "market-service"
	shutdownGrace  = 15 * time.Second
	readHdrTimeout = 10 * time.Second
)

type appConfig struct {
	Port     string `envconfig:"PORT" default:"8002"`
	Env      string `envconfig:"APP_ENV" default:"development"`
	LogLevel string `envconfig:"LOG_LEVEL" default:"info"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)

	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(middleware.RequestID())
	r.Use(middleware.Logger())

	r.GET("/health", func(c *gin.Context) {
		response.OK(c, gin.H{"status": "ok", "service": serviceName}, nil)
	})

	srv := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           r,
		ReadHeaderTimeout: readHdrTimeout,
	}

	go func() {
		log.Info().
			Str("service", serviceName).
			Str("env", cfg.Env).
			Str("addr", srv.Addr).
			Msg("server starting")
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatal().Err(err).Msg("server failed")
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Info().Str("signal", sig.String()).Msg("shutdown signal received")

	ctx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error().Err(err).Msg("graceful shutdown failed")
		cancel()
		os.Exit(1) //nolint:gocritic // explicit cancel above; deferred cancel is redundant here
	}
	log.Info().Msg("server stopped cleanly")
}
