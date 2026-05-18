// Package main wires the farm-service HTTP API.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"sort"
	"strconv"
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
	weatherTimeout = 8 * time.Second
	maxFarmAreaHa  = 10000
)

type appConfig struct {
	Port                   string `envconfig:"PORT" default:"8001"`
	Env                    string `envconfig:"APP_ENV" default:"development"`
	LogLevel               string `envconfig:"LOG_LEVEL" default:"info"`
	HMACSecret             string `envconfig:"HMAC_SECRET"`
	OpenWeatherAPIKey      string `envconfig:"OPENWEATHER_API_KEY"`
	OpenWeatherMapAPIKey   string `envconfig:"OPENWEATHERMAP_API_KEY"`
	OpenWeatherCurrentURL  string `envconfig:"OPENWEATHER_CURRENT_URL" default:"https://api.openweathermap.org/data/2.5/weather"`
	OpenWeatherUnits       string `envconfig:"OPENWEATHER_UNITS" default:"metric"`
	OpenWeatherLang        string `envconfig:"OPENWEATHER_LANG" default:"en"`
	WeatherCacheTTLSeconds int    `envconfig:"WEATHER_CACHE_TTL" default:"10800"`
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
	weather     map[string]weatherCacheEntry
}

type farmHandler struct {
	client *http.Client
	store  *farmStore
	cfg    *appConfig
}

type weatherCacheEntry struct {
	payload   gin.H
	expiresAt time.Time
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

type openWeatherResponse struct {
	Main struct {
		Temp      float64 `json:"temp"`
		FeelsLike float64 `json:"feels_like"`
		Humidity  int     `json:"humidity"`
		Pressure  int     `json:"pressure"`
	} `json:"main"`
	Wind struct {
		Speed float64 `json:"speed"`
		Deg   int     `json:"deg"`
	} `json:"wind"`
	Clouds struct {
		All int `json:"all"`
	} `json:"clouds"`
	Rain    map[string]float64 `json:"rain"`
	Snow    map[string]float64 `json:"snow"`
	Weather []struct {
		Main        string `json:"main"`
		Description string `json:"description"`
	} `json:"weather"`
	ObservedAt int64 `json:"dt"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)

	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	h := &farmHandler{
		cfg:    &cfg,
		client: &http.Client{Timeout: weatherTimeout},
		store:  newFarmStore(),
	}
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
	return &farmStore{
		farms:       make(map[string]*farm),
		soilSamples: make(map[string][]*soilSample),
		weather:     make(map[string]weatherCacheEntry),
	}
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
	if cached, ok := h.cachedWeather(item.ID); ok {
		response.OK(c, cached, nil)
		return
	}
	latitude, longitude, ok := boundaryCentroid(item.Boundary)
	if !ok {
		response.Error(c, http.StatusUnprocessableEntity, response.CodeUnprocessable, "farm boundary has no coordinates")
		return
	}
	weather, err := h.fetchWeather(c.Request.Context(), item.ID, latitude, longitude)
	if err != nil {
		log.Error().Err(err).Str("farm_id", item.ID).Msg("openweather request failed")
		response.Error(c, http.StatusBadGateway, response.CodeUpstream, "weather service unavailable")
		return
	}
	h.storeWeather(item.ID, weather)
	response.OK(c, weather, nil)
}

func (h *farmHandler) cachedWeather(farmID string) (gin.H, bool) {
	h.store.mu.RLock()
	entry, ok := h.store.weather[farmID]
	h.store.mu.RUnlock()
	if !ok || time.Now().UTC().After(entry.expiresAt) {
		return nil, false
	}
	clone := gin.H{}
	for key, value := range entry.payload {
		clone[key] = value
	}
	clone["cached"] = true
	return clone, true
}

func (h *farmHandler) storeWeather(farmID string, payload gin.H) {
	clone := gin.H{}
	for key, value := range payload {
		clone[key] = value
	}
	h.store.mu.Lock()
	h.store.weather[farmID] = weatherCacheEntry{
		payload:   clone,
		expiresAt: time.Now().UTC().Add(time.Duration(h.cfg.WeatherCacheTTLSeconds) * time.Second),
	}
	h.store.mu.Unlock()
}

func (h *farmHandler) fetchWeather(ctx context.Context, farmID string, latitude, longitude float64) (gin.H, error) {
	apiKey := openWeatherAPIKey(h.cfg)
	if apiKey == "" {
		return nil, errors.New("OPENWEATHER_API_KEY is required")
	}
	endpoint, err := url.Parse(h.cfg.OpenWeatherCurrentURL)
	if err != nil {
		return nil, err
	}
	query := endpoint.Query()
	query.Set("lat", strconv.FormatFloat(latitude, 'f', 6, 64))
	query.Set("lon", strconv.FormatFloat(longitude, 'f', 6, 64))
	query.Set("appid", apiKey)
	query.Set("units", valueOrDefault(h.cfg.OpenWeatherUnits, "metric"))
	query.Set("lang", valueOrDefault(h.cfg.OpenWeatherLang, "en"))
	endpoint.RawQuery = query.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), http.NoBody)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "khetibadi-farm-service/1.0")
	resp, err := h.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			log.Error().Err(err).Msg("close weather response body")
		}
	}()
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, errors.New("openweather returned status " + strconv.Itoa(resp.StatusCode))
	}
	var payload openWeatherResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	condition, description := weatherCondition(&payload)
	return gin.H{
		"farm_id":           farmID,
		"source":            "openweathermap",
		"condition":         condition,
		"description":       description,
		"temperature":       payload.Main.Temp,
		"feels_like":        payload.Main.FeelsLike,
		"humidity":          payload.Main.Humidity,
		"pressure":          payload.Main.Pressure,
		"wind_speed":        payload.Wind.Speed,
		"wind_degrees":      payload.Wind.Deg,
		"cloudiness":        payload.Clouds.All,
		"rainfall_mm":       precipitation(payload.Rain),
		"snowfall_mm":       precipitation(payload.Snow),
		"latitude":          latitude,
		"longitude":         longitude,
		"observed_at":       time.Unix(payload.ObservedAt, 0).UTC(),
		"generated_at":      time.Now().UTC(),
		"cached":            false,
		"cache_ttl_seconds": h.cfg.WeatherCacheTTLSeconds,
	}, nil
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

func boundaryCentroid(boundary json.RawMessage) (latitude, longitude float64, ok bool) {
	var geometry struct {
		Type        string          `json:"type"`
		Coordinates json.RawMessage `json:"coordinates"`
	}
	if err := json.Unmarshal(boundary, &geometry); err != nil {
		return 0, 0, false
	}
	var points [][2]float64
	switch strings.ToLower(geometry.Type) {
	case "polygon":
		points = polygonPoints(geometry.Coordinates)
	case "feature":
		var feature struct {
			Geometry json.RawMessage `json:"geometry"`
		}
		if err := json.Unmarshal(boundary, &feature); err != nil {
			return 0, 0, false
		}
		return boundaryCentroid(feature.Geometry)
	default:
		return 0, 0, false
	}
	if len(points) == 0 {
		return 0, 0, false
	}
	var longitudeSum, latitudeSum float64
	for _, point := range points {
		longitudeSum += point[0]
		latitudeSum += point[1]
	}
	return latitudeSum / float64(len(points)), longitudeSum / float64(len(points)), true
}

func polygonPoints(raw json.RawMessage) [][2]float64 {
	var rings [][][]float64
	if err := json.Unmarshal(raw, &rings); err != nil || len(rings) == 0 {
		return nil
	}
	points := make([][2]float64, 0, len(rings[0]))
	for _, point := range rings[0] {
		if len(point) < 2 {
			continue
		}
		points = append(points, [2]float64{point[0], point[1]})
	}
	return points
}

func openWeatherAPIKey(cfg *appConfig) string {
	if strings.TrimSpace(cfg.OpenWeatherAPIKey) != "" {
		return strings.TrimSpace(cfg.OpenWeatherAPIKey)
	}
	return strings.TrimSpace(cfg.OpenWeatherMapAPIKey)
}

func valueOrDefault(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func weatherCondition(payload *openWeatherResponse) (main, description string) {
	if len(payload.Weather) == 0 {
		return "unknown", "unknown"
	}
	return payload.Weather[0].Main, payload.Weather[0].Description
}

func precipitation(values map[string]float64) float64 {
	if values == nil {
		return 0
	}
	if value, ok := values["1h"]; ok {
		return value
	}
	return values["3h"]
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
