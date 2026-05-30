package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"api2agent/services/data-plane/internal/adapters"
	"api2agent/services/data-plane/internal/events"
	"api2agent/services/data-plane/internal/protocol"
	"api2agent/services/data-plane/internal/snapshots"
)

func TestExecuteGoldenPath(t *testing.T) {
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("format") != "json" {
			t.Fatalf("expected format=json query, got %q", r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	snapshot := &snapshots.Snapshot{
		SnapshotVersion:   "snapshot_test_v1",
		SnapshotFetchedAt: time.Date(2026, 5, 30, 0, 0, 0, 0, time.UTC),
		SnapshotTTL:       "24h",
		SnapshotSource:    "pull",
		Capabilities: []snapshots.Capability{{
			ID:      "network.public_ip.get",
			Version: "0.1-migrated",
			Name:    "Public IP Lookup",
		}},
		Providers: []snapshots.ProviderCandidate{{
			ID:                "ipify_public_ip_v1",
			CapabilityID:      "network.public_ip.get",
			CapabilityVersion: "0.1-migrated",
			ProviderID:        "ipify",
			ProviderVersion:   "1.0.0",
			MappingVersion:    "1.0.0",
			ToolID:            "get_public_ip",
			Regions:           []string{"global"},
			GeoAffinity:       "global",
			Metadata:          map[string]string{"base_url": providerServer.URL},
		}},
		RoutingPolicy: snapshots.RoutingPolicy{
			Strategy:    "first",
			RoutingMode: "deterministic",
		},
	}
	writer := events.NewMemoryWriter()
	registry := adapters.NewRegistry()
	registry.Register("ipify", adapters.IpifyAdapter{Client: providerServer.Client()})
	handler := Handler{
		Snapshot: snapshot,
		Adapters: registry,
		Events:   writer,
	}
	mux := http.NewServeMux()
	handler.Register(mux)

	body := []byte(`{
		"project_id":"local",
		"capability_id":"network.public_ip.get",
		"capability_version":"0.1-migrated",
		"input":{},
		"execution_mode":"proxy",
		"timeout_budget_ms":5000
	}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !response.Success {
		t.Fatalf("expected success response: %+v", response)
	}
	if got := response.Output["ip"]; got != "203.0.113.10" {
		t.Fatalf("expected normalized ip output, got %#v", got)
	}
	if len(writer.Events) != 4 {
		t.Fatalf("expected 4 events, got %d", len(writer.Events))
	}
	if writer.Events[0].EventType != "request_context" {
		t.Fatalf("expected request_context first, got %s", writer.Events[0].EventType)
	}
	if writer.Events[1].EventType != "routing_decision" {
		t.Fatalf("expected routing_decision second, got %s", writer.Events[1].EventType)
	}
	decision, ok := writer.Events[1].Record.(protocol.RoutingDecision)
	if !ok {
		t.Fatalf("expected routing decision record, got %T", writer.Events[1].Record)
	}
	if decision.SnapshotVersion != "snapshot_test_v1" {
		t.Fatalf("expected snapshot version on decision, got %q", decision.SnapshotVersion)
	}
	if decision.RoutingMode != "deterministic" {
		t.Fatalf("expected deterministic routing mode, got %q", decision.RoutingMode)
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event record, got %T", writer.Events[2].Record)
	}
	if !usage.Success {
		t.Fatalf("expected successful usage event")
	}
	if usage.EventSequenceID == 0 {
		t.Fatalf("expected usage event sequence id")
	}
	if usage.RequestMetadata["snapshot_version"] != "snapshot_test_v1" {
		t.Fatalf("expected snapshot_version metadata, got %#v", usage.RequestMetadata)
	}
	if usage.RequestMetadata["execution_timeout_budget_ms"] == nil {
		t.Fatalf("expected timeout budget metadata, got %#v", usage.RequestMetadata)
	}
	if writer.Events[3].EventType != "decision_log" {
		t.Fatalf("expected decision_log fourth, got %s", writer.Events[3].EventType)
	}
}
