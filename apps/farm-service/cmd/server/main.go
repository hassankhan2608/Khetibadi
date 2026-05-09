// Package main wires the farm-service HTTP API.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"math"
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
	serviceName    = "farm-service"
	shutdownGrace  = 15 * time.Second
	readHdrTimeout = 10 * time.Second
	maxFarmAreaHa  = 10000
)

type appConfig struct {
	Port       string `envconfig:"PORT" default:"8001"`
	Env        string `envconfig:"APP_ENV" default:"development"`
	LogLevel   string `envconfig:"LOG_LEVEL" default:"info"`
	HMACSecret string `envconfig:"HMAC_SECRET"`
}

type farm struct {
	CreatedAt    time.Time       `json:"created_at"`
	UpdatedAt    time.Time       `json:"updated_at"`
	Boundary     json.RawMessage `json:"boundary"`
	ID           string          `json:"id"`
	UserID       string          `json:"user_id"`
	Name         string          `json:"name"`
	Crop         string          `json:"crop"`
	SoilType     string          `json:"soil_type"`
	AreaHectares float64         `json:"area_hectares"`
}

type soilSample struct {
	CollectedAt time.Time `json:"collected_at"`
	CreatedAt   time.Time `json:"created_at"`
	ID          string    `json:"id"`
	FarmID      string    `json:"farm_id"`
	UserID      string    `json:"user_id"`
	PH          float64   `json:"ph"`
	Nitrogen    float64   `json:"nitrogen"`
	Phosphorus  float64   `json:"phosphorus"`
	Potassium   float64   `json:"potassium"`
	Organic     float64   `json:"organic_carbon"`
	Moisture    float64   `json:"moisture"`
}

type farmStore struct {
	mu          sync.RWMutex
	farms       map[string]*farm
	soilSamples map[string][]*soilSample
}

type farmHandler struct {
	store *farmStore
}

type farmRequest struct {
	Boundary     json.RawMessage `json:"boundary" binding:"required"`
	Name         string          `json:"name" binding:"required"`
	Crop         string          `json:"crop"`
	SoilType     string          `json:"soil_type"`
	AreaHectares float64         `json:"area_hectares"`
}

type soilSampleRequest struct {
	CollectedAt string  `json:"collected_at"`
	PH          float64 `json:"ph" binding:"required"`
	Nitrogen    float64 `json:"nitrogen" binding:"required"`
	Phosphorus  float64 `json:"phosphorus" binding:"required"`
	Potassium   float64 `json:"potassium" binding:"required"`
	Organic     float64 `json:"organic_carbon"`
	Moisture    float64 `json:"moisture"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)

	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	h := &farmHandler{store: newFarmStore()}
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(middleware.RequestID())
	r.Use(middleware.Logger())

	r.GET("/health", h.health)
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

func newFarmStore() *farmStore {
	return &farmStore{farms: make(map[string]*farm), soilSamples: make(map[string][]*soilSample)}
}

func (h *farmHandler) registerRoutes(r gin.IRoutes) {
	r.POST("/farms", h.createFarm)
	r.GET("/farms", h.listFarms)
	r.GET("/farms/:id", h.getFarm)
	r.PUT("/farms/:id", h.updateFarm)
	r.PATCH("/farms/:id", h.updateFarm)
	r.DELETE("/farms/:id", h.deleteFarm)
	r.POST("/farms/:id/soil-samples", h.createSoilSample)
	r.GET("/farms/:id/soil-samples", h.listSoilSamples)
	r.GET("/farms/:id/weather", h.getWeather)
}

func (h *farmHandler) health(c *gin.Context) {
	response.OK(c, gin.H{"status": "ok", "service": serviceName, "uptime_check": "in_memory"}, nil)
}

func (h *farmHandler) createFarm(c *gin.Context) {
	userID := middleware.UserIDFrom(c)
	var req farmRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	prepared, ok := prepareFarmRequest(c, &req)
	if !ok {
		return
	}
	now := time.Now().UTC()
	created := &farm{
		ID:           uuid.NewString(),
		UserID:       userID,
		Name:         prepared.Name,
		Crop:         prepared.Crop,
		SoilType:     prepared.SoilType,
		AreaHectares: prepared.AreaHectares,
		Boundary:     prepared.Boundary,
		CreatedAt:    now,
		UpdatedAt:    now,
	}
	h.store.mu.Lock()
	h.store.farms[created.ID] = created
	h.store.mu.Unlock()
	response.Created(c, created)
}

func (h *farmHandler) listFarms(c *gin.Context) {
	userID := middleware.UserIDFrom(c)
	page := pagination.Parse(c)
	h.store.mu.RLock()
	items := make([]*farm, 0)
	for _, item := range h.store.farms {
		if item.UserID == userID {
			items = append(items, cloneFarm(item))
		}
	}
	h.store.mu.RUnlock()
	sort.Slice(items, func(i, j int) bool { return items[i].CreatedAt.After(items[j].CreatedAt) })
	total := len(items)
	items = paginate(items, page.Offset, page.Limit)
	response.Paginated(c, items, response.PageMeta{Page: page.Page, Limit: page.Limit, Total: int64(total)})
}

func (h *farmHandler) getFarm(c *gin.Context) {
	item, ok := h.findOwnedFarm(c, c.Param("id"))
	if !ok {
		return
	}
	response.OK(c, item, nil)
}

func (h *farmHandler) updateFarm(c *gin.Context) {
	farmID := c.Param("id")
	userID := middleware.UserIDFrom(c)
	var req farmRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	prepared, ok := prepareFarmRequest(c, &req)
	if !ok {
		return
	}
	h.store.mu.Lock()
	item := h.store.farms[farmID]
	if item == nil || item.UserID != userID {
		h.store.mu.Unlock()
		response.Error(c, http.StatusNotFound, response.CodeNotFound, "farm not found")
		return
	}
	item.Name = prepared.Name
	item.Crop = prepared.Crop
	item.SoilType = prepared.SoilType
	item.AreaHectares = prepared.AreaHectares
	item.Boundary = prepared.Boundary
	item.UpdatedAt = time.Now().UTC()
	updated := cloneFarm(item)
	h.store.mu.Unlock()
	response.OK(c, updated, nil)
}

func (h *farmHandler) deleteFarm(c *gin.Context) {
	farmID := c.Param("id")
	userID := middleware.UserIDFrom(c)
	h.store.mu.Lock()
	item := h.store.farms[farmID]
	if item == nil || item.UserID != userID {
		h.store.mu.Unlock()
		response.Error(c, http.StatusNotFound, response.CodeNotFound, "farm not found")
		return
	}
	delete(h.store.farms, farmID)
	delete(h.store.soilSamples, farmID)
	h.store.mu.Unlock()
	response.NoContent(c)
}

func (h *farmHandler) createSoilSample(c *gin.Context) {
	farmID := c.Param("id")
	userID := middleware.UserIDFrom(c)
	if _, ok := h.findOwnedFarm(c, farmID); !ok {
		return
	}
	var req soilSampleRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	collectedAt, ok := parseCollectedAt(c, req.CollectedAt)
	if !ok {
		return
	}
	now := time.Now().UTC()
	created := &soilSample{
		ID:          uuid.NewString(),
		FarmID:      farmID,
		UserID:      userID,
		PH:          req.PH,
		Nitrogen:    req.Nitrogen,
		Phosphorus:  req.Phosphorus,
		Potassium:   req.Potassium,
		Organic:     req.Organic,
		Moisture:    req.Moisture,
		CollectedAt: collectedAt,
		CreatedAt:   now,
	}
	h.store.mu.Lock()
	h.store.soilSamples[farmID] = append(h.store.soilSamples[farmID], created)
	h.store.mu.Unlock()
	response.Created(c, created)
}

func (h *farmHandler) listSoilSamples(c *gin.Context) {
	farmID := c.Param("id")
	if _, ok := h.findOwnedFarm(c, farmID); !ok {
		return
	}
	page := pagination.Parse(c)
	h.store.mu.RLock()
	items := append([]*soilSample(nil), h.store.soilSamples[farmID]...)
	h.store.mu.RUnlock()
	sort.Slice(items, func(i, j int) bool { return items[i].CollectedAt.After(items[j].CollectedAt) })
	total := len(items)
	items = paginate(items, page.Offset, page.Limit)
	response.Paginated(c, items, response.PageMeta{Page: page.Page, Limit: page.Limit, Total: int64(total)})
}

func (h *farmHandler) getWeather(c *gin.Context) {
	item, ok := h.findOwnedFarm(c, c.Param("id"))
	if !ok {
		return
	}
	seed := float64(len(item.ID) + len(item.Name))
	weather := gin.H{
		"farm_id":      item.ID,
		"source":       "stub",
		"condition":    "partly_cloudy",
		"temperature":  math.Round((24+math.Mod(seed, 9))*10) / 10,
		"humidity":     int(55 + math.Mod(seed, 25)),
		"wind_speed":   math.Round((3+math.Mod(seed, 5))*10) / 10,
		"rainfall_mm":  math.Round(math.Mod(seed, 12)*10) / 10,
		"cached":       true,
		"generated_at": time.Now().UTC(),
	}
	response.OK(c, weather, nil)
}

func (h *farmHandler) findOwnedFarm(c *gin.Context, farmID string) (*farm, bool) {
	userID := middleware.UserIDFrom(c)
	h.store.mu.RLock()
	item := h.store.farms[farmID]
	if item == nil || item.UserID != userID {
		h.store.mu.RUnlock()
		response.Error(c, http.StatusNotFound, response.CodeNotFound, "farm not found")
		return nil, false
	}
	clone := cloneFarm(item)
	h.store.mu.RUnlock()
	return clone, true
}

func prepareFarmRequest(c *gin.Context, req *farmRequest) (farmRequest, bool) {
	prepared := *req
	prepared.Name = strings.TrimSpace(prepared.Name)
	prepared.Crop = strings.TrimSpace(prepared.Crop)
	prepared.SoilType = strings.TrimSpace(prepared.SoilType)
	if prepared.Name == "" {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, "farm name is required")
		return farmRequest{}, false
	}
	if !json.Valid(prepared.Boundary) {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, "boundary must be valid GeoJSON")
		return farmRequest{}, false
	}
	if prepared.AreaHectares <= 0 {
		prepared.AreaHectares = 1
	}
	if prepared.AreaHectares > maxFarmAreaHa {
		response.Error(c, http.StatusUnprocessableEntity, response.CodeUnprocessable, "farm area exceeds 10000 hectares")
		return farmRequest{}, false
	}
	return prepared, true
}

func parseCollectedAt(c *gin.Context, raw string) (time.Time, bool) {
	if strings.TrimSpace(raw) == "" {
		return time.Now().UTC(), true
	}
	parsed, err := time.Parse(time.RFC3339, raw)
	if err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, "collected_at must be RFC3339")
		return time.Time{}, false
	}
	return parsed.UTC(), true
}

func cloneFarm(item *farm) *farm {
	clone := *item
	clone.Boundary = append(json.RawMessage(nil), item.Boundary...)
	return &clone
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
