// Package main wires the market-service HTTP API.
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/rs/zerolog/log"

	"github.com/khetibadi/go-shared/config"
	"github.com/khetibadi/go-shared/middleware"
	"github.com/khetibadi/go-shared/pagination"
	"github.com/khetibadi/go-shared/response"
)

const (
	serviceName      = "market-service"
	shutdownGrace    = 15 * time.Second
	readHdrTimeout   = 10 * time.Second
	maxActiveAlerts  = 20
	maxHistoryWindow = 730 * 24 * time.Hour
)

type appConfig struct {
	Port       string `envconfig:"PORT" default:"8002"`
	Env        string `envconfig:"APP_ENV" default:"development"`
	LogLevel   string `envconfig:"LOG_LEVEL" default:"info"`
	HMACSecret string `envconfig:"HMAC_SECRET"`
}

type marketPrice struct {
	ObservedAt time.Time `json:"observed_at"`
	ID         string    `json:"id"`
	Commodity  string    `json:"commodity"`
	State      string    `json:"state"`
	Market     string    `json:"market"`
	Unit       string    `json:"unit"`
	MinPrice   float64   `json:"min_price"`
	MaxPrice   float64   `json:"max_price"`
	ModalPrice float64   `json:"modal_price"`
}

type priceAlert struct {
	CreatedAt   time.Time `json:"created_at"`
	ID          string    `json:"id"`
	UserID      string    `json:"user_id"`
	Commodity   string    `json:"commodity"`
	State       string    `json:"state"`
	Market      string    `json:"market"`
	Direction   string    `json:"direction"`
	TargetPrice float64   `json:"target_price"`
	Active      bool      `json:"active"`
}

type marketStore struct {
	mu     sync.RWMutex
	prices []*marketPrice
	alerts map[string]*priceAlert
}

type marketHandler struct {
	store *marketStore
}

type alertRequest struct {
	Commodity   string  `json:"commodity" binding:"required"`
	State       string  `json:"state" binding:"required"`
	Market      string  `json:"market"`
	Direction   string  `json:"direction" binding:"required"`
	TargetPrice float64 `json:"target_price" binding:"required"`
}

type syncRequest struct {
	Prices []marketPrice `json:"prices" binding:"required"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)

	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	h := &marketHandler{store: newMarketStore()}
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(middleware.RequestID())
	r.Use(middleware.Logger())

	r.GET("/health", h.health)
	r.POST("/internal/market/sync", h.syncPrices)
	protected := r.Group("/")
	protected.Use(middleware.HMACAuth(middleware.HMACAuthConfig{Secret: cfg.HMACSecret}))
	h.registerRoutes(protected)

	srv := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           r,
		ReadHeaderTimeout: readHdrTimeout,
	}

	go func() {
		log.Info().Str("service", serviceName).Str("env", cfg.Env).Str("addr", srv.Addr).Msg("server starting")
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

func newMarketStore() *marketStore {
	now := time.Now().UTC()
	return &marketStore{
		prices: []*marketPrice{
			{ID: uuid.NewString(), Commodity: "wheat", State: "punjab", Market: "ludhiana", Unit: "quintal", MinPrice: 2100, MaxPrice: 2450, ModalPrice: 2325, ObservedAt: now.Add(-2 * time.Hour)},
			{ID: uuid.NewString(), Commodity: "rice", State: "west bengal", Market: "burdwan", Unit: "quintal", MinPrice: 1850, MaxPrice: 2200, ModalPrice: 2040, ObservedAt: now.Add(-3 * time.Hour)},
			{ID: uuid.NewString(), Commodity: "maize", State: "karnataka", Market: "davangere", Unit: "quintal", MinPrice: 1750, MaxPrice: 2050, ModalPrice: 1920, ObservedAt: now.Add(-4 * time.Hour)},
		},
		alerts: make(map[string]*priceAlert),
	}
}

func (h *marketHandler) registerRoutes(r gin.IRoutes) {
	r.GET("/market/prices", h.listPrices)
	r.GET("/market/prices/history", h.priceHistory)
	r.GET("/market/commodities", h.listCommodities)
	r.GET("/market/commodities/:name/states", h.listStates)
	r.POST("/market/alerts", h.createAlert)
	r.GET("/market/alerts", h.listAlerts)
	r.DELETE("/market/alerts/:id", h.deleteAlert)
}

func (h *marketHandler) health(c *gin.Context) {
	response.OK(c, gin.H{"status": "ok", "service": serviceName, "uptime_check": "in_memory"}, nil)
}

func (h *marketHandler) listPrices(c *gin.Context) {
	page := pagination.Parse(c)
	commodity := normalize(c.Query("commodity"))
	state := normalize(c.Query("state"))
	h.store.mu.RLock()
	items := make([]*marketPrice, 0, len(h.store.prices))
	for _, price := range h.store.prices {
		if matchesPrice(price, commodity, state) {
			items = append(items, clonePrice(price))
		}
	}
	h.store.mu.RUnlock()
	sort.Slice(items, func(i, j int) bool { return items[i].ObservedAt.After(items[j].ObservedAt) })
	total := len(items)
	items = paginate(items, page.Offset, page.Limit)
	c.Header("X-Cache", "MISS")
	response.Paginated(c, items, response.PageMeta{Page: page.Page, Limit: page.Limit, Total: int64(total)})
}

func (h *marketHandler) priceHistory(c *gin.Context) {
	from, to, ok := parseHistoryRange(c)
	if !ok {
		return
	}
	commodity := normalize(c.Query("commodity"))
	state := normalize(c.Query("state"))
	h.store.mu.RLock()
	items := make([]*marketPrice, 0)
	for _, price := range h.store.prices {
		if matchesPrice(price, commodity, state) && !price.ObservedAt.Before(from) && !price.ObservedAt.After(to) {
			items = append(items, clonePrice(price))
		}
	}
	h.store.mu.RUnlock()
	sort.Slice(items, func(i, j int) bool { return items[i].ObservedAt.Before(items[j].ObservedAt) })
	c.Header("X-Cache", "MISS")
	response.OK(c, items, nil)
}

func (h *marketHandler) listCommodities(c *gin.Context) {
	h.store.mu.RLock()
	seen := make(map[string]struct{})
	for _, price := range h.store.prices {
		seen[price.Commodity] = struct{}{}
	}
	h.store.mu.RUnlock()
	commodities := keys(seen)
	response.OK(c, commodities, nil)
}

func (h *marketHandler) listStates(c *gin.Context) {
	commodity := normalize(c.Param("name"))
	h.store.mu.RLock()
	seen := make(map[string]struct{})
	for _, price := range h.store.prices {
		if normalize(price.Commodity) == commodity {
			seen[price.State] = struct{}{}
		}
	}
	h.store.mu.RUnlock()
	response.OK(c, keys(seen), nil)
}

func (h *marketHandler) createAlert(c *gin.Context) {
	userID := middleware.UserIDFrom(c)
	var req alertRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	req.Commodity = normalize(req.Commodity)
	req.State = normalize(req.State)
	req.Market = normalize(req.Market)
	req.Direction = normalize(req.Direction)
	if req.Direction != "above" && req.Direction != "below" {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, "direction must be above or below")
		return
	}
	if req.TargetPrice <= 0 {
		response.Error(c, http.StatusUnprocessableEntity, response.CodeUnprocessable, "target_price must be positive")
		return
	}
	h.store.mu.Lock()
	active := 0
	for _, alert := range h.store.alerts {
		if alert.UserID == userID && alert.Active {
			active++
		}
	}
	if active >= maxActiveAlerts {
		h.store.mu.Unlock()
		response.Error(c, http.StatusUnprocessableEntity, response.CodeUnprocessable, "alert limit reached")
		return
	}
	created := &priceAlert{ID: uuid.NewString(), UserID: userID, Commodity: req.Commodity, State: req.State, Market: req.Market, Direction: req.Direction, TargetPrice: req.TargetPrice, Active: true, CreatedAt: time.Now().UTC()}
	h.store.alerts[created.ID] = created
	h.store.mu.Unlock()
	response.Created(c, created)
}

func (h *marketHandler) listAlerts(c *gin.Context) {
	userID := middleware.UserIDFrom(c)
	h.store.mu.RLock()
	items := make([]*priceAlert, 0)
	for _, alert := range h.store.alerts {
		if alert.UserID == userID {
			items = append(items, cloneAlert(alert))
		}
	}
	h.store.mu.RUnlock()
	sort.Slice(items, func(i, j int) bool { return items[i].CreatedAt.After(items[j].CreatedAt) })
	response.OK(c, items, nil)
}

func (h *marketHandler) deleteAlert(c *gin.Context) {
	userID := middleware.UserIDFrom(c)
	alertID := c.Param("id")
	h.store.mu.Lock()
	alert := h.store.alerts[alertID]
	if alert == nil || alert.UserID != userID {
		h.store.mu.Unlock()
		response.Error(c, http.StatusNotFound, response.CodeNotFound, "alert not found")
		return
	}
	delete(h.store.alerts, alertID)
	h.store.mu.Unlock()
	response.NoContent(c)
}

func (h *marketHandler) syncPrices(c *gin.Context) {
	var req syncRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	prices := make([]*marketPrice, 0, len(req.Prices))
	now := time.Now().UTC()
	for i := range req.Prices {
		price := req.Prices[i]
		price.ID = valueOrDefault(price.ID, uuid.NewString())
		price.Commodity = normalize(price.Commodity)
		price.State = normalize(price.State)
		price.Market = normalize(price.Market)
		price.Unit = valueOrDefault(price.Unit, "quintal")
		if price.ObservedAt.IsZero() {
			price.ObservedAt = now
		}
		prices = append(prices, &price)
	}
	h.store.mu.Lock()
	h.store.prices = prices
	h.store.mu.Unlock()
	response.OK(c, gin.H{"synced": len(prices)}, nil)
}

func parseHistoryRange(c *gin.Context) (from, to time.Time, ok bool) {
	now := time.Now().UTC()
	from = now.Add(-30 * 24 * time.Hour)
	to = now
	if raw := c.Query("from"); raw != "" {
		parsed, err := time.Parse(time.DateOnly, raw)
		if err != nil {
			response.Error(c, http.StatusBadRequest, response.CodeValidation, "from must be YYYY-MM-DD")
			return time.Time{}, time.Time{}, false
		}
		from = parsed
	}
	if raw := c.Query("to"); raw != "" {
		parsed, err := time.Parse(time.DateOnly, raw)
		if err != nil {
			response.Error(c, http.StatusBadRequest, response.CodeValidation, "to must be YYYY-MM-DD")
			return time.Time{}, time.Time{}, false
		}
		to = parsed.Add(24*time.Hour - time.Nanosecond)
	}
	if to.Sub(from) > maxHistoryWindow {
		response.Error(c, http.StatusBadRequest, response.CodeBadRequest, "history range is too large")
		return time.Time{}, time.Time{}, false
	}
	return from, to, true
}

func matchesPrice(price *marketPrice, commodity, state string) bool {
	if commodity != "" && normalize(price.Commodity) != commodity {
		return false
	}
	return state == "" || normalize(price.State) == state
}

func clonePrice(price *marketPrice) *marketPrice {
	clone := *price
	return &clone
}

func cloneAlert(alert *priceAlert) *priceAlert {
	clone := *alert
	return &clone
}

func normalize(value string) string {
	return strings.ToLower(strings.TrimSpace(value))
}

func valueOrDefault(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func keys(values map[string]struct{}) []string {
	items := make([]string, 0, len(values))
	for value := range values {
		items = append(items, value)
	}
	sort.Strings(items)
	return items
}

func paginate[T any](items []T, offset, limit int) []T {
	if offset >= len(items) {
		return []T{}
	}
	end := offset + limit
	if end > len(items) {
		end = len(items)
	}
	return items[offset:end]
}
