package response

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func newCtx() (*gin.Context, *httptest.ResponseRecorder) {
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	return c, w
}

func TestOK_WritesDataEnvelope(t *testing.T) {
	c, w := newCtx()
	OK(c, gin.H{"id": "u1"}, nil)

	require.Equal(t, http.StatusOK, w.Code)
	var got map[string]any
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &got))
	require.Contains(t, got, "data")
	require.NotContains(t, got, "meta")
}

func TestOK_WithMetaIncludesMeta(t *testing.T) {
	c, w := newCtx()
	OK(c, gin.H{"id": "u1"}, gin.H{"version": 1})

	var got map[string]any
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &got))
	require.Contains(t, got, "meta")
}

func TestPaginated_WritesPageMeta(t *testing.T) {
	c, w := newCtx()
	Paginated(c, []int{1, 2, 3}, PageMeta{Page: 1, Limit: 20, Total: 3})

	require.Equal(t, http.StatusOK, w.Code)
	require.Contains(t, w.Body.String(), `"page":1`)
	require.Contains(t, w.Body.String(), `"total":3`)
}

func TestError_AbortsWithCodeAndMessage(t *testing.T) {
	c, w := newCtx()
	Error(c, http.StatusBadRequest, CodeValidation, "bad input")

	require.Equal(t, http.StatusBadRequest, w.Code)
	require.True(t, c.IsAborted())
	require.JSONEq(t, `{"error":"validation_error","message":"bad input"}`, w.Body.String())
}

func TestCreated_Writes201(t *testing.T) {
	c, w := newCtx()
	Created(c, gin.H{"id": "u1"})
	require.Equal(t, http.StatusCreated, w.Code)
}

func TestNoContent_Writes204AndEmptyBody(t *testing.T) {
	r := gin.New()
	r.DELETE("/x", func(c *gin.Context) { NoContent(c) })
	w := httptest.NewRecorder()
	req := httptest.NewRequestWithContext(context.Background(), http.MethodDelete, "/x", http.NoBody)
	r.ServeHTTP(w, req)
	require.Equal(t, http.StatusNoContent, w.Code)
	require.Empty(t, w.Body.String())
}
