// Package config loads service configuration from environment variables.
//
// It wraps kelseyhightower/envconfig to provide a single, consistent entry
// point for every Go service in the monorepo. Each service defines its own
// config struct (with `envconfig` tags) and calls Load to populate it.
package config

import (
	"fmt"

	"github.com/kelseyhightower/envconfig"
)

// Load populates spec from environment variables.
//
// spec must be a pointer to a struct whose fields are annotated with
// `envconfig` tags. The optional prefix is uppercased and prepended to every
// variable name. Pass an empty prefix to read top-level variables.
func Load(prefix string, spec any) error {
	if err := envconfig.Process(prefix, spec); err != nil {
		return fmt.Errorf("config.Load(%q): %w", prefix, err)
	}
	return nil
}

// MustLoad is the panicking variant of Load. It is intended for use in
// main.go during startup, where missing configuration is unrecoverable.
func MustLoad(prefix string, spec any) {
	if err := Load(prefix, spec); err != nil {
		panic(err)
	}
}
