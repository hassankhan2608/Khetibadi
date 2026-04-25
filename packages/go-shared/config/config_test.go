package config

import (
	"testing"

	"github.com/stretchr/testify/require"
)

type sampleConfig struct {
	Host     string `envconfig:"HOST" default:"localhost"`
	Port     int    `envconfig:"PORT" default:"8080"`
	Required string `envconfig:"REQUIRED" required:"true"`
}

func TestLoad_PopulatesFieldsFromEnv(t *testing.T) {
	t.Setenv("APP_HOST", "example.com")
	t.Setenv("APP_PORT", "9090")
	t.Setenv("APP_REQUIRED", "value")

	var cfg sampleConfig
	require.NoError(t, Load("APP", &cfg))
	require.Equal(t, "example.com", cfg.Host)
	require.Equal(t, 9090, cfg.Port)
	require.Equal(t, "value", cfg.Required)
}

func TestLoad_AppliesDefaultsWhenMissing(t *testing.T) {
	t.Setenv("APP_REQUIRED", "value")

	var cfg sampleConfig
	require.NoError(t, Load("APP", &cfg))
	require.Equal(t, "localhost", cfg.Host)
	require.Equal(t, 8080, cfg.Port)
}

func TestLoad_ReturnsErrorWhenRequiredMissing(t *testing.T) {
	var cfg sampleConfig
	err := Load("APP", &cfg)
	require.Error(t, err)
	require.Contains(t, err.Error(), "REQUIRED")
}
