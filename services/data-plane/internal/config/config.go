package config

import "os"

type Config struct {
	Addr         string
	SnapshotPath string
	EventDir     string
	ProjectKey   string
}

func FromEnv() Config {
	cfg := Config{
		Addr:         getenv("API2AGENT_DATAPLANE_ADDR", ":8080"),
		SnapshotPath: getenv("API2AGENT_SNAPSHOT", "testdata/snapshots/network.public_ip.get.json"),
		EventDir:     getenv("API2AGENT_EVENT_DIR", ".api2agent/events"),
		ProjectKey:   os.Getenv("API2AGENT_PROJECT_KEY"),
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
