// Package pagination parses page/limit query parameters into a normalised
// Page struct usable by repository layers.
package pagination

import (
	"strconv"
)

const (
	// DefaultLimit is used when the client omits the `limit` query parameter.
	DefaultLimit = 20
	// MaxLimit clamps abusive limit values without returning an error.
	MaxLimit = 100
	// DefaultPage is used when the client omits the `page` query parameter or
	// supplies a value < 1.
	DefaultPage = 1
)

// Page describes a normalised pagination request.
type Page struct {
	Page   int
	Limit  int
	Offset int
}

// QueryReader is the minimal interface satisfied by *gin.Context.Query, kept
// abstract so that the pagination package remains framework-agnostic and
// trivially testable.
type QueryReader interface {
	Query(key string) string
}

// Parse reads `page` and `limit` query parameters from r and returns a
// normalised Page. Invalid integers fall back to defaults; limits above
// MaxLimit are clamped silently.
func Parse(r QueryReader) Page {
	page := parseIntDefault(r.Query("page"), DefaultPage)
	if page < 1 {
		page = DefaultPage
	}
	limit := parseIntDefault(r.Query("limit"), DefaultLimit)
	switch {
	case limit < 1:
		limit = DefaultLimit
	case limit > MaxLimit:
		limit = MaxLimit
	}
	return Page{
		Page:   page,
		Limit:  limit,
		Offset: (page - 1) * limit,
	}
}

func parseIntDefault(raw string, def int) int {
	if raw == "" {
		return def
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		return def
	}
	return v
}
