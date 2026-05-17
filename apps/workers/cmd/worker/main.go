// Package main is the entrypoint for the workers process.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
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
	marketHTTPTimeout   = 30 * time.Second

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
	defaultMarketAPIURL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
	defaultMarketLimit  = 100
)

type appConfig struct {
	Env                string `envconfig:"APP_ENV" default:"development"`
	LogLevel           string `envconfig:"LOG_LEVEL" default:"info"`
	RedisURL           string `envconfig:"REDIS_URL" default:"redis://redis:6379"`
	MarketServiceURL   string `envconfig:"MARKET_SERVICE_URL" default:"http://market-service:8002"`
	DataGovAPIKey      string `envconfig:"DATA_GOV_IN_API_KEY"`
	MarketDataAPIURL   string `envconfig:"MARKET_DATA_API_URL" default:"https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"`
	MarketDataFormat   string `envconfig:"MARKET_DATA_FORMAT" default:"json"`
	MarketDataResource string `envconfig:"MARKET_DATA_RESOURCE_ID" default:"9ef84268-d588-465a-a308-a864a43d0070"`
	Concurrency        int    `envconfig:"WORKER_CONCURRENCY" default:"5"`
	Port               int    `envconfig:"PORT" default:"8080"`
	MarketDataLimit    int    `envconfig:"MARKET_DATA_LIMIT" default:"100"`
}

type workerHandler struct {
	client *http.Client
	cfg    *appConfig
}

type dataGovResponse struct {
	Records []dataGovMarketRecord `json:"records"`
	Error   string                `json:"error"`
}

type dataGovMarketRecord struct {
	State       string          `json:"state"`
	District    string          `json:"district"`
	Market      string          `json:"market"`
	Commodity   string          `json:"commodity"`
	Variety     string          `json:"variety"`
	Grade       string          `json:"grade"`
	ArrivalDate string          `json:"arrival_date"`
	MinPrice    json.RawMessage `json:"min_price"`
	MaxPrice    json.RawMessage `json:"max_price"`
	ModalPrice  json.RawMessage `json:"modal_price"`
}

type syncRequest struct {
	Prices []marketPrice `json:"prices"`
}

type marketPrice struct {
	ObservedAt time.Time `json:"observed_at"`
	ID         string    `json:"id,omitempty"`
	Commodity  string    `json:"commodity"`
	State      string    `json:"state"`
	Market     string    `json:"market"`
	Unit       string    `json:"unit"`
	MinPrice   float64   `json:"min_price"`
	MaxPrice   float64   `json:"max_price"`
	ModalPrice float64   `json:"modal_price"`
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
	handler := &workerHandler{
		cfg:    &cfg,
		client: &http.Client{Timeout: marketHTTPTimeout},
	}
	registerHandlers(mux, handler)

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
	startupMarketSync(&redisOpt, cfg.DataGovAPIKey)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Info().Str("signal", sig.String()).Msg("shutdown signal received")

	server.Shutdown()
	scheduler.Shutdown()
	shutdownMonitor(monitor)
	log.Info().Msg("worker stopped cleanly")
}

func registerHandlers(mux *asynq.ServeMux, handler *workerHandler) {
	mux.HandleFunc(jobMarketSync, handler.syncMarketPrices)
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

func (h *workerHandler) syncMarketPrices(ctx context.Context, task *asynq.Task) error {
	if strings.TrimSpace(h.cfg.DataGovAPIKey) == "" {
		return errors.New("DATA_GOV_IN_API_KEY is required for market sync")
	}
	prices, err := h.fetchMarketPrices(ctx)
	if err != nil {
		return fmt.Errorf("fetch market prices: %w", err)
	}
	if len(prices) == 0 {
		log.Warn().Str("task", task.Type()).Msg("market sync returned no prices")
		return nil
	}
	if err := h.postMarketPrices(ctx, prices); err != nil {
		return fmt.Errorf("post market prices: %w", err)
	}
	log.Info().Str("task", task.Type()).Int("prices", len(prices)).Msg("market prices synced")
	return nil
}

func (h *workerHandler) fetchMarketPrices(ctx context.Context) ([]marketPrice, error) {
	endpoint, err := url.Parse(marketDataAPIURL(h.cfg))
	if err != nil {
		return nil, fmt.Errorf("parse market data url: %w", err)
	}
	query := endpoint.Query()
	query.Set("api-key", h.cfg.DataGovAPIKey)
	query.Set("format", valueOrDefault(h.cfg.MarketDataFormat, "json"))
	query.Set("offset", "0")
	query.Set("limit", strconv.Itoa(marketDataLimit(h.cfg.MarketDataLimit)))
	endpoint.RawQuery = query.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), http.NoBody)
	if err != nil {
		return nil, fmt.Errorf("create market data request: %w", err)
	}
	req.Header.Set("User-Agent", "khetibadi-workers/1.0")

	resp, err := h.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request market data: %w", err)
	}
	defer closeBody(resp.Body)
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("market data status %d", resp.StatusCode)
	}

	var payload dataGovResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, fmt.Errorf("decode market data: %w", err)
	}
	if payload.Error != "" {
		return nil, errors.New(payload.Error)
	}
	prices := make([]marketPrice, 0, len(payload.Records))
	for i := range payload.Records {
		price, ok := normalizeMarketRecord(&payload.Records[i])
		if ok {
			prices = append(prices, price)
		}
	}
	return prices, nil
}

func (h *workerHandler) postMarketPrices(ctx context.Context, prices []marketPrice) error {
	body, err := json.Marshal(syncRequest{Prices: prices})
	if err != nil {
		return fmt.Errorf("marshal sync request: %w", err)
	}
	endpoint := strings.TrimRight(h.cfg.MarketServiceURL, "/") + "/internal/market/sync"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create sync request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "khetibadi-workers/1.0")

	resp, err := h.client.Do(req)
	if err != nil {
		return fmt.Errorf("request market sync: %w", err)
	}
	defer closeBody(resp.Body)
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("market sync status %d", resp.StatusCode)
	}
	return nil
}

func normalizeMarketRecord(record *dataGovMarketRecord) (marketPrice, bool) {
	minPrice, minOK := parsePrice(record.MinPrice)
	maxPrice, maxOK := parsePrice(record.MaxPrice)
	modalPrice, modalOK := parsePrice(record.ModalPrice)
	if strings.TrimSpace(record.Commodity) == "" || strings.TrimSpace(record.Market) == "" || !modalOK {
		return marketPrice{}, false
	}
	if !minOK {
		minPrice = modalPrice
	}
	if !maxOK {
		maxPrice = modalPrice
	}
	return marketPrice{
		Commodity:  strings.ToLower(strings.TrimSpace(record.Commodity)),
		State:      strings.ToLower(strings.TrimSpace(record.State)),
		Market:     strings.ToLower(strings.TrimSpace(record.Market)),
		Unit:       "quintal",
		MinPrice:   minPrice,
		MaxPrice:   maxPrice,
		ModalPrice: modalPrice,
		ObservedAt: parseArrivalDate(record.ArrivalDate),
	}, true
}

func parsePrice(raw json.RawMessage) (float64, bool) {
	var quoted string
	if err := json.Unmarshal(raw, &quoted); err == nil {
		raw = json.RawMessage(quoted)
	}
	cleaned := strings.ReplaceAll(strings.TrimSpace(string(raw)), ",", "")
	if cleaned == "" || strings.EqualFold(cleaned, "NA") || cleaned == "-" {
		return 0, false
	}
	value, err := strconv.ParseFloat(cleaned, 64)
	return value, err == nil
}

func parseArrivalDate(raw string) time.Time {
	for _, layout := range []string{"02/01/2006", time.DateOnly} {
		parsed, err := time.Parse(layout, strings.TrimSpace(raw))
		if err == nil {
			return parsed.UTC()
		}
	}
	return time.Now().UTC()
}

func marketDataAPIURL(cfg *appConfig) string {
	if strings.TrimSpace(cfg.MarketDataAPIURL) != "" {
		return cfg.MarketDataAPIURL
	}
	if strings.TrimSpace(cfg.MarketDataResource) != "" {
		return "https://api.data.gov.in/resource/" + strings.TrimSpace(cfg.MarketDataResource)
	}
	return defaultMarketAPIURL
}

func marketDataLimit(limit int) int {
	if limit <= 0 {
		return defaultMarketLimit
	}
	if limit > 1000 {
		return 1000
	}
	return limit
}

func valueOrDefault(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func closeBody(body io.Closer) {
	if err := body.Close(); err != nil {
		log.Error().Err(err).Msg("close response body")
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

func startupMarketSync(redisOpt *asynq.RedisClientOpt, dataGovAPIKey string) {
	if strings.TrimSpace(dataGovAPIKey) == "" {
		log.Warn().Str("task", jobMarketSync).Msg("skip startup market sync without DATA_GOV_IN_API_KEY")
		return
	}
	client := asynq.NewClient(*redisOpt)
	defer func() {
		if err := client.Close(); err != nil {
			log.Error().Err(err).Msg("close asynq client")
		}
	}()
	if _, err := client.Enqueue(asynq.NewTask(jobMarketSync, nil), asynq.Queue(queueDefault)); err != nil {
		log.Error().Err(err).Str("task", jobMarketSync).Msg("enqueue startup market sync")
		return
	}
	log.Info().Str("task", jobMarketSync).Msg("startup market sync enqueued")
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
