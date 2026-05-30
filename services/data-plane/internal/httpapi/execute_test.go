package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"api2agent/services/data-plane/internal/adapters"
	"api2agent/services/data-plane/internal/conformance"
	"api2agent/services/data-plane/internal/credentials"
	"api2agent/services/data-plane/internal/events"
	"api2agent/services/data-plane/internal/protocol"
	"api2agent/services/data-plane/internal/snapshots"
)

func newTestSnapshot(providerURL string) *snapshots.Snapshot {
	return &snapshots.Snapshot{
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
			Metadata:          map[string]string{"base_url": providerURL},
		}},
		RoutingPolicy: snapshots.RoutingPolicy{
			Strategy:    "first",
			RoutingMode: "deterministic",
		},
	}
}

func newFailoverSnapshot(failingURL, fallbackURL string) *snapshots.Snapshot {
	snapshot := newTestSnapshot(failingURL)
	snapshot.Providers = []snapshots.ProviderCandidate{
		{
			ID:                "ipify_primary_v1",
			CapabilityID:      "network.public_ip.get",
			CapabilityVersion: "0.1-migrated",
			ProviderID:        "ipify",
			ProviderVersion:   "1.0.0",
			MappingVersion:    "1.0.0",
			ToolID:            "get_public_ip",
			Regions:           []string{"global"},
			GeoAffinity:       "global",
			Metadata:          map[string]string{"base_url": failingURL},
		},
		{
			ID:                "ipify_fallback_v1",
			CapabilityID:      "network.public_ip.get",
			CapabilityVersion: "0.1-migrated",
			ProviderID:        "ipify",
			ProviderVersion:   "1.0.0",
			MappingVersion:    "1.0.0",
			ToolID:            "get_public_ip",
			Regions:           []string{"global"},
			GeoAffinity:       "global",
			Metadata:          map[string]string{"base_url": fallbackURL},
		},
	}
	snapshot.RoutingPolicy.FailoverPolicy = &snapshots.FailoverPolicy{
		Enabled:              true,
		MaxAttempts:          2,
		RetryOnErrorTypes:    []string{"PROVIDER_ERROR", "TIMEOUT"},
		RetryOnStatusCodes:   []int{500, 502, 503, 504},
		AttemptTimeoutPolicy: "fixed",
	}
	return snapshot
}

func newTestHandler(snapshot *snapshots.Snapshot, client *http.Client) (Handler, *events.MemoryWriter) {
	writer := events.NewMemoryWriter()
	registry := adapters.NewRegistry()
	registry.Register("ipify", adapters.IpifyAdapter{Client: client})
	handler := Handler{
		Snapshot: snapshot,
		Adapters: registry,
		Events:   writer,
	}
	return handler, writer
}

type failingEventWriter struct {
	err error
}

func (w failingEventWriter) Write(ctx context.Context, eventType string, record any) (int64, error) {
	return 0, w.err
}

func executeBody(timeoutBudgetMS int) []byte {
	return []byte(fmt.Sprintf(`{
		"project_id":"local",
		"capability_id":"network.public_ip.get",
		"capability_version":"0.1-migrated",
		"input":{},
		"execution_mode":"proxy",
		"timeout_budget_ms":%d
	}`, timeoutBudgetMS))
}

func writeSnapshotFile(t *testing.T, path string, snapshot *snapshots.Snapshot) {
	t.Helper()
	data, err := json.MarshalIndent(snapshot, "", "  ")
	if err != nil {
		t.Fatalf("encode snapshot: %v", err)
	}
	if err := os.WriteFile(path, append(data, '\n'), 0o644); err != nil {
		t.Fatalf("write snapshot: %v", err)
	}
}

func TestHealthzReportsProtocolAndSnapshot(t *testing.T) {
	snapshot := newTestSnapshot("https://example.test")
	handler, _ := newTestHandler(snapshot, http.DefaultClient)
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var response HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Status != "ok" {
		t.Fatalf("expected ok status, got %q", response.Status)
	}
	if response.SchemaVersion != protocol.SchemaVersion {
		t.Fatalf("expected schema version %q, got %q", protocol.SchemaVersion, response.SchemaVersion)
	}
	if response.SnapshotVersion != "snapshot_test_v1" {
		t.Fatalf("expected snapshot version, got %q", response.SnapshotVersion)
	}
	if response.SnapshotExpired == nil || *response.SnapshotExpired {
		t.Fatalf("expected non-expired snapshot, got %#v", response.SnapshotExpired)
	}
	if response.SnapshotExpiresAt == nil {
		t.Fatalf("expected snapshot expiration timestamp")
	}
}

func TestHealthzReportsDegradedForExpiredSnapshot(t *testing.T) {
	snapshot := newTestSnapshot("https://example.test")
	snapshot.SnapshotFetchedAt = time.Date(2026, 5, 28, 0, 0, 0, 0, time.UTC)
	handler, _ := newTestHandler(snapshot, http.DefaultClient)
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var response HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Status != "degraded" {
		t.Fatalf("expected degraded status, got %q", response.Status)
	}
	if response.SnapshotExpired == nil || !*response.SnapshotExpired {
		t.Fatalf("expected expired snapshot, got %#v", response.SnapshotExpired)
	}
}

func TestReloadSnapshotUpdatesCurrentSnapshot(t *testing.T) {
	dir := t.TempDir()
	snapshotPath := filepath.Join(dir, "snapshot.json")
	snapshotV1 := newTestSnapshot("https://example.test")
	snapshotV1.SnapshotVersion = "snapshot_test_v1"
	snapshotV2 := newTestSnapshot("https://example.test")
	snapshotV2.SnapshotVersion = "snapshot_test_v2"
	writeSnapshotFile(t, snapshotPath, snapshotV1)

	handler, _ := newTestHandler(snapshotV1, http.DefaultClient)
	handler.SnapshotStore = NewSnapshotStore(snapshotPath, snapshotV1)
	handler.SnapshotReloadPolicy = "manual"
	mux := http.NewServeMux()
	handler.Register(mux)

	writeSnapshotFile(t, snapshotPath, snapshotV2)
	req := httptest.NewRequest(http.MethodPost, "/v1/admin/reload-snapshot", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected reload success, got %d: %s", rec.Code, rec.Body.String())
	}
	var reload ReloadSnapshotResponse
	if err := json.NewDecoder(rec.Body).Decode(&reload); err != nil {
		t.Fatalf("decode reload response: %v", err)
	}
	if !reload.Reloaded || reload.PreviousSnapshotVersion != "snapshot_test_v1" || reload.SnapshotVersion != "snapshot_test_v2" {
		t.Fatalf("unexpected reload response: %#v", reload)
	}

	healthReq := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	healthRec := httptest.NewRecorder()
	mux.ServeHTTP(healthRec, healthReq)
	var health HealthResponse
	if err := json.NewDecoder(healthRec.Body).Decode(&health); err != nil {
		t.Fatalf("decode health response: %v", err)
	}
	if health.SnapshotVersion != "snapshot_test_v2" {
		t.Fatalf("expected reloaded snapshot version, got %#v", health)
	}
}

func TestReloadSnapshotDisabledByDefault(t *testing.T) {
	handler, _ := newTestHandler(newTestSnapshot("https://example.test"), http.DefaultClient)
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/admin/reload-snapshot", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusConflict {
		t.Fatalf("expected reload disabled conflict, got %d: %s", rec.Code, rec.Body.String())
	}
}

func TestExecuteGoldenPath(t *testing.T) {
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("format") != "json" {
			t.Fatalf("expected format=json query, got %q", r.URL.RawQuery)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	snapshot := newTestSnapshot(providerServer.URL)
	handler, writer := newTestHandler(snapshot, providerServer.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	body := executeBody(5000)
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
	assertProtocolConformance(t, "RequestContext", writer.Events[0].Record)
	if writer.Events[1].EventType != "routing_decision" {
		t.Fatalf("expected routing_decision second, got %s", writer.Events[1].EventType)
	}
	assertProtocolConformance(t, "RoutingDecision", writer.Events[1].Record)
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
	assertProtocolConformance(t, "UsageEvent", usage)
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
	decisionLog, ok := writer.Events[3].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log record, got %T", writer.Events[3].Record)
	}
	assertProtocolConformance(t, "DecisionLog", decisionLog)
	if decisionLog.EventSequenceID == 0 {
		t.Fatalf("expected decision log event sequence id")
	}
}

func TestExecuteFailsClosedWhenSnapshotExpired(t *testing.T) {
	var providerCalls int32
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&providerCalls, 1)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	snapshot := newTestSnapshot(providerServer.URL)
	snapshot.SnapshotFetchedAt = time.Date(2026, 5, 28, 0, 0, 0, 0, time.UTC)
	handler, writer := newTestHandler(snapshot, providerServer.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d: %s", rec.Code, rec.Body.String())
	}
	if got := atomic.LoadInt32(&providerCalls); got != 0 {
		t.Fatalf("provider should not be called for expired snapshot, got %d calls", got)
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Success {
		t.Fatalf("expected failed response")
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "SNAPSHOT_EXPIRED" {
		t.Fatalf("expected SNAPSHOT_EXPIRED error, got %#v", response.Error)
	}
	if len(writer.Events) != 2 {
		t.Fatalf("expected request_context and decision_log only, got %d events", len(writer.Events))
	}
	if writer.Events[0].EventType != "request_context" || writer.Events[1].EventType != "decision_log" {
		t.Fatalf("unexpected event order: %#v", writer.Events)
	}
	assertProtocolConformance(t, "RequestContext", writer.Events[0].Record)
	decisionLog, ok := writer.Events[1].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log, got %T", writer.Events[1].Record)
	}
	assertProtocolConformance(t, "DecisionLog", decisionLog)
	if decisionLog.Outcome != "failure" {
		t.Fatalf("expected failure decision outcome, got %q", decisionLog.Outcome)
	}
	if len(decisionLog.UsageEventIDs) != 0 {
		t.Fatalf("expected no usage attempts, got %#v", decisionLog.UsageEventIDs)
	}
	if decisionLog.RoutingContext["error_type"] != "SNAPSHOT_EXPIRED" {
		t.Fatalf("expected snapshot error in decision log, got %#v", decisionLog.RoutingContext)
	}
}

func TestExecuteFailsClosedWhenSnapshotTTLInvalid(t *testing.T) {
	var providerCalls int32
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&providerCalls, 1)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	snapshot := newTestSnapshot(providerServer.URL)
	snapshot.SnapshotTTL = "not-a-duration"
	handler, writer := newTestHandler(snapshot, providerServer.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d: %s", rec.Code, rec.Body.String())
	}
	if got := atomic.LoadInt32(&providerCalls); got != 0 {
		t.Fatalf("provider should not be called for invalid snapshot ttl, got %d calls", got)
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "SNAPSHOT_INVALID" {
		t.Fatalf("expected SNAPSHOT_INVALID error, got %#v", response.Error)
	}
	if len(writer.Events) != 2 {
		t.Fatalf("expected request_context and decision_log only, got %d events", len(writer.Events))
	}
	decisionLog, ok := writer.Events[1].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log, got %T", writer.Events[1].Record)
	}
	if decisionLog.RoutingContext["error_type"] != "SNAPSHOT_INVALID" {
		t.Fatalf("expected snapshot invalid in decision log, got %#v", decisionLog.RoutingContext)
	}
}

func TestExecuteRequiresBearerWhenProjectKeyConfigured(t *testing.T) {
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	handler, _ := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	handler.ProjectKey = "secret"
	mux := http.NewServeMux()
	handler.Register(mux)

	missingAuth := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	missingAuthRec := httptest.NewRecorder()
	mux.ServeHTTP(missingAuthRec, missingAuth)
	if missingAuthRec.Code != http.StatusUnauthorized {
		t.Fatalf("expected missing bearer to return 401, got %d", missingAuthRec.Code)
	}

	invalidAuth := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	invalidAuth.Header.Set("Authorization", "Bearer wrong")
	invalidAuthRec := httptest.NewRecorder()
	mux.ServeHTTP(invalidAuthRec, invalidAuth)
	if invalidAuthRec.Code != http.StatusUnauthorized {
		t.Fatalf("expected invalid bearer to return 401, got %d", invalidAuthRec.Code)
	}

	validAuth := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	validAuth.Header.Set("Authorization", "Bearer secret")
	validAuthRec := httptest.NewRecorder()
	mux.ServeHTTP(validAuthRec, validAuth)
	if validAuthRec.Code != http.StatusOK {
		t.Fatalf("expected valid bearer to pass, got %d: %s", validAuthRec.Code, validAuthRec.Body.String())
	}
}

func TestExecuteProjectQuotaFailsClosedBeforeRouting(t *testing.T) {
	var providerCalls int32
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&providerCalls, 1)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	handler, writer := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	handler.Quota = NewQuotaGate(1)
	mux := http.NewServeMux()
	handler.Register(mux)

	firstReq := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	firstRec := httptest.NewRecorder()
	mux.ServeHTTP(firstRec, firstReq)
	if firstRec.Code != http.StatusOK {
		t.Fatalf("expected first request to pass, got %d: %s", firstRec.Code, firstRec.Body.String())
	}

	secondReq := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	secondRec := httptest.NewRecorder()
	mux.ServeHTTP(secondRec, secondReq)
	if secondRec.Code != http.StatusTooManyRequests {
		t.Fatalf("expected second request to return 429, got %d: %s", secondRec.Code, secondRec.Body.String())
	}
	if got := atomic.LoadInt32(&providerCalls); got != 1 {
		t.Fatalf("expected provider to be called only once, got %d calls", got)
	}
	var response ExecuteResponse
	if err := json.Unmarshal(secondRec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "QUOTA_EXCEEDED" {
		t.Fatalf("expected QUOTA_EXCEEDED error, got %#v", response.Error)
	}
	if len(writer.Events) != 6 {
		t.Fatalf("expected 6 events across two requests, got %d", len(writer.Events))
	}
	if writer.Events[4].EventType != "request_context" || writer.Events[5].EventType != "decision_log" {
		t.Fatalf("expected quota failure to write request_context and decision_log, got %#v", writer.Events[4:])
	}
	decisionLog, ok := writer.Events[5].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log, got %T", writer.Events[5].Record)
	}
	assertProtocolConformance(t, "DecisionLog", decisionLog)
	if decisionLog.RoutingContext["error_type"] != "QUOTA_EXCEEDED" {
		t.Fatalf("expected quota error in decision log, got %#v", decisionLog.RoutingContext)
	}
	if len(decisionLog.UsageEventIDs) != 0 {
		t.Fatalf("expected no provider usage event for quota failure, got %#v", decisionLog.UsageEventIDs)
	}
}

func TestExecuteFailsClosedWhenRequestContextCannotBeWritten(t *testing.T) {
	handler := Handler{
		Snapshot: newTestSnapshot("https://example.test"),
		Adapters: adapters.NewRegistry(),
		Events:   failingEventWriter{err: errors.New("disk full")},
	}
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d: %s", rec.Code, rec.Body.String())
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Success {
		t.Fatalf("expected failed response")
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "EVENT_WRITE_FAILED" {
		t.Fatalf("expected EVENT_WRITE_FAILED error, got %#v", response.Error)
	}
}

func TestExecuteMissingAdapterWritesFailedDecision(t *testing.T) {
	writer := events.NewMemoryWriter()
	handler := Handler{
		Snapshot: newTestSnapshot("https://example.test"),
		Adapters: adapters.NewRegistry(),
		Events:   writer,
	}
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d: %s", rec.Code, rec.Body.String())
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Success {
		t.Fatalf("expected failure response")
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "NO_PROVIDER" {
		t.Fatalf("expected NO_PROVIDER error, got %#v", response.Error)
	}
	if len(writer.Events) != 4 {
		t.Fatalf("expected 4 events, got %d", len(writer.Events))
	}
	if writer.Events[0].EventType != "request_context" || writer.Events[1].EventType != "routing_decision" || writer.Events[2].EventType != "usage_event" || writer.Events[3].EventType != "decision_log" {
		t.Fatalf("unexpected event order: %#v", writer.Events)
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event pointer, got %T", writer.Events[2].Record)
	}
	if usage.Success {
		t.Fatalf("expected missing adapter usage to fail")
	}
	if usage.Error == nil || usage.Error.ErrorType == nil || *usage.Error.ErrorType != "NO_PROVIDER" {
		t.Fatalf("expected NO_PROVIDER usage error, got %#v", usage.Error)
	}
	decisionLog, ok := writer.Events[3].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log pointer, got %T", writer.Events[3].Record)
	}
	if decisionLog.EventSequenceID == 0 {
		t.Fatalf("expected failed decision log sequence id")
	}
}

func TestExecuteTimeoutWritesUsageError(t *testing.T) {
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(100 * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.10"}`))
	}))
	defer providerServer.Close()

	handler, writer := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(1)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d: %s", rec.Code, rec.Body.String())
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "TIMEOUT" {
		t.Fatalf("expected TIMEOUT response, got %#v", response.Error)
	}
	if len(writer.Events) != 4 {
		t.Fatalf("expected 4 events, got %d", len(writer.Events))
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event record, got %T", writer.Events[2].Record)
	}
	if usage.Success {
		t.Fatalf("expected failed usage event")
	}
	if usage.Error == nil || usage.Error.ErrorType == nil || *usage.Error.ErrorType != "TIMEOUT" {
		t.Fatalf("expected TIMEOUT usage error, got %#v", usage.Error)
	}
	if usage.RequestMetadata["execution_timeout_budget_ms"] != 1 {
		t.Fatalf("expected timeout metadata, got %#v", usage.RequestMetadata)
	}
}

func TestExecuteResolvesEnvCredentialAndRecordsRedactedMetadata(t *testing.T) {
	t.Setenv("API2AGENT_TEST_BEARER", "local-secret")
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer local-secret" {
			t.Fatalf("expected injected bearer credential, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.77"}`))
	}))
	defer providerServer.Close()

	handler, writer := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	body := []byte(`{
		"project_id":"local",
		"capability_id":"network.public_ip.get",
		"capability_version":"0.1-migrated",
		"input":{},
		"execution_mode":"proxy",
		"timeout_budget_ms":5000,
		"credential":{
			"credential_id":"cred_test_bearer",
			"owner_type":"project",
			"owner_id":"local",
			"provider_id":"ipify",
			"auth_type":"bearer",
			"injection_mode":"header",
			"injection_name":"Authorization",
			"source":"env",
			"secret_ref":"API2AGENT_TEST_BEARER",
			"status":"active"
		}
	}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	if len(writer.Events) != 4 {
		t.Fatalf("expected 4 events, got %d", len(writer.Events))
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event, got %T", writer.Events[2].Record)
	}
	if usage.CredentialReference == nil || usage.CredentialReference.CredentialReference == nil {
		t.Fatalf("expected credential reference, got %#v", usage.CredentialReference)
	}
	if got := *usage.CredentialReference.CredentialReference; got != "env:API2AGENT_TEST_BEARER" {
		t.Fatalf("expected env credential reference, got %q", got)
	}
	metadata, ok := usage.RequestMetadata["credential"].(map[string]any)
	if !ok {
		t.Fatalf("expected redacted credential metadata, got %#v", usage.RequestMetadata)
	}
	if metadata["secret_ref"] != "API2AGENT_TEST_BEARER" {
		t.Fatalf("expected secret_ref metadata, got %#v", metadata)
	}
	encodedMetadata, err := json.Marshal(metadata)
	if err != nil {
		t.Fatalf("marshal credential metadata: %v", err)
	}
	if strings.Contains(string(encodedMetadata), "local-secret") {
		t.Fatalf("credential metadata leaked raw secret: %s", string(encodedMetadata))
	}
}

func TestExecuteMissingEnvCredentialRecordsFailureWithoutCallingProvider(t *testing.T) {
	called := false
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.88"}`))
	}))
	defer providerServer.Close()

	handler, writer := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	body := []byte(`{
		"project_id":"local",
		"capability_id":"network.public_ip.get",
		"capability_version":"0.1-migrated",
		"input":{},
		"execution_mode":"proxy",
		"timeout_budget_ms":5000,
		"credential":{
			"credential_id":"cred_missing",
			"owner_type":"project",
			"owner_id":"local",
			"provider_id":"ipify",
			"auth_type":"bearer",
			"injection_mode":"header",
			"source":"env",
			"secret_ref":"API2AGENT_MISSING_BEARER",
			"status":"active"
		}
	}`)
	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(body))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d: %s", rec.Code, rec.Body.String())
	}
	if called {
		t.Fatalf("provider should not be called when credential secret is missing")
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event, got %T", writer.Events[2].Record)
	}
	if usage.Success {
		t.Fatalf("expected failed usage event")
	}
	if usage.Error == nil || usage.Error.ErrorType == nil || *usage.Error.ErrorType != "missing_credential_secret" {
		t.Fatalf("expected missing credential error, got %#v", usage.Error)
	}
}

func TestExecuteUsesConfigCredentialWhenRequestCredentialMissing(t *testing.T) {
	t.Setenv("API2AGENT_CONFIG_TOKEN", "config-secret")
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.URL.Query().Get("api_key"); got != "config-secret" {
			t.Fatalf("expected config query credential, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.120"}`))
	}))
	defer providerServer.Close()

	handler, writer := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	handler.Credentials = []credentials.CredentialDefinition{{
		CredentialID:      "cred_config_ipify",
		CredentialVersion: "2026-05-30",
		OwnerType:         "project",
		OwnerID:           "local",
		ProviderID:        "ipify",
		AuthType:          "api_key",
		InjectionMode:     "query",
		InjectionName:     "api_key",
		Source:            "config",
		SecretRef:         "API2AGENT_CONFIG_TOKEN",
		RotationHint:      "rotate-quarterly",
	}}
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event, got %T", writer.Events[2].Record)
	}
	if usage.CredentialReference == nil || usage.CredentialReference.CredentialReference == nil {
		t.Fatalf("expected credential reference, got %#v", usage.CredentialReference)
	}
	if got := *usage.CredentialReference.CredentialReference; got != "config:cred_config_ipify" {
		t.Fatalf("expected config credential reference, got %q", got)
	}
	if usage.CredentialReference.ResolutionStrategy == nil || *usage.CredentialReference.ResolutionStrategy != "static" {
		t.Fatalf("expected static credential resolution, got %#v", usage.CredentialReference)
	}
	metadata, ok := usage.RequestMetadata["credential"].(map[string]any)
	if !ok {
		t.Fatalf("expected credential metadata, got %#v", usage.RequestMetadata)
	}
	encodedMetadata, err := json.Marshal(metadata)
	if err != nil {
		t.Fatalf("marshal credential metadata: %v", err)
	}
	if strings.Contains(string(encodedMetadata), "config-secret") {
		t.Fatalf("credential metadata leaked config secret: %s", string(encodedMetadata))
	}
	if metadata["credential_version"] != "2026-05-30" {
		t.Fatalf("expected credential_version metadata, got %#v", metadata)
	}
	if metadata["rotation_hint"] != "rotate-quarterly" {
		t.Fatalf("expected rotation_hint metadata, got %#v", metadata)
	}
	if metadata["status"] != "active" {
		t.Fatalf("expected default active status metadata, got %#v", metadata)
	}
	if _, ok := metadata["resolved_at"].(string); !ok {
		t.Fatalf("expected resolved_at metadata, got %#v", metadata)
	}
}

func TestExecuteConfigCredentialScopeDenialDoesNotCallProvider(t *testing.T) {
	t.Setenv("API2AGENT_CONFIG_TOKEN", "config-secret")
	called := false
	providerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.121"}`))
	}))
	defer providerServer.Close()

	handler, writer := newTestHandler(newTestSnapshot(providerServer.URL), providerServer.Client())
	handler.Credentials = []credentials.CredentialDefinition{{
		CredentialID:  "cred_config_ipify",
		OwnerType:     "project",
		OwnerID:       "local",
		ProviderID:    "ipify",
		AuthType:      "api_key",
		InjectionMode: "query",
		Source:        "config",
		SecretRef:     "API2AGENT_CONFIG_TOKEN",
		Scope:         []string{"capability:network.public_ip.create"},
	}}
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d: %s", rec.Code, rec.Body.String())
	}
	if called {
		t.Fatalf("provider should not be called when config credential scope is denied")
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event, got %T", writer.Events[2].Record)
	}
	if usage.Error == nil || usage.Error.ErrorType == nil || *usage.Error.ErrorType != "credential_scope_denied" {
		t.Fatalf("expected credential_scope_denied usage error, got %#v", usage.Error)
	}
}

func TestExecuteFailoverWritesFailedAndFallbackUsage(t *testing.T) {
	failingProvider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "primary failed", http.StatusInternalServerError)
	}))
	defer failingProvider.Close()

	fallbackProvider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.99"}`))
	}))
	defer fallbackProvider.Close()

	handler, writer := newTestHandler(newFailoverSnapshot(failingProvider.URL, fallbackProvider.URL), fallbackProvider.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(5000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 after fallback, got %d: %s", rec.Code, rec.Body.String())
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !response.Success {
		t.Fatalf("expected success after fallback: %+v", response)
	}
	if got := response.Output["ip"]; got != "203.0.113.99" {
		t.Fatalf("expected fallback output, got %#v", got)
	}
	if len(writer.Events) != 5 {
		t.Fatalf("expected 5 events, got %d", len(writer.Events))
	}
	firstUsage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected first usage event, got %T", writer.Events[2].Record)
	}
	if firstUsage.Success {
		t.Fatalf("expected first provider usage to fail")
	}
	if firstUsage.Error == nil || firstUsage.Error.ErrorType == nil || *firstUsage.Error.ErrorType != "PROVIDER_ERROR" {
		t.Fatalf("expected provider error on first usage, got %#v", firstUsage.Error)
	}
	if firstUsage.ParentAttemptID != nil {
		t.Fatalf("first attempt should not have parent attempt id, got %#v", firstUsage.ParentAttemptID)
	}
	if firstUsage.RequestMetadata["attempt_id"] != firstUsage.ID {
		t.Fatalf("expected first attempt metadata to include attempt id, got %#v", firstUsage.RequestMetadata)
	}
	secondUsage, ok := writer.Events[3].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected second usage event, got %T", writer.Events[3].Record)
	}
	if !secondUsage.Success {
		t.Fatalf("expected fallback usage to succeed")
	}
	if secondUsage.ParentAttemptID == nil || *secondUsage.ParentAttemptID != firstUsage.ID {
		t.Fatalf("expected second attempt parent id %q, got %#v", firstUsage.ID, secondUsage.ParentAttemptID)
	}
	if secondUsage.RequestMetadata["parent_attempt_id"] != firstUsage.ID {
		t.Fatalf("expected second attempt metadata to include parent id, got %#v", secondUsage.RequestMetadata)
	}
	decisionLog, ok := writer.Events[4].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log, got %T", writer.Events[4].Record)
	}
	if decisionLog.Outcome != "success" {
		t.Fatalf("expected success decision outcome, got %q", decisionLog.Outcome)
	}
	if len(decisionLog.UsageEventIDs) != 2 {
		t.Fatalf("expected decision log to reference both usage events, got %#v", decisionLog.UsageEventIDs)
	}
	if decisionLog.SelectedProviderID == nil || *decisionLog.SelectedProviderID != "ipify_fallback_v1" {
		t.Fatalf("expected fallback provider selected in decision log, got %#v", decisionLog.SelectedProviderID)
	}
	chain, ok := decisionLog.RoutingContext["attempt_chain"].([]map[string]any)
	if !ok || len(chain) != 2 {
		t.Fatalf("expected attempt chain in decision log, got %#v", decisionLog.RoutingContext["attempt_chain"])
	}
	if chain[0]["attempt_id"] != firstUsage.ID || chain[1]["attempt_id"] != secondUsage.ID || chain[1]["parent_attempt_id"] != firstUsage.ID {
		t.Fatalf("unexpected attempt chain: %#v", chain)
	}
}

func TestExecuteTimeoutBudgetExhaustionPreventsFallback(t *testing.T) {
	var fallbackCalls int32
	slowProvider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(150 * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.98"}`))
	}))
	defer slowProvider.Close()

	fallbackProvider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&fallbackCalls, 1)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.99"}`))
	}))
	defer fallbackProvider.Close()

	handler, writer := newTestHandler(newFailoverSnapshot(slowProvider.URL, fallbackProvider.URL), fallbackProvider.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(20)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d: %s", rec.Code, rec.Body.String())
	}
	if got := atomic.LoadInt32(&fallbackCalls); got != 0 {
		t.Fatalf("fallback should not be called after total timeout budget exhaustion, got %d calls", got)
	}
	var response ExecuteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if response.Error == nil || response.Error.ErrorType == nil || *response.Error.ErrorType != "TIMEOUT" {
		t.Fatalf("expected TIMEOUT response, got %#v", response.Error)
	}
	if len(writer.Events) != 4 {
		t.Fatalf("expected 4 events, got %d", len(writer.Events))
	}
	usage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected usage event, got %T", writer.Events[2].Record)
	}
	if usage.Success {
		t.Fatalf("expected timeout usage event to fail")
	}
	if usage.RequestMetadata["timeout_budget_policy"] != "total_deadline" {
		t.Fatalf("expected total_deadline timeout metadata, got %#v", usage.RequestMetadata)
	}
	if usage.RequestMetadata["total_timeout_budget_ms"] != 20 {
		t.Fatalf("expected total budget metadata, got %#v", usage.RequestMetadata)
	}
	if got, ok := usage.RequestMetadata["attempt_timeout_budget_ms"].(int); !ok || got <= 0 || got > 20 {
		t.Fatalf("expected attempt budget in (0,20], got %#v", usage.RequestMetadata["attempt_timeout_budget_ms"])
	}
	decisionLog, ok := writer.Events[3].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log, got %T", writer.Events[3].Record)
	}
	if decisionLog.Outcome != "failure" {
		t.Fatalf("expected failure decision outcome, got %q", decisionLog.Outcome)
	}
	if decisionLog.RoutingContext["timeout_budget_exhausted"] != true {
		t.Fatalf("expected exhausted budget in routing context, got %#v", decisionLog.RoutingContext)
	}
	if len(decisionLog.UsageEventIDs) != 1 {
		t.Fatalf("expected only one usage event after exhausted budget, got %#v", decisionLog.UsageEventIDs)
	}
}

func TestExecuteFastFailureAllowsFallbackWithinRemainingBudget(t *testing.T) {
	failingProvider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "primary failed fast", http.StatusInternalServerError)
	}))
	defer failingProvider.Close()

	fallbackProvider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ip":"203.0.113.100"}`))
	}))
	defer fallbackProvider.Close()

	handler, writer := newTestHandler(newFailoverSnapshot(failingProvider.URL, fallbackProvider.URL), fallbackProvider.Client())
	mux := http.NewServeMux()
	handler.Register(mux)

	req := httptest.NewRequest(http.MethodPost, "/v1/execute", bytes.NewReader(executeBody(1000)))
	rec := httptest.NewRecorder()

	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 after fallback, got %d: %s", rec.Code, rec.Body.String())
	}
	if len(writer.Events) != 5 {
		t.Fatalf("expected 5 events, got %d", len(writer.Events))
	}
	firstUsage, ok := writer.Events[2].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected first usage event, got %T", writer.Events[2].Record)
	}
	secondUsage, ok := writer.Events[3].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected second usage event, got %T", writer.Events[3].Record)
	}
	if firstUsage.Success {
		t.Fatalf("expected first attempt to fail")
	}
	if !secondUsage.Success {
		t.Fatalf("expected fallback attempt to succeed")
	}
	for _, usage := range []*protocol.UsageEvent{firstUsage, secondUsage} {
		if usage.RequestMetadata["timeout_budget_policy"] != "total_deadline" {
			t.Fatalf("expected total_deadline metadata, got %#v", usage.RequestMetadata)
		}
		if usage.RequestMetadata["total_timeout_budget_ms"] != 1000 {
			t.Fatalf("expected total budget metadata, got %#v", usage.RequestMetadata)
		}
		if got, ok := usage.RequestMetadata["attempt_timeout_budget_ms"].(int); !ok || got <= 0 || got > 1000 {
			t.Fatalf("expected attempt budget in (0,1000], got %#v", usage.RequestMetadata["attempt_timeout_budget_ms"])
		}
	}
	decisionLog, ok := writer.Events[4].Record.(*protocol.DecisionLog)
	if !ok {
		t.Fatalf("expected decision log, got %T", writer.Events[4].Record)
	}
	if decisionLog.Outcome != "success" {
		t.Fatalf("expected success decision outcome, got %q", decisionLog.Outcome)
	}
	if decisionLog.RoutingContext["timeout_budget_exhausted"] != false {
		t.Fatalf("expected non-exhausted budget in routing context, got %#v", decisionLog.RoutingContext)
	}
}

func assertProtocolConformance(t *testing.T, definitionName string, record any) {
	t.Helper()
	schema, err := conformance.LoadDefaultSchema()
	if err != nil {
		t.Fatalf("load protocol schema: %v", err)
	}
	if err := schema.ValidateRecord(definitionName, record); err != nil {
		t.Fatalf("validate %s: %v", definitionName, err)
	}
}
