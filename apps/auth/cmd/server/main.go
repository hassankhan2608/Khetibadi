// Package main wires the auth service and public API gateway.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
	"golang.org/x/crypto/bcrypt"

	"github.com/khetibadi/go-shared/config"
	"github.com/khetibadi/go-shared/middleware"
	"github.com/khetibadi/go-shared/response"
)

const (
	serviceName    = "auth"
	shutdownGrace  = 15 * time.Second
	readHdrTimeout = 10 * time.Second
	bcryptCost     = 12

	refreshCookieName = "refresh_token"

	farmRoutePrefix     = "/farms"
	marketRoutePrefix   = "/market"
	mlCropRoutePrefix   = "/ml/crop"
	mlVisionRoutePrefix = "/ml/vision"
	aiChatRoutePrefix   = "/ai/chat"

	gatewayErrorCode    = "bad_gateway"
	gatewayErrorMessage = "downstream service unavailable"
	configErrorCode     = "gateway_configuration_error"
	configErrorMessage  = "gateway signing secret is not configured"
	invalidCredsMessage = "email or password is incorrect"
)

type appConfig struct {
	Port               string `envconfig:"PORT" default:"8000"`
	Env                string `envconfig:"APP_ENV" default:"development"`
	LogLevel           string `envconfig:"LOG_LEVEL" default:"info"`
	JWTSecret          string `envconfig:"JWT_SECRET" default:"dev-jwt-secret-change-me-minimum-32-bytes"`
	JWTAccessTTL       string `envconfig:"JWT_ACCESS_TTL" default:"15m"`
	JWTRefreshTTL      string `envconfig:"JWT_REFRESH_TTL" default:"168h"`
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

type user struct {
	ID           string    `json:"id"`
	Email        string    `json:"email"`
	Name         string    `json:"name"`
	PasswordHash []byte    `json:"-"`
	CreatedAt    time.Time `json:"created_at"`
}

type refreshToken struct {
	Hash      []byte
	UserID    string
	FamilyID  string
	ExpiresAt time.Time
	Revoked   bool
}

type authStore struct {
	mu             sync.RWMutex
	usersByEmail   map[string]*user
	usersByID      map[string]*user
	refreshByPlain map[string]*refreshToken
}

type authHandler struct {
	store      *authStore
	jwtSecret  []byte
	accessTTL  time.Duration
	refreshTTL time.Duration
}

type registerRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required"`
	Name     string `json:"name" binding:"required"`
}

type loginRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required"`
}

type passwordRequest struct {
	CurrentPassword string `json:"current_password" binding:"required"`
	NewPassword     string `json:"new_password" binding:"required"`
}

func main() {
	var cfg appConfig
	config.MustLoad("", &cfg)

	middleware.ConfigureGlobalLogger(cfg.LogLevel)

	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	auth := newAuthHandler(&cfg)
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(middleware.RequestID())
	r.Use(middleware.Logger())

	r.GET("/health", func(c *gin.Context) {
		response.OK(c, gin.H{"status": "ok", "service": serviceName}, nil)
	})
	auth.registerRoutes(r)
	registerGatewayRoutes(r, auth.jwtAuth(), []gatewayRoute{
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

func newAuthStore() *authStore {
	return &authStore{
		usersByEmail:   make(map[string]*user),
		usersByID:      make(map[string]*user),
		refreshByPlain: make(map[string]*refreshToken),
	}
}

func newAuthHandler(cfg *appConfig) *authHandler {
	accessTTL, err := time.ParseDuration(cfg.JWTAccessTTL)
	if err != nil {
		log.Fatal().Err(err).Msg("invalid JWT_ACCESS_TTL")
	}
	refreshTTL, err := time.ParseDuration(cfg.JWTRefreshTTL)
	if err != nil {
		log.Fatal().Err(err).Msg("invalid JWT_REFRESH_TTL")
	}
	return &authHandler{
		store:      newAuthStore(),
		jwtSecret:  []byte(cfg.JWTSecret),
		accessTTL:  accessTTL,
		refreshTTL: refreshTTL,
	}
}

func (h *authHandler) registerRoutes(r *gin.Engine) {
	r.POST("/auth/register", h.register)
	r.POST("/auth/login", h.login)
	r.POST("/auth/refresh", h.refresh)
	r.POST("/auth/logout", h.logout)
	r.PUT("/auth/password", h.jwtAuth(), h.changePassword)
}

func (h *authHandler) register(c *gin.Context) {
	var req registerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	req.Email = strings.ToLower(strings.TrimSpace(req.Email))
	if !validPassword(req.Password) {
		response.Error(c, http.StatusUnprocessableEntity, response.CodeValidation, "password must be at least 8 characters with one uppercase letter and one digit")
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcryptCost)
	if err != nil {
		response.Error(c, http.StatusInternalServerError, response.CodeInternal, "failed to secure password")
		return
	}
	now := time.Now().UTC()
	u := &user{ID: uuid.NewString(), Email: req.Email, Name: strings.TrimSpace(req.Name), PasswordHash: hash, CreatedAt: now}
	h.store.mu.Lock()
	if _, exists := h.store.usersByEmail[u.Email]; exists {
		h.store.mu.Unlock()
		response.Error(c, http.StatusConflict, response.CodeEmailTaken, "a user with that email already exists")
		return
	}
	h.store.usersByEmail[u.Email] = u
	h.store.usersByID[u.ID] = u
	h.store.mu.Unlock()
	response.Created(c, gin.H{"user": publicUser(u)})
}

func (h *authHandler) login(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	email := strings.ToLower(strings.TrimSpace(req.Email))
	h.store.mu.RLock()
	u := h.store.usersByEmail[email]
	h.store.mu.RUnlock()
	if u == nil || bcrypt.CompareHashAndPassword(u.PasswordHash, []byte(req.Password)) != nil {
		response.Error(c, http.StatusUnauthorized, response.CodeInvalidCreds, invalidCredsMessage)
		return
	}
	h.issueSession(c, u, uuid.NewString())
}

func (h *authHandler) refresh(c *gin.Context) {
	plain, err := c.Cookie(refreshCookieName)
	if err != nil || plain == "" {
		response.Error(c, http.StatusUnauthorized, response.CodeTokenInvalid, "refresh token is missing")
		return
	}
	h.store.mu.Lock()
	rt := h.store.refreshByPlain[plain]
	if rt == nil || bcrypt.CompareHashAndPassword(rt.Hash, []byte(plain)) != nil || time.Now().After(rt.ExpiresAt) {
		h.store.mu.Unlock()
		response.Error(c, http.StatusUnauthorized, response.CodeTokenInvalid, "refresh token is invalid")
		return
	}
	if rt.Revoked {
		for _, candidate := range h.store.refreshByPlain {
			if candidate.FamilyID == rt.FamilyID {
				candidate.Revoked = true
			}
		}
		h.store.mu.Unlock()
		response.Error(c, http.StatusUnauthorized, response.CodeReplayDetected, "refresh token reuse detected")
		return
	}
	rt.Revoked = true
	u := h.store.usersByID[rt.UserID]
	familyID := rt.FamilyID
	h.store.mu.Unlock()
	if u == nil {
		response.Error(c, http.StatusUnauthorized, response.CodeTokenInvalid, "refresh token is invalid")
		return
	}
	h.issueSession(c, u, familyID)
}

func (h *authHandler) logout(c *gin.Context) {
	plain, err := c.Cookie(refreshCookieName)
	if err == nil && plain != "" {
		h.store.mu.Lock()
		if rt := h.store.refreshByPlain[plain]; rt != nil {
			rt.Revoked = true
		}
		h.store.mu.Unlock()
	}
	clearRefreshCookie(c)
	response.NoContent(c)
}

func (h *authHandler) changePassword(c *gin.Context) {
	userID := middleware.UserIDFrom(c)
	var req passwordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.Error(c, http.StatusBadRequest, response.CodeValidation, err.Error())
		return
	}
	if !validPassword(req.NewPassword) {
		response.Error(c, http.StatusUnprocessableEntity, response.CodeValidation, "password must be at least 8 characters with one uppercase letter and one digit")
		return
	}
	h.store.mu.Lock()
	u := h.store.usersByID[userID]
	if u == nil || bcrypt.CompareHashAndPassword(u.PasswordHash, []byte(req.CurrentPassword)) != nil {
		h.store.mu.Unlock()
		response.Error(c, http.StatusUnauthorized, response.CodeInvalidCreds, invalidCredsMessage)
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcryptCost)
	if err != nil {
		h.store.mu.Unlock()
		response.Error(c, http.StatusInternalServerError, response.CodeInternal, "failed to secure password")
		return
	}
	u.PasswordHash = hash
	h.store.mu.Unlock()
	response.OK(c, gin.H{"changed": true}, nil)
}

func (h *authHandler) issueSession(c *gin.Context, u *user, familyID string) {
	accessToken, err := h.signAccessToken(u)
	if err != nil {
		response.Error(c, http.StatusInternalServerError, response.CodeInternal, "failed to issue access token")
		return
	}
	plain, err := randomHex(32)
	if err != nil {
		response.Error(c, http.StatusInternalServerError, response.CodeInternal, "failed to issue refresh token")
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(plain), bcryptCost)
	if err != nil {
		response.Error(c, http.StatusInternalServerError, response.CodeInternal, "failed to secure refresh token")
		return
	}
	expiresAt := time.Now().UTC().Add(h.refreshTTL)
	h.store.mu.Lock()
	h.store.refreshByPlain[plain] = &refreshToken{Hash: hash, UserID: u.ID, FamilyID: familyID, ExpiresAt: expiresAt}
	h.store.mu.Unlock()
	setRefreshCookie(c, plain, h.refreshTTL)
	response.OK(c, gin.H{"access_token": accessToken, "token_type": "Bearer", "expires_in": int(h.accessTTL.Seconds()), "user": publicUser(u)}, nil)
}

func (h *authHandler) signAccessToken(u *user) (string, error) {
	now := time.Now().UTC()
	claims := jwt.MapClaims{
		"sub":   u.ID,
		"email": u.Email,
		"iat":   now.Unix(),
		"exp":   now.Add(h.accessTTL).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(h.jwtSecret)
}

func (h *authHandler) jwtAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		tokenText := bearerToken(c.GetHeader("Authorization"))
		if tokenText == "" {
			response.Error(c, http.StatusUnauthorized, response.CodeUnauthorized, "missing bearer token")
			return
		}
		claims := jwt.MapClaims{}
		token, err := jwt.ParseWithClaims(tokenText, claims, func(token *jwt.Token) (any, error) {
			if token.Method != jwt.SigningMethodHS256 {
				return nil, errors.New("unexpected JWT signing method")
			}
			return h.jwtSecret, nil
		})
		if err != nil || token == nil || !token.Valid {
			response.Error(c, http.StatusUnauthorized, response.CodeTokenInvalid, "access token is invalid")
			return
		}
		userID, hasUserID := claims["sub"].(string)
		email, hasEmail := claims["email"].(string)
		if !hasUserID || !hasEmail || userID == "" || email == "" {
			response.Error(c, http.StatusUnauthorized, response.CodeTokenInvalid, "access token is invalid")
			return
		}
		h.store.mu.RLock()
		_, exists := h.store.usersByID[userID]
		h.store.mu.RUnlock()
		if !exists {
			response.Error(c, http.StatusUnauthorized, response.CodeTokenInvalid, "access token is invalid")
			return
		}
		c.Set(middleware.ContextKeyUserID, userID)
		c.Next()
	}
}

func registerGatewayRoutes(r *gin.Engine, auth gin.HandlerFunc, routes []gatewayRoute) {
	for _, route := range routes {
		handler := newReverseProxyHandler(route)
		r.Any(route.Prefix, auth, handler)
		r.Any(route.Prefix+"/*proxyPath", auth, handler)
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
			log.Error().Err(err).Str("service", route.Service).Str("method", req.Method).Str("path", req.URL.Path).Msg("gateway proxy failed")
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

func publicUser(u *user) gin.H {
	return gin.H{"id": u.ID, "email": u.Email, "name": u.Name, "created_at": u.CreatedAt}
}

func validPassword(password string) bool {
	if len(password) < 8 {
		return false
	}
	hasUpper := false
	hasDigit := false
	for _, r := range password {
		switch {
		case r >= 'A' && r <= 'Z':
			hasUpper = true
		case r >= '0' && r <= '9':
			hasDigit = true
		}
	}
	return hasUpper && hasDigit
}

func randomHex(size int) (string, error) {
	b := make([]byte, size)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func bearerToken(header string) string {
	parts := strings.Fields(header)
	if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
		return ""
	}
	return parts[1]
}

func setRefreshCookie(c *gin.Context, value string, ttl time.Duration) {
	c.SetCookieData(&http.Cookie{
		Name:     refreshCookieName,
		Value:    value,
		Path:     "/",
		MaxAge:   int(ttl.Seconds()),
		Expires:  time.Now().UTC().Add(ttl),
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
	})
}

func clearRefreshCookie(c *gin.Context) {
	c.SetCookieData(&http.Cookie{
		Name:     refreshCookieName,
		Value:    "",
		Path:     "/",
		MaxAge:   -1,
		Expires:  time.Unix(0, 0),
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
	})
}
