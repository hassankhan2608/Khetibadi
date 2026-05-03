// Package main is the entrypoint for the workers process.
//
// Phase 2 skeleton: structured logging, env-driven config, and graceful
// shutdown on SIGINT/SIGTERM. Asynq server registration, queue priorities,
// and the Asynqmon UI on :8080 are wired in subsequent commits per
// apps/workers/AGENTS.md.
package main

import (
	"os"
	"os/signal"
	"syscall"

	"github.com/rs/zerolog/log"

	"github.com/khetibadi/go-shared/config"
	"github.com/khetibadi/go-shared/middleware"
)

const serviceName = "workers"

type appConfig struct {
	Env      string `envconfig:"APP_ENV" default:"development"`
	LogLevel string `envconfig:"LOG_LEVEL" default:"info"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)

	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	log.Info().
		Str("service", serviceName).
		Str("env", cfg.Env).
		Msg("worker starting")

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Info().Str("signal", sig.String()).Msg("shutdown signal received")

	log.Info().Msg("worker stopped cleanly")
}
