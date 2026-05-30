package httpapi

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"api2agent/services/data-plane/internal/adapters"
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
	secondUsage, ok := writer.Events[3].Record.(*protocol.UsageEvent)
	if !ok {
		t.Fatalf("expected second usage event, got %T", writer.Events[3].Record)
	}
	if !secondUsage.Success {
		t.Fatalf("expected fallback usage to succeed")
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
}

func assertProtocolConformance(t *testing.T, definitionName string, record any) {
	t.Helper()
	schema := loadProtocolSchema(t)
	definition, ok := schema.Defs[definitionName]
	if !ok {
		t.Fatalf("schema definition %q not found", definitionName)
	}

	data, err := json.Marshal(record)
	if err != nil {
		t.Fatalf("marshal %s: %v", definitionName, err)
	}
	var payload map[string]any
	if err := json.Unmarshal(data, &payload); err != nil {
		t.Fatalf("decode marshaled %s: %v", definitionName, err)
	}
	for _, required := range definition.Required {
		if _, ok := payload[required]; !ok {
			t.Fatalf("%s missing required schema field %q in %#v", definitionName, required, payload)
		}
	}
	if definition.AdditionalProperties == false {
		for key := range payload {
			if _, ok := definition.Properties[key]; !ok {
				t.Fatalf("%s emitted field %q not present in schema snapshot", definitionName, key)
			}
		}
	}
	if got, ok := payload["schema_version"].(string); ok && got != protocol.SchemaVersion {
		t.Fatalf("%s schema_version = %q, want %q", definitionName, got, protocol.SchemaVersion)
	}
}

type protocolSchema struct {
	Defs map[string]schemaDefinition `json:"$defs"`
}

type schemaDefinition struct {
	AdditionalProperties bool                       `json:"additionalProperties"`
	Required             []string                   `json:"required"`
	Properties           map[string]json.RawMessage `json:"properties"`
}

func loadProtocolSchema(t *testing.T) protocolSchema {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatalf("resolve caller path")
	}
	path := filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", "..", "..", "schemas", "api2agent", "v0.2", "protocol.schema.json"))
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read protocol schema %s: %v", path, err)
	}
	var schema protocolSchema
	if err := json.Unmarshal(data, &schema); err != nil {
		t.Fatalf("decode protocol schema: %v", err)
	}
	return schema
}
