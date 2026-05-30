package config

import (
	"os"
	"strconv"
)

type Config struct {
	Addr                 string
	SnapshotPath         string
	SnapshotReloadPolicy string
	EventDir             string
	ProjectKey           string
	ProjectQuota         int
	CredentialConfigPath string
}

func FromEnv() Config {
	cfg := Config{
		Addr:                 getenv("API2AGENT_DATAPLANE_ADDR", ":8080"),
		SnapshotPath:         getenv("API2AGENT_SNAPSHOT", "testdata/snapshots/network.public_ip.get.json"),
		SnapshotReloadPolicy: getenv("API2AGENT_SNAPSHOT_RELOAD_POLICY", "startup_only"),
		EventDir:             getenv("API2AGENT_EVENT_DIR", ".api2agent/events"),
		ProjectKey:           os.Getenv("API2AGENT_PROJECT_KEY"),
		ProjectQuota:         getenvInt("API2AGENT_PROJECT_QUOTA", 0),
		CredentialConfigPath: os.Getenv("API2AGENT_CREDENTIAL_CONFIG"),
	}
	return cfg
}

func getenv(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}

func getenvInt(key string, fallback int) int {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed < 1 {
		return fallback
	}
	return parsed
}
