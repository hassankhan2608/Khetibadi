// Package response provides JSON response envelope helpers used by every
// Gin-based service in the monorepo.
//
// Envelope shapes:
//
//	Success            : {"data": <T>}
//	Success with meta  : {"data": <T>, "meta": <M>}
//	Paginated          : {"data": [...], "meta": {"page": 1, "limit": 20, "total": 100}}
//	Error              : {"error": "<code>", "message": "<human>"}
package response

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// PageMeta describes pagination metadata returned with list endpoints.
type PageMeta struct {
	Page  int   `json:"page"`
	Limit int   `json:"limit"`
	Total int64 `json:"total"`
}

// OK writes a 200 response with the standard envelope. Meta is omitted when nil.
func OK(c *gin.Context, data, meta any) {
	write(c, http.StatusOK, data, meta)
}

// Created writes a 201 response with the standard envelope.
func Created(c *gin.Context, data any) {
	write(c, http.StatusCreated, data, nil)
}

// NoContent writes a 204 response with no body.
func NoContent(c *gin.Context) {
	c.Status(http.StatusNoContent)
}

// Paginated writes a 200 response with pagination metadata.
func Paginated(c *gin.Context, data any, meta PageMeta) {
	write(c, http.StatusOK, data, meta)
}

// Error writes the canonical error envelope and aborts the request.
func Error(c *gin.Context, status int, code, message string) {
	c.AbortWithStatusJSON(status, gin.H{
		"error":   code,
		"message": message,
	})
}

func write(c *gin.Context, status int, data, meta any) {
	body := gin.H{"data": data}
	if meta != nil {
		body["meta"] = meta
	}
	c.JSON(status, body)
}
