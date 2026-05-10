// Package main is the entrypoint for the workers process.
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/hibiken/asynq"
	"github.com/hibiken/asynqmon"
	"github.com/rs/zerolog/log"

	"github.com/khetibadi/go-shared/config"
	"github.com/khetibadi/go-shared/middleware"
)

const (
	serviceName         = "workers"
	shutdownGrace       = 10 * time.Second
	asynqmonReadTimeout = 5 * time.Second

	jobMarketSync       = "market:sync_prices"
	jobCheckAlerts      = "market:check_price_alerts"
	jobWeatherPrefetch  = "farm:prefetch_weather"
	jobVisionDetect     = "vision:detect_disease"
	jobKnowledgeIndex   = "ai:index_knowledge_chunk"
	jobNotifications    = "notifications:send"
	jobCleanup          = "cleanup:stale_data"
	jobMLWarmup         = "ml:warmup_models"
	queueCritical       = "critical"
	queueDefault        = "default"
	queueLow            = "low"
	asynqmonRootPath    = "/monitoring"
	defaultRedisAddress = "redis:6379"
)

type appConfig struct {
	Env         string `envconfig:"APP_ENV" default:"development"`
	LogLevel    string `envconfig:"LOG_LEVEL" default:"info"`
	RedisURL    string `envconfig:"REDIS_URL" default:"redis://redis:6379"`
	Concurrency int    `envconfig:"WORKER_CONCURRENCY" default:"5"`
	Port        int    `envconfig:"PORT" default:"8080"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)
	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	redisOpt := redisClientOpt(cfg.RedisURL)
	server := asynq.NewServer(redisOpt, asynq.Config{
		Concurrency: cfg.Concurrency,
		Queues: map[string]int{
			queueCritical: 6,
			queueDefault:  3,
			queueLow:      1,
		},
	})
	mux := asynq.NewServeMux()
	registerHandlers(mux)

	scheduler := asynq.NewScheduler(redisOpt, nil)
	registerSchedules(scheduler)
	monitor := newMonitorServer(cfg.Port, &redisOpt)

	log.Info().
		Str("service", serviceName).
		Str("env", cfg.Env).
		Int("port", cfg.Port).
		Msg("worker starting")

	runAsync("asynq_server", func() error { return server.Run(mux) })
	runAsync("asynq_scheduler", scheduler.Run)
	runAsync("asynqmon", monitor.ListenAndServe)

	warmup(&redisOpt)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Info().Str("signal", sig.String()).Msg("shutdown signal received")

	server.Shutdown()
	scheduler.Shutdown()
	shutdownMonitor(monitor)
	log.Info().Msg("worker stopped cleanly")
}

func registerHandlers(mux *asynq.ServeMux) {
	mux.HandleFunc(jobMarketSync, logJob)
	mux.HandleFunc(jobCheckAlerts, logJob)
	mux.HandleFunc(jobWeatherPrefetch, logJob)
	mux.HandleFunc(jobVisionDetect, logJob)
	mux.HandleFunc(jobKnowledgeIndex, logJob)
	mux.HandleFunc(jobNotifications, logJob)
	mux.HandleFunc(jobCleanup, logJob)
	mux.HandleFunc(jobMLWarmup, logJob)
}

func registerSchedules(scheduler *asynq.Scheduler) {
	mustRegister(scheduler, "0 */6 * * *", asynq.NewTask(jobMarketSync, nil), queueDefault)
	mustRegister(scheduler, "0 */3 * * *", asynq.NewTask(jobWeatherPrefetch, nil), queueDefault)
	mustRegister(scheduler, "30 20 * * *", asynq.NewTask(jobCleanup, nil), queueLow)
}

func mustRegister(scheduler *asynq.Scheduler, spec string, task *asynq.Task, queue string) {
	entryID, err := scheduler.Register(spec, task, asynq.Queue(queue))
	if err != nil {
		log.Fatal().Err(err).Str("task", task.Type()).Str("cron", spec).Msg("register schedule")
	}
	log.Info().Str("entry_id", entryID).Str("task", task.Type()).Str("queue", queue).Msg("schedule registered")
}

func newMonitorServer(port int, redisOpt *asynq.RedisClientOpt) *http.Server {
	monitor := asynqmon.New(asynqmon.Options{
		RootPath:     asynqmonRootPath,
		RedisConnOpt: *redisOpt,
	})
	mux := http.NewServeMux()
	mux.Handle(monitor.RootPath()+"/", monitor)
	mux.HandleFunc("/health", healthHandler)
	return &http.Server{
		Addr:              ":" + strconv.Itoa(port),
		Handler:           mux,
		ReadHeaderTimeout: asynqmonReadTimeout,
	}
}

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte(`{"status":"ok","service":"workers"}`)); err != nil {
		log.Error().Err(err).Msg("write health response")
	}
}

func logJob(ctx context.Context, task *asynq.Task) error {
	log.Info().Str("task", task.Type()).Int("payload_bytes", len(task.Payload())).Msg("job handled")
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return nil
	}
}

func warmup(redisOpt *asynq.RedisClientOpt) {
	client := asynq.NewClient(*redisOpt)
	defer func() {
		if err := client.Close(); err != nil {
			log.Error().Err(err).Msg("close asynq client")
		}
	}()
	if _, err := client.Enqueue(asynq.NewTask(jobMLWarmup, nil), asynq.Queue(queueLow)); err != nil {
		log.Error().Err(err).Str("task", jobMLWarmup).Msg("enqueue warmup task")
		return
	}
	log.Info().Str("task", jobMLWarmup).Msg("warmup task enqueued")
}

func runAsync(name string, fn func() error) {
	go func() {
		if err := fn(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error().Err(err).Str("component", name).Msg("component stopped")
		}
	}()
}

func shutdownMonitor(server *http.Server) {
	ctx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Error().Err(err).Msg("shutdown asynqmon")
	}
}

func redisClientOpt(redisURL string) asynq.RedisClientOpt {
	trimmed := strings.TrimSpace(redisURL)
	trimmed = strings.TrimPrefix(trimmed, "redis://")
	trimmed = strings.TrimSuffix(trimmed, "/0")
	if trimmed == "" {
		trimmed = defaultRedisAddress
	}
	return asynq.RedisClientOpt{Addr: trimmed}
}
