package middleware

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func init() { gin.SetMode(gin.TestMode) }

func TestRequestID_GeneratesWhenMissing(t *testing.T) {
	r := gin.New()
	r.Use(RequestID())
	var got string
	r.GET("/", func(c *gin.Context) {
		got = RequestIDFrom(c)
		c.Status(http.StatusOK)
	})

	w := httptest.NewRecorder()
	req := httptest.NewRequestWithContext(context.Background(), http.MethodGet, "/", http.NoBody)
	r.ServeHTTP(w, req)

	require.NotEmpty(t, got)
	require.Equal(t, got, w.Header().Get(HeaderRequestID))
}

func TestRequestID_PropagatesIncoming(t *testing.T) {
	r := gin.New()
	r.Use(RequestID())
	var got string
	r.GET("/", func(c *gin.Context) {
		got = RequestIDFrom(c)
		c.Status(http.StatusOK)
	})

	w := httptest.NewRecorder()
	req := httptest.NewRequestWithContext(context.Background(), http.MethodGet, "/", http.NoBody)
	req.Header.Set(HeaderRequestID, "rid-1234")
	r.ServeHTTP(w, req)

	require.Equal(t, "rid-1234", got)
	require.Equal(t, "rid-1234", w.Header().Get(HeaderRequestID))
}
