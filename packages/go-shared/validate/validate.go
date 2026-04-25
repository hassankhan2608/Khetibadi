// Package validate exposes a process-wide go-playground/validator/v10 instance
// configured with sensible defaults for the Khetibadi codebase.
package validate

import (
	"reflect"
	"strings"
	"sync"

	"github.com/go-playground/validator/v10"
)

var (
	instance *validator.Validate
	once     sync.Once
)

// V returns the shared validator instance. It is safe for concurrent use.
//
// The validator is configured to use the `json` struct tag for field names so
// that error messages reference wire-level identifiers rather than Go field
// names.
func V() *validator.Validate {
	once.Do(func() {
		v := validator.New(validator.WithRequiredStructEnabled())
		v.RegisterTagNameFunc(func(fld reflect.StructField) string {
			name := strings.SplitN(fld.Tag.Get("json"), ",", 2)[0]
			if name == "-" {
				return ""
			}
			return name
		})
		instance = v
	})
	return instance
}

// Struct validates a struct using the shared validator instance.
func Struct(s any) error {
	return V().Struct(s)
}
