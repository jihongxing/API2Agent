package main

import (
	"log"
	"net/http"

	"api2agent/services/data-plane/internal/adapters"
	"api2agent/services/data-plane/internal/config"
	"api2agent/services/data-plane/internal/events"
	"api2agent/services/data-plane/internal/httpapi"
	"api2agent/services/data-plane/internal/snapshots"
)

func main() {
	cfg := config.FromEnv()
	snapshot, err := snapshots.LoadFile(cfg.SnapshotPath)
	if err != nil {
		log.Fatalf("load snapshot: %v", err)
	}
	writer, err := events.NewJSONLWriter(cfg.EventDir)
	if err != nil {
		log.Fatalf("create event writer: %v", err)
	}
	registry := adapters.NewRegistry()
	registry.Register("ipify", adapters.IpifyAdapter{})

	mux := http.NewServeMux()
	handler := httpapi.Handler{
		Snapshot:   snapshot,
		Adapters:   registry,
		Events:     writer,
		ProjectKey: cfg.ProjectKey,
	}
	handler.Register(mux)

	log.Printf("api2agent data plane listening on %s", cfg.Addr)
	if err := http.ListenAndServe(cfg.Addr, mux); err != nil {
		log.Fatal(err)
	}
}
