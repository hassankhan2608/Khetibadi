// Package middleware provides Gin middleware shared across all Go services.
package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// HeaderRequestID is the HTTP header used to propagate the request ID across
// service boundaries. The header value is also stored on the Gin context
// under ContextKeyRequestID for in-process consumers.
const (
	HeaderRequestID     = "X-Request-ID"
	ContextKeyRequestID = "request_id"
)

// RequestID returns middleware that ensures every request has a stable
// X-Request-ID header. If the client did not supply one, a UUIDv4 is
// generated. The value is mirrored to the response header so clients can
// correlate log entries.
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.GetHeader(HeaderRequestID)
		if id == "" {
			id = uuid.NewString()
		}
		c.Set(ContextKeyRequestID, id)
		c.Writer.Header().Set(HeaderRequestID, id)
		c.Next()
	}
}

// RequestIDFrom extracts the request ID from a Gin context. Returns an empty
// string if RequestID middleware was not mounted.
func RequestIDFrom(c *gin.Context) string {
	if v, ok := c.Get(ContextKeyRequestID); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}
