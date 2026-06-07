package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/khetibadi/go-shared/middleware"
)

const testHMACSecret = "test-hmac-secret-minimum-32-bytes"

func newTestRouter() *gin.Engine {
	gin.SetMode(gin.TestMode)
	h := newAuthHandler(&appConfig{
		JWTSecret:     "test-jwt-secret-minimum-32-bytes",
		JWTAccessTTL:  "15m",
		JWTRefreshTTL: "168h",
		HMACSecret:    testHMACSecret,
	})
	r := gin.New()
	h.registerRoutes(r)
	return r
}

func postJSON(t *testing.T, r http.Handler, path string, body map[string]string, token string) *httptest.ResponseRecorder {
	t.Helper()
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func patchJSON(t *testing.T, r http.Handler, path string, body map[string]string, token string) *httptest.ResponseRecorder {
	t.Helper()
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}
	req := httptest.NewRequest(http.MethodPatch, path, bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func registerUser(t *testing.T, r http.Handler, email string, phone string) string {
	t.Helper()
	response := postJSON(t, r, "/auth/register", map[string]string{
		"email":    email,
		"name":     "Test Farmer",
		"password": "Password1",
		"phone":    phone,
	}, "")
	if response.Code != http.StatusCreated {
		t.Fatalf("register status = %d, body = %s", response.Code, response.Body.String())
	}
	var body struct {
		Data struct {
			AccessToken string `json:"access_token"`
		} `json:"data"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode register response: %v", err)
	}
	return body.Data.AccessToken
}

func serviceHeaders() http.Header {
	timestamp := time.Now().Unix()
	headers := http.Header{}
	headers.Set(middleware.HeaderUserID, "whatsapp-bridge")
	headers.Set(middleware.HeaderTimestamp, ""+strconvFormat(timestamp))
	headers.Set(middleware.HeaderSignature, middleware.Sign(testHMACSecret, "whatsapp-bridge", timestamp))
	return headers
}

func strconvFormat(timestamp int64) string {
	return strconv.FormatInt(timestamp, 10)
}

func TestNormalizePhoneNumber(t *testing.T) {
	t.Parallel()
	cases := map[string]string{
		"+91 98765 43210": "+919876543210",
		"9876543210":      "+919876543210",
		"919876543210":    "+919876543210",
	}
	for input, want := range cases {
		got, ok := normalizePhoneNumber(input)
		if !ok || got != want {
			t.Fatalf("normalizePhoneNumber(%q) = %q, %v; want %q, true", input, got, ok, want)
		}
	}
	invalid := []string{"abc", "+", "12345", "+0012345678", "98765x43210"}
	for _, input := range invalid {
		if got, ok := normalizePhoneNumber(input); ok || got != "" {
			t.Fatalf("normalizePhoneNumber(%q) = %q, %v; want empty, false", input, got, ok)
		}
	}
}

func TestRegisterWithPhoneReturnsNormalizedPublicUser(t *testing.T) {
	r := newTestRouter()
	response := postJSON(t, r, "/auth/register", map[string]string{
		"email":    "phone@example.com",
		"name":     "Phone Farmer",
		"password": "Password1",
		"phone":    "9876543210",
	}, "")

	if response.Code != http.StatusCreated {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	var body struct {
		Data struct {
			User struct {
				Phone string `json:"phone"`
			} `json:"user"`
		} `json:"data"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body.Data.User.Phone != "+919876543210" {
		t.Fatalf("phone = %q", body.Data.User.Phone)
	}
}

func TestRegisterRejectsDuplicatePhone(t *testing.T) {
	r := newTestRouter()
	registerUser(t, r, "first@example.com", "+919876543210")
	response := postJSON(t, r, "/auth/register", map[string]string{
		"email":    "second@example.com",
		"name":     "Second Farmer",
		"password": "Password1",
		"phone":    "9876543210",
	}, "")

	if response.Code != http.StatusConflict {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if !bytes.Contains(response.Body.Bytes(), []byte("phone_taken")) {
		t.Fatalf("expected phone_taken body, got %s", response.Body.String())
	}
}

func TestRegisterRejectsInvalidPhone(t *testing.T) {
	r := newTestRouter()
	response := postJSON(t, r, "/auth/register", map[string]string{
		"email":    "invalid-phone@example.com",
		"name":     "Invalid Farmer",
		"password": "Password1",
		"phone":    "not-a-phone",
	}, "")

	if response.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
}

func TestUpdateProfilePhone(t *testing.T) {
	r := newTestRouter()
	token := registerUser(t, r, "update@example.com", "")
	response := patchJSON(t, r, "/auth/profile", map[string]string{"phone": "9876543210"}, token)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if !bytes.Contains(response.Body.Bytes(), []byte("+919876543210")) {
		t.Fatalf("expected normalized phone, got %s", response.Body.String())
	}
}

func TestInternalLookupByPhone(t *testing.T) {
	r := newTestRouter()
	registerUser(t, r, "lookup@example.com", "+919876543210")
	req := httptest.NewRequest(http.MethodGet, "/internal/users/by-phone?phone=%2B919876543210", nil)
	req.Header = serviceHeaders()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("lookup@example.com")) {
		t.Fatalf("expected lookup user, got %s", w.Body.String())
	}
}

func TestInternalLookupRejectsUnauthorizedCaller(t *testing.T) {
	r := newTestRouter()
	req := httptest.NewRequest(http.MethodGet, "/internal/users/by-phone?phone=%2B919876543210", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
}

func TestInternalLookupReturnsNotFound(t *testing.T) {
	r := newTestRouter()
	req := httptest.NewRequest(http.MethodGet, "/internal/users/by-phone?phone=%2B919876543210", nil)
	req.Header = serviceHeaders()
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d, body = %s", w.Code, w.Body.String())
	}
}
