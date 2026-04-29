package middleware

import (
	"time"

	"github.com/gin-gonic/gin"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// Logger returns middleware that emits one structured zerolog entry per
// completed request. The log level is INFO for 2xx/3xx and 4xx responses, and
// ERROR for 5xx responses so that operational dashboards can alert on real
// failures without noise from client errors.
func Logger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		raw := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()
		if raw != "" {
			path = path + "?" + raw
		}

		evt := log.Info()
		if status >= 500 {
			evt = log.Error()
		}
		evt.
			Str("method", c.Request.Method).
			Str("path", path).
			Int("status", status).
			Dur("latency", latency).
			Str("client_ip", c.ClientIP()).
			Str("request_id", RequestIDFrom(c)).
			Int("size", c.Writer.Size()).
			Msg("request")
	}
}

// ConfigureGlobalLogger applies sensible defaults for zerolog used by every
// service in this monorepo. It is intended to be called once from main().
//
// JSON output is used in containerised environments; humans running locally
// can pipe through `zerolog`'s console writer if they prefer.
func ConfigureGlobalLogger(level string) {
	zerolog.TimeFieldFormat = time.RFC3339Nano
	lvl, err := zerolog.ParseLevel(level)
	if err != nil || lvl == zerolog.NoLevel {
		lvl = zerolog.InfoLevel
	}
	zerolog.SetGlobalLevel(lvl)
}
