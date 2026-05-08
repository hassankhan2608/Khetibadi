// Package main is the entrypoint for the auth service.
//
// Phase 2 skeleton: structured logging, env-driven config, shared request ID
// and request logger middleware, a /health endpoint, and graceful shutdown.
// Domain handlers (register, login, refresh, logout) are wired in
// subsequent commits.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/rs/zerolog/log"

	"github.com/khetibadi/go-shared/config"
	"github.com/khetibadi/go-shared/middleware"
	"github.com/khetibadi/go-shared/response"
)

const (
	serviceName    = "auth"
	shutdownGrace  = 15 * time.Second
	readHdrTimeout = 10 * time.Second

	farmRoutePrefix     = "/farms"
	marketRoutePrefix   = "/market"
	mlCropRoutePrefix   = "/ml/crop"
	mlVisionRoutePrefix = "/ml/vision"
	aiChatRoutePrefix   = "/ai/chat"

	gatewayErrorCode    = "bad_gateway"
	gatewayErrorMessage = "downstream service unavailable"
	configErrorCode     = "gateway_configuration_error"
	configErrorMessage  = "gateway signing secret is not configured"
)

type appConfig struct {
	Port               string `envconfig:"PORT" default:"8000"`
	Env                string `envconfig:"APP_ENV" default:"development"`
	LogLevel           string `envconfig:"LOG_LEVEL" default:"info"`
	HMACSecret         string `envconfig:"HMAC_SECRET"`
	FarmServiceURL     string `envconfig:"FARM_SERVICE_URL" default:"http://farm-service:8001"`
	MarketServiceURL   string `envconfig:"MARKET_SERVICE_URL" default:"http://market-service:8002"`
	MLCropServiceURL   string `envconfig:"ML_CROP_SERVICE_URL" default:"http://ml-crop:8010"`
	MLVisionServiceURL string `envconfig:"ML_VISION_SERVICE_URL" default:"http://ml-vision:8011"`
	AIChatServiceURL   string `envconfig:"AI_CHAT_SERVICE_URL" default:"http://ai-chat:8012"`
}

type gatewayRoute struct {
	Prefix     string
	Service    string
	TargetURL  string
	HMACSecret string
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
	registerGatewayRoutes(r, []gatewayRoute{
		{Prefix: farmRoutePrefix, Service: "farm-service", TargetURL: cfg.FarmServiceURL, HMACSecret: cfg.HMACSecret},
		{Prefix: marketRoutePrefix, Service: "market-service", TargetURL: cfg.MarketServiceURL, HMACSecret: cfg.HMACSecret},
		{Prefix: mlCropRoutePrefix, Service: "ml-crop", TargetURL: cfg.MLCropServiceURL, HMACSecret: cfg.HMACSecret},
		{Prefix: mlVisionRoutePrefix, Service: "ml-vision", TargetURL: cfg.MLVisionServiceURL, HMACSecret: cfg.HMACSecret},
		{Prefix: aiChatRoutePrefix, Service: "ai-chat", TargetURL: cfg.AIChatServiceURL, HMACSecret: cfg.HMACSecret},
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

func registerGatewayRoutes(r *gin.Engine, routes []gatewayRoute) {
	for _, route := range routes {
		handler := newReverseProxyHandler(route)
		r.Any(route.Prefix, handler)
		r.Any(route.Prefix+"/*proxyPath", handler)
	}
}

func newReverseProxyHandler(route gatewayRoute) gin.HandlerFunc {
	target, err := url.Parse(route.TargetURL)
	if err != nil || target.Scheme == "" || target.Host == "" {
		log.Fatal().Err(err).Str("service", route.Service).Msg("invalid gateway target URL")
	}

	proxy := &httputil.ReverseProxy{
		Rewrite: func(req *httputil.ProxyRequest) {
			req.SetURL(target)
			req.SetXForwarded()
		},
		ErrorHandler: func(w http.ResponseWriter, req *http.Request, err error) {
			log.Error().
				Err(err).
				Str("service", route.Service).
				Str("method", req.Method).
				Str("path", req.URL.Path).
				Msg("gateway proxy failed")
			writeGatewayError(w, http.StatusBadGateway, gatewayErrorCode, gatewayErrorMessage)
		},
	}

	return func(c *gin.Context) {
		stripForwardedIdentity(c.Request.Header)
		if !signForwardedIdentity(c, route.HMACSecret) {
			return
		}
		proxy.ServeHTTP(c.Writer, c.Request)
	}
}

func stripForwardedIdentity(header http.Header) {
	header.Del(middleware.HeaderUserID)
	header.Del(middleware.HeaderSignature)
	header.Del(middleware.HeaderTimestamp)
}

func signForwardedIdentity(c *gin.Context, secret string) bool {
	userID := middleware.UserIDFrom(c)
	if userID == "" {
		return true
	}
	if secret == "" {
		response.Error(c, http.StatusInternalServerError, configErrorCode, configErrorMessage)
		return false
	}

	timestamp := time.Now().Unix()
	timestampText := strconv.FormatInt(timestamp, 10)
	c.Request.Header.Set(middleware.HeaderUserID, userID)
	c.Request.Header.Set(middleware.HeaderTimestamp, timestampText)
	c.Request.Header.Set(middleware.HeaderSignature, middleware.Sign(secret, userID, timestamp))
	return true
}

func writeGatewayError(w http.ResponseWriter, status int, code, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(gin.H{"error": code, "message": message}); err != nil {
		log.Error().Err(err).Msg("failed to write gateway error response")
	}
}
