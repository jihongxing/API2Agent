package httpapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"api2agent/services/control-plane/internal/registry"
)

func TestHealthzDoesNotRequireAdminToken(t *testing.T) {
	handler := newTestHandler(t, "")
	response := performRequest(handler, http.MethodGet, "/healthz", nil, "")
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	var health HealthResponse
	decodeResponse(t, response, &health)
	if health.Service != "api2agent-control-plane" {
		t.Fatalf("unexpected service %q", health.Service)
	}
	if health.SchemaVersion != registry.ProtocolSchemaVersion {
		t.Fatalf("unexpected schema version %q", health.SchemaVersion)
	}
}

func TestAdminEndpointsRequireBearerToken(t *testing.T) {
	handler := newTestHandler(t, "")
	response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "")
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected status 401, got %d: %s", response.Code, response.Body.String())
	}
}

func TestValidateRegistry(t *testing.T) {
	handler := newTestHandler(t, "")
	response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "secret")
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	var validation RegistryValidationResponse
	decodeResponse(t, response, &validation)
	if !validation.Valid {
		t.Fatalf("expected valid registry")
	}
	if !strings.HasPrefix(validation.RegistryFingerprint, "sha256:") {
		t.Fatalf("expected registry fingerprint, got %q", validation.RegistryFingerprint)
	}
	if validation.Validation.ProjectCount != 1 || validation.Validation.ProviderCount != 1 {
		t.Fatalf("unexpected validation counts: %#v", validation.Validation)
	}
}

func TestExportArtifactWritesArtifactDir(t *testing.T) {
	handler := newTestHandler(t, "")
	outputDir := filepath.Join(t.TempDir(), "artifact")
	body := ExportArtifactRequest{OutputDir: outputDir}
	response := performRequest(handler, http.MethodPost, "/v1/admin/snapshots/export-artifact", body, "secret")
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	var exported ExportArtifactResponse
	decodeResponse(t, response, &exported)
	if exported.ArtifactDir != outputDir {
		t.Fatalf("unexpected artifact dir %q", exported.ArtifactDir)
	}
	if exported.Manifest.SnapshotVersion != "snapshot_service_api_v1" {
		t.Fatalf("unexpected snapshot version %q", exported.Manifest.SnapshotVersion)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "snapshot.json")); err != nil {
		t.Fatalf("snapshot.json was not written: %v", err)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "manifest.json")); err != nil {
		t.Fatalf("manifest.json was not written: %v", err)
	}
}

func TestDistributionCurrentReadsPointer(t *testing.T) {
	artifactDir := filepath.Join(t.TempDir(), "artifact")
	distributionDir := filepath.Join(t.TempDir(), "distribution")
	reg := validRegistry()
	snapshot, manifest, err := reg.ExportArtifact(time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC), "file", "registry.json")
	if err != nil {
		t.Fatalf("export artifact: %v", err)
	}
	if err := registry.WriteArtifactDir(artifactDir, snapshot, manifest); err != nil {
		t.Fatalf("write artifact: %v", err)
	}
	pointer, err := registry.PublishArtifactDir(artifactDir, distributionDir, time.Date(2026, 5, 31, 4, 5, 6, 0, time.UTC))
	if err != nil {
		t.Fatalf("publish artifact: %v", err)
	}
	handler := newTestHandler(t, distributionDir)
	response := performRequest(handler, http.MethodGet, "/v1/admin/distribution/current", nil, "secret")
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	var current DistributionCurrentResponse
	decodeResponse(t, response, &current)
	if current.Pointer.SnapshotVersion != pointer.SnapshotVersion {
		t.Fatalf("unexpected pointer: %#v", current.Pointer)
	}
	if current.DistributionDir != distributionDir {
		t.Fatalf("unexpected distribution dir %q", current.DistributionDir)
	}
}

func TestPublishArtifactPublishesToDistribution(t *testing.T) {
	artifactDir := filepath.Join(t.TempDir(), "artifact")
	distributionDir := filepath.Join(t.TempDir(), "distribution")
	reg := validRegistry()
	snapshot, manifest, err := reg.ExportArtifact(time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC), "file", "registry.json")
	if err != nil {
		t.Fatalf("export artifact: %v", err)
	}
	if err := registry.WriteArtifactDir(artifactDir, snapshot, manifest); err != nil {
		t.Fatalf("write artifact: %v", err)
	}
	handler := newTestHandler(t, distributionDir)
	response := performRequest(handler, http.MethodPost, "/v1/admin/distribution/publish", PublishArtifactRequest{ArtifactDir: artifactDir}, "secret")
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	var published PublishArtifactResponse
	decodeResponse(t, response, &published)
	if published.Pointer.SnapshotVersion != "snapshot_service_api_v1" {
		t.Fatalf("unexpected pointer: %#v", published.Pointer)
	}
	current, err := registry.ReadDistributionPointerFile(filepath.Join(distributionDir, "current.json"))
	if err != nil {
		t.Fatalf("read current pointer: %v", err)
	}
	if current.SnapshotVersion != published.Pointer.SnapshotVersion {
		t.Fatalf("current pointer did not match response: %#v vs %#v", current, published.Pointer)
	}
}

func TestPublishArtifactRejectsDuplicateWithoutAdvancingCurrent(t *testing.T) {
	artifactDir := filepath.Join(t.TempDir(), "artifact")
	distributionDir := filepath.Join(t.TempDir(), "distribution")
	reg := validRegistry()
	snapshot, manifest, err := reg.ExportArtifact(time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC), "file", "registry.json")
	if err != nil {
		t.Fatalf("export artifact: %v", err)
	}
	if err := registry.WriteArtifactDir(artifactDir, snapshot, manifest); err != nil {
		t.Fatalf("write artifact: %v", err)
	}
	handler := newTestHandler(t, distributionDir)
	first := performRequest(handler, http.MethodPost, "/v1/admin/distribution/publish", PublishArtifactRequest{ArtifactDir: artifactDir}, "secret")
	if first.Code != http.StatusCreated {
		t.Fatalf("expected first status 201, got %d: %s", first.Code, first.Body.String())
	}
	currentBefore, err := registry.ReadDistributionPointerFile(filepath.Join(distributionDir, "current.json"))
	if err != nil {
		t.Fatalf("read current pointer before duplicate: %v", err)
	}
	duplicate := performRequest(handler, http.MethodPost, "/v1/admin/distribution/publish", PublishArtifactRequest{ArtifactDir: artifactDir}, "secret")
	if duplicate.Code != http.StatusConflict {
		t.Fatalf("expected duplicate status 409, got %d: %s", duplicate.Code, duplicate.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, duplicate, &errorResponse)
	if errorResponse.Error.ErrorType != "DISTRIBUTION_ARTIFACT_EXISTS" {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
	currentAfter, err := registry.ReadDistributionPointerFile(filepath.Join(distributionDir, "current.json"))
	if err != nil {
		t.Fatalf("read current pointer after duplicate: %v", err)
	}
	if currentAfter.PublishedAt != currentBefore.PublishedAt || currentAfter.SnapshotVersion != currentBefore.SnapshotVersion {
		t.Fatalf("expected current pointer to remain unchanged: %#v vs %#v", currentAfter, currentBefore)
	}
}

func newTestHandler(t *testing.T, distributionDir string) Handler {
	t.Helper()
	registryPath := filepath.Join(t.TempDir(), "registry.json")
	data, err := json.MarshalIndent(validRegistry(), "", "  ")
	if err != nil {
		t.Fatalf("encode registry: %v", err)
	}
	if err := os.WriteFile(registryPath, append(data, '\n'), 0o644); err != nil {
		t.Fatalf("write registry: %v", err)
	}
	return Handler{
		Store:           registry.NewFileStore(registryPath),
		RegistryStore:   "file",
		RegistrySource:  registryPath,
		DistributionDir: distributionDir,
		AdminToken:      "secret",
		Now: func() time.Time {
			return time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC)
		},
	}
}

func performRequest(handler Handler, method string, path string, body any, token string) *httptest.ResponseRecorder {
	var reader *bytes.Reader
	if body == nil {
		reader = bytes.NewReader(nil)
	} else {
		data, _ := json.Marshal(body)
		reader = bytes.NewReader(data)
	}
	req := httptest.NewRequest(method, path, reader)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	mux := http.NewServeMux()
	handler.Register(mux)
	response := httptest.NewRecorder()
	mux.ServeHTTP(response, req)
	return response
}

func decodeResponse(t *testing.T, response *httptest.ResponseRecorder, target any) {
	t.Helper()
	if err := json.Unmarshal(response.Body.Bytes(), target); err != nil {
		t.Fatalf("decode response: %v; body=%s", err, response.Body.String())
	}
}

func validRegistry() registry.Registry {
	return registry.Registry{
		Projects: []registry.Project{
			{ID: "local", Name: "Local", Status: "active", DefaultMode: "proxy"},
		},
		APIKeys: []registry.APIKey{
			{ID: "key_local_dev", ProjectID: "local", KeyPrefix: "a2a_local", Status: "active"},
		},
		Capabilities: []registry.Capability{
			{ID: "network.public_ip.get", Version: "1.0.0", Name: "Get public IP"},
		},
		Providers: []registry.Provider{
			{
				ID:                "ipify_public_ip_v1",
				CapabilityID:      "network.public_ip.get",
				CapabilityVersion: "1.0.0",
				ProviderID:        "ipify",
				ProviderVersion:   "1.0.0",
				MappingVersion:    "1.0.0",
				ToolID:            "get_public_ip",
				Regions:           []string{"global"},
				GeoAffinity:       "global",
				EstimatedCost:     0,
				Status:            "active",
				Metadata: map[string]string{
					"base_url": "https://api.ipify.org",
				},
			},
		},
		RoutingPolicy: registry.RoutingPolicy{
			Strategy:    "first",
			RoutingMode: "deterministic",
		},
		Snapshot: registry.SnapshotExportOptions{
			Version:   "snapshot_service_api_v1",
			FetchedAt: time.Date(2026, 5, 30, 0, 0, 0, 0, time.UTC),
			TTL:       "24h",
			Source:    "pull",
		},
	}
}
