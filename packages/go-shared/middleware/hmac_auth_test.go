package middleware

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

const testSecret = "test-secret-do-not-use-in-production"

func setupHMACRouter(t *testing.T) *gin.Engine {
	t.Helper()
	r := gin.New()
	r.Use(HMACAuth(HMACAuthConfig{Secret: testSecret}))
	r.GET("/protected", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"user_id": UserIDFrom(c)})
	})
	return r
}

func signedRequest(t *testing.T, userID string, ts int64) *http.Request {
	t.Helper()
	req := httptest.NewRequestWithContext(context.Background(), http.MethodGet, "/protected", http.NoBody)
	req.Header.Set(HeaderUserID, userID)
	req.Header.Set(HeaderTimestamp, strconv.FormatInt(ts, 10))
	req.Header.Set(HeaderSignature, Sign(testSecret, userID, ts))
	return req
}

func TestHMACAuth_ValidRequestSetsUserID(t *testing.T) {
	r := setupHMACRouter(t)
	ts := time.Now().Unix()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, signedRequest(t, "user-1", ts))

	require.Equal(t, http.StatusOK, w.Code)
	require.Contains(t, w.Body.String(), `"user_id":"user-1"`)
}

func TestHMACAuth_MissingHeadersRejected(t *testing.T) {
	r := setupHMACRouter(t)
	w := httptest.NewRecorder()
	req := httptest.NewRequestWithContext(context.Background(), http.MethodGet, "/protected", http.NoBody)
	r.ServeHTTP(w, req)

	require.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestHMACAuth_TamperedSignatureRejected(t *testing.T) {
	r := setupHMACRouter(t)
	ts := time.Now().Unix()
	req := signedRequest(t, "user-1", ts)
	req.Header.Set(HeaderSignature, "deadbeef")

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	require.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestHMACAuth_ReplayWindowEnforced(t *testing.T) {
	r := setupHMACRouter(t)

	// 301 seconds in the past — outside window.
	stale := time.Now().Add(-301 * time.Second).Unix()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, signedRequest(t, "user-1", stale))
	require.Equal(t, http.StatusUnauthorized, w.Code)

	// 299 seconds in the past — inside window.
	fresh := time.Now().Add(-299 * time.Second).Unix()
	w = httptest.NewRecorder()
	r.ServeHTTP(w, signedRequest(t, "user-1", fresh))
	require.Equal(t, http.StatusOK, w.Code)
}

func TestHMACAuth_FutureTimestampWithinWindowAccepted(t *testing.T) {
	r := setupHMACRouter(t)
	future := time.Now().Add(60 * time.Second).Unix()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, signedRequest(t, "user-1", future))
	require.Equal(t, http.StatusOK, w.Code)
}

func TestHMACAuth_NonNumericTimestampRejected(t *testing.T) {
	r := setupHMACRouter(t)
	req := httptest.NewRequestWithContext(context.Background(), http.MethodGet, "/protected", http.NoBody)
	req.Header.Set(HeaderUserID, "user-1")
	req.Header.Set(HeaderTimestamp, "notanint")
	req.Header.Set(HeaderSignature, Sign(testSecret, "user-1", time.Now().Unix()))

	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	require.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestHMACAuth_PanicsWithoutSecret(t *testing.T) {
	t.Setenv("HMAC_SECRET", "")
	require.Panics(t, func() {
		HMACAuth(HMACAuthConfig{})
	})
}
