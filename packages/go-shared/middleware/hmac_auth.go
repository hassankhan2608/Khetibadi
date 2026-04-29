// HMAC verification middleware.
//
// Expected request headers:
//
//	X-User-ID:        <uuid>
//	X-HMAC-Signature: hex(HMAC-SHA256(key=HMAC_SECRET, msg="<user_id>:<unix_timestamp>"))
//	X-Timestamp:      <unix_seconds>
//
// Replay window: ±300 seconds from server time.
//
// On success the verified user ID is stored on the Gin context under
// ContextKeyUserID. On failure the request is aborted with 401 and the
// canonical error envelope {"error": "unauthorized"}.
package middleware

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// HMAC header names and the Gin context key for the verified user ID.
const (
	HeaderUserID     = "X-User-ID"
	HeaderSignature  = "X-HMAC-Signature"
	HeaderTimestamp  = "X-Timestamp"
	ContextKeyUserID = "user_id"

	// ReplayWindow is the maximum permitted clock skew between client and
	// server. Changing this value requires a coordinated update across every
	// HMAC implementation in the monorepo (Go middleware + Python adapters).
	ReplayWindow = 300 * time.Second
)

// nowFunc is injectable for tests. Production code uses time.Now.
var nowFunc = time.Now

// HMACAuthConfig configures the HMAC middleware. Secret is loaded from the
// HMAC_SECRET environment variable when not supplied explicitly, matching the
// shared-package contract.
type HMACAuthConfig struct {
	Secret string
}

// HMACAuth returns the configured Gin middleware.
//
// If cfg.Secret is empty, the HMAC_SECRET environment variable is read at
// middleware construction time. Construction panics if no secret is
// configured because running without HMAC verification would be a silent
// security regression.
func HMACAuth(cfg HMACAuthConfig) gin.HandlerFunc {
	secret := cfg.Secret
	if secret == "" {
		secret = os.Getenv("HMAC_SECRET")
	}
	if secret == "" {
		panic("middleware.HMACAuth: HMAC_SECRET is not configured")
	}
	secretBytes := []byte(secret)

	return func(c *gin.Context) {
		userID := c.GetHeader(HeaderUserID)
		signature := c.GetHeader(HeaderSignature)
		timestamp := c.GetHeader(HeaderTimestamp)
		if userID == "" || signature == "" || timestamp == "" {
			abort(c)
			return
		}

		ts, err := strconv.ParseInt(timestamp, 10, 64)
		if err != nil {
			abort(c)
			return
		}

		skew := nowFunc().Unix() - ts
		if skew < 0 {
			skew = -skew
		}
		if time.Duration(skew)*time.Second > ReplayWindow {
			abort(c)
			return
		}

		mac := hmac.New(sha256.New, secretBytes)
		mac.Write([]byte(userID + ":" + timestamp))
		expected := hex.EncodeToString(mac.Sum(nil))

		gotSig, err := hex.DecodeString(signature)
		if err != nil {
			abort(c)
			return
		}
		expectedBytes, err := hex.DecodeString(expected)
		if err != nil {
			abort(c)
			return
		}
		if !hmac.Equal(gotSig, expectedBytes) {
			abort(c)
			return
		}

		c.Set(ContextKeyUserID, userID)
		c.Next()
	}
}

func abort(c *gin.Context) {
	c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
		"error":   "unauthorized",
		"message": "invalid or missing HMAC credentials",
	})
}

// Sign produces the canonical HMAC signature for the given user ID and
// timestamp. Exported so that internal callers (workers issuing service-to-
// service requests) and tests can construct valid signatures without
// duplicating the algorithm.
func Sign(secret, userID string, timestamp int64) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(userID + ":" + strconv.FormatInt(timestamp, 10)))
	return hex.EncodeToString(mac.Sum(nil))
}

// UserIDFrom returns the verified user ID stored on the Gin context by
// HMACAuth. Returns an empty string if the middleware was not mounted.
func UserIDFrom(c *gin.Context) string {
	if v, ok := c.Get(ContextKeyUserID); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}
