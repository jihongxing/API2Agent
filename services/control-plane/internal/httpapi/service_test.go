package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
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

func TestValidateRegistryRecordsAdminAudit(t *testing.T) {
	audit := &recordingAuditSink{}
	handler := newTestHandler(t, "")
	handler.AuditSink = audit
	response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "secret")
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one admin audit event, got %#v", audit.adminEvents)
	}
	event := audit.adminEvents[0]
	if event.Action != "registry.validate" || event.Outcome != "success" || event.ResourceType != "registry" {
		t.Fatalf("unexpected audit event: %#v", event)
	}
	if event.Metadata["registry_store"] != "file" {
		t.Fatalf("expected registry_store metadata, got %#v", event.Metadata)
	}
}

func TestValidateRegistryPersistentStoreReadFailure(t *testing.T) {
	audit := &recordingAuditSink{}
	handler := newTestHandler(t, "")
	handler.Store = failingStore{err: fmt.Errorf("query projects: connection refused")}
	handler.RegistryStore = "postgres"
	handler.RegistrySource = "postgres"
	handler.AuditSink = audit
	response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "secret")
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "PERSISTENT_STORE_READ_FAILED" || errorResponse.Error.ErrorScope != "platform" || !errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one failure audit event, got %#v", audit.adminEvents)
	}
	event := audit.adminEvents[0]
	if event.Action != "registry.validate" || event.Outcome != "failure" || event.ErrorType != "PERSISTENT_STORE_READ_FAILED" {
		t.Fatalf("unexpected audit event: %#v", event)
	}
}

func TestValidateRegistryFileStoreLoadFailureRemainsRegistryInvalid(t *testing.T) {
	handler := newTestHandler(t, "")
	handler.Store = failingStore{err: fmt.Errorf("open registry: missing file")}
	handler.RegistryStore = "file"
	response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "secret")
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "REGISTRY_INVALID" || errorResponse.Error.ErrorScope != "caller" || errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestValidateRegistryFailsClosedWhenAuditWriteFails(t *testing.T) {
	handler := newTestHandler(t, "")
	handler.AuditSink = &recordingAuditSink{err: fmt.Errorf("audit unavailable")}
	response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "secret")
	if response.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUDIT_WRITE_FAILED" || errorResponse.Error.ErrorScope != "platform" || !errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestImportReplaceRegistryRequiresAdminToken(t *testing.T) {
	handler := newPostgresImportHandler(registry.ImportReplaceResult{})
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", map[string]string{
		"X-Request-ID":    "req-import",
		"Idempotency-Key": "idem-import",
	})
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected status 401, got %d: %s", response.Code, response.Body.String())
	}
}

func TestImportReplaceRegistryRequiresRequestIDAndIdempotencyKey(t *testing.T) {
	handler := newPostgresImportHandler(registry.ImportReplaceResult{})
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "secret", nil)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing request id status 400, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "INVALID_REQUEST" || !strings.Contains(errorResponse.Error.Message, "X-Request-ID") {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "secret", map[string]string{
		"X-Request-ID": "req-import",
	})
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing idempotency key status 400, got %d: %s", response.Code, response.Body.String())
	}
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "INVALID_REQUEST" || !strings.Contains(errorResponse.Error.Message, "Idempotency-Key") {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestImportReplaceRegistryUnavailableForFileStore(t *testing.T) {
	handler := newTestHandler(t, "")
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "secret", map[string]string{
		"X-Request-ID":    "req-import",
		"Idempotency-Key": "idem-import",
	})
	if response.Code != http.StatusConflict {
		t.Fatalf("expected status 409, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "REGISTRY_MUTATION_UNAVAILABLE" || errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestImportReplaceRegistryRejectsInvalidBodies(t *testing.T) {
	handler := newPostgresImportHandler(registry.ImportReplaceResult{})
	headers := map[string]string{
		"X-Request-ID":    "req-import",
		"Idempotency-Key": "idem-import",
	}

	response := performRawRequest(handler, http.MethodPost, "/v1/admin/registry/import-replace", []byte(`{`), "secret", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected invalid json status 400, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", map[string]any{"source": "missing-registry"}, "secret", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing registry status 400, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", map[string]any{
		"registry": validRegistry(),
		"dry_run":  true,
	}, "secret", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected dry_run status 400, got %d: %s", response.Code, response.Body.String())
	}

	large := []byte(`{"registry":`)
	large = append(large, bytes.Repeat([]byte(" "), int(importReplaceMaxBodyBytes))...)
	large = append(large, []byte(`{}}`)...)
	response = performRawRequest(handler, http.MethodPost, "/v1/admin/registry/import-replace", large, "secret", headers)
	if response.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("expected body too large status 413, got %d: %s", response.Code, response.Body.String())
	}
}

func TestImportReplaceRegistryReturnsCreatedAndPassesOptions(t *testing.T) {
	result := registry.ImportReplaceResult{
		RegistryFingerprint:         "sha256:new",
		PreviousRegistryFingerprint: "sha256:old",
		SnapshotVersion:             "snapshot_http_import_v1",
		Noop:                        false,
		Counts: registry.ImportReplaceCounts{
			Projects:           1,
			APIKeys:            1,
			Capabilities:       1,
			Providers:          1,
			CredentialMetadata: 1,
			RoutingPolicies:    1,
			SnapshotConfigs:    1,
		},
	}
	replacer := &recordingImportReplacer{result: result}
	handler := newPostgresImportHandlerWithReplacer(replacer)
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBodyWithSource(t, "admin_upload"), "secret", map[string]string{
		"X-Request-ID":    " req-http ",
		"Idempotency-Key": " idem-http ",
		"X-Actor-ID":      " local-admin ",
	})
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	var imported ImportReplaceResponse
	decodeResponse(t, response, &imported)
	if imported.RegistryStore != "postgres" || imported.Noop || imported.RegistryFingerprint != result.RegistryFingerprint {
		t.Fatalf("unexpected import response: %#v", imported)
	}
	if replacer.calls != 1 {
		t.Fatalf("expected one replacer call, got %d", replacer.calls)
	}
	if replacer.options.ActorID != "local-admin" || replacer.options.RequestID != "req-http" || replacer.options.IdempotencyKey != "idem-http" || replacer.options.Source != "admin_upload" {
		t.Fatalf("unexpected import options: %#v", replacer.options)
	}
}

func TestImportReplaceRegistryReturnsOKForNoop(t *testing.T) {
	result := registry.ImportReplaceResult{
		RegistryFingerprint:         "sha256:same",
		PreviousRegistryFingerprint: "sha256:same",
		SnapshotVersion:             "snapshot_http_import_v1",
		Noop:                        true,
		Counts:                      registry.ImportReplaceCounts{Projects: 1, Providers: 1},
	}
	replacer := &recordingImportReplacer{result: result}
	handler := newPostgresImportHandlerWithReplacer(replacer)
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "secret", map[string]string{
		"X-Request-ID":    "req-noop",
		"Idempotency-Key": "idem-noop",
	})
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	var imported ImportReplaceResponse
	decodeResponse(t, response, &imported)
	if !imported.Noop || imported.RegistryFingerprint != "sha256:same" {
		t.Fatalf("unexpected no-op response: %#v", imported)
	}
	if replacer.options.ActorID != "admin" || replacer.options.Source != "admin_http_import" {
		t.Fatalf("unexpected default options: %#v", replacer.options)
	}
}

func TestImportReplaceRegistryMapsMutationErrors(t *testing.T) {
	tests := []struct {
		errorType string
		scope     string
		retryable bool
		status    int
	}{
		{"REGISTRY_MUTATION_INVALID", "caller", false, http.StatusBadRequest},
		{"REGISTRY_MUTATION_CONFLICT", "platform", true, http.StatusConflict},
		{"PERSISTENT_STORE_READ_FAILED", "platform", true, http.StatusServiceUnavailable},
		{"PERSISTENT_STORE_WRITE_FAILED", "platform", true, http.StatusServiceUnavailable},
		{"AUDIT_WRITE_FAILED", "platform", true, http.StatusInternalServerError},
	}
	for _, test := range tests {
		t.Run(test.errorType, func(t *testing.T) {
			handler := newPostgresImportHandlerWithReplacer(&recordingImportReplacer{
				err: registry.RegistryMutationError{
					ErrorType:  test.errorType,
					Scope:      test.scope,
					Retryable:  test.retryable,
					Underlying: fmt.Errorf("simulated %s", test.errorType),
				},
			})
			response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "secret", map[string]string{
				"X-Request-ID":    "req-error",
				"Idempotency-Key": "idem-error",
			})
			if response.Code != test.status {
				t.Fatalf("expected status %d, got %d: %s", test.status, response.Code, response.Body.String())
			}
			var errorResponse ErrorResponse
			decodeResponse(t, response, &errorResponse)
			if errorResponse.Error.ErrorType != test.errorType || errorResponse.Error.ErrorScope != test.scope || errorResponse.Error.Retryable != test.retryable {
				t.Fatalf("unexpected error response: %#v", errorResponse)
			}
		})
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

func TestExportArtifactRecordsPersistentAudit(t *testing.T) {
	audit := &recordingAuditSink{}
	handler := newTestHandler(t, "")
	handler.AuditSink = audit
	outputDir := filepath.Join(t.TempDir(), "artifact")
	response := performRequest(handler, http.MethodPost, "/v1/admin/snapshots/export-artifact", ExportArtifactRequest{OutputDir: outputDir}, "secret")
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	if len(audit.registryRevisions) != 1 {
		t.Fatalf("expected one registry revision, got %#v", audit.registryRevisions)
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one admin audit event, got %#v", audit.adminEvents)
	}
	revision := audit.registryRevisions[0]
	if revision.SnapshotVersion != "snapshot_service_api_v1" || !strings.HasPrefix(revision.RegistryFingerprint, "sha256:") {
		t.Fatalf("unexpected registry revision: %#v", revision)
	}
	event := audit.adminEvents[0]
	if event.Action != "snapshot.export_artifact" || event.Outcome != "success" || event.ResourceID != "snapshot_service_api_v1" {
		t.Fatalf("unexpected admin audit event: %#v", event)
	}
}

func TestExportArtifactFailsClosedWhenAuditWriteFails(t *testing.T) {
	handler := newTestHandler(t, "")
	handler.AuditSink = &recordingAuditSink{err: fmt.Errorf("audit unavailable")}
	outputDir := filepath.Join(t.TempDir(), "artifact")
	response := performRequest(handler, http.MethodPost, "/v1/admin/snapshots/export-artifact", ExportArtifactRequest{OutputDir: outputDir}, "secret")
	if response.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUDIT_WRITE_FAILED" {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestExportArtifactPersistentStoreReadFailure(t *testing.T) {
	handler := newTestHandler(t, "")
	handler.Store = failingStore{err: fmt.Errorf("begin registry read transaction: connection refused")}
	handler.RegistryStore = "postgres"
	handler.RegistrySource = "postgres"
	outputDir := filepath.Join(t.TempDir(), "artifact")
	response := performRequest(handler, http.MethodPost, "/v1/admin/snapshots/export-artifact", ExportArtifactRequest{OutputDir: outputDir}, "secret")
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "PERSISTENT_STORE_READ_FAILED" || errorResponse.Error.ErrorScope != "platform" || !errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
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

func TestDistributionCurrentRecordsAdminAudit(t *testing.T) {
	audit := &recordingAuditSink{}
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
	if _, err := registry.PublishArtifactDir(artifactDir, distributionDir, time.Date(2026, 5, 31, 4, 5, 6, 0, time.UTC)); err != nil {
		t.Fatalf("publish artifact: %v", err)
	}
	handler := newTestHandler(t, distributionDir)
	handler.AuditSink = audit
	response := performRequest(handler, http.MethodGet, "/v1/admin/distribution/current", nil, "secret")
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one admin audit event, got %#v", audit.adminEvents)
	}
	event := audit.adminEvents[0]
	if event.Action != "distribution.current.read" || event.Outcome != "success" || event.ResourceID != "snapshot_service_api_v1" {
		t.Fatalf("unexpected admin audit event: %#v", event)
	}
}

func TestDistributionCurrentFailsClosedWhenAuditWriteFails(t *testing.T) {
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
	if _, err := registry.PublishArtifactDir(artifactDir, distributionDir, time.Date(2026, 5, 31, 4, 5, 6, 0, time.UTC)); err != nil {
		t.Fatalf("publish artifact: %v", err)
	}
	handler := newTestHandler(t, distributionDir)
	handler.AuditSink = &recordingAuditSink{err: fmt.Errorf("audit unavailable")}
	response := performRequest(handler, http.MethodGet, "/v1/admin/distribution/current", nil, "secret")
	if response.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUDIT_WRITE_FAILED" || errorResponse.Error.ErrorScope != "platform" || !errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
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

func TestPublishArtifactRecordsPersistentAudit(t *testing.T) {
	audit := &recordingAuditSink{}
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
	handler.AuditSink = audit
	response := performRequest(handler, http.MethodPost, "/v1/admin/distribution/publish", PublishArtifactRequest{ArtifactDir: artifactDir}, "secret")
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	if len(audit.artifactPublications) != 1 {
		t.Fatalf("expected one artifact publication, got %#v", audit.artifactPublications)
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one admin audit event, got %#v", audit.adminEvents)
	}
	publication := audit.artifactPublications[0]
	if publication.SnapshotVersion != "snapshot_service_api_v1" || publication.Status != "published" || publication.DistributionURI == "" {
		t.Fatalf("unexpected artifact publication: %#v", publication)
	}
	event := audit.adminEvents[0]
	if event.Action != "distribution.publish" || event.Outcome != "success" || event.ResourceID != "snapshot_service_api_v1" {
		t.Fatalf("unexpected admin audit event: %#v", event)
	}
}

func TestPublishArtifactFailsClosedWhenAuditWriteFails(t *testing.T) {
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
	handler.AuditSink = &recordingAuditSink{err: fmt.Errorf("audit unavailable")}
	response := performRequest(handler, http.MethodPost, "/v1/admin/distribution/publish", PublishArtifactRequest{ArtifactDir: artifactDir}, "secret")
	if response.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUDIT_WRITE_FAILED" || errorResponse.Error.ErrorScope != "platform" || !errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
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

func newPostgresImportHandler(result registry.ImportReplaceResult) Handler {
	return newPostgresImportHandlerWithReplacer(&recordingImportReplacer{result: result})
}

func newPostgresImportHandlerWithReplacer(replacer *recordingImportReplacer) Handler {
	return Handler{
		RegistryStore:  "postgres",
		RegistrySource: "postgres",
		AdminToken:     "secret",
		ImportReplacer: replacer,
		Now: func() time.Time {
			return time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC)
		},
	}
}

func performRequest(handler Handler, method string, path string, body any, token string) *httptest.ResponseRecorder {
	return performRequestWithHeaders(handler, method, path, body, token, nil)
}

func performRequestWithHeaders(handler Handler, method string, path string, body any, token string, headers map[string]string) *httptest.ResponseRecorder {
	var reader *bytes.Reader
	if body == nil {
		reader = bytes.NewReader(nil)
	} else {
		data, _ := json.Marshal(body)
		reader = bytes.NewReader(data)
	}
	return performRequestReader(handler, method, path, reader, body != nil, token, headers)
}

func performRawRequest(handler Handler, method string, path string, body []byte, token string, headers map[string]string) *httptest.ResponseRecorder {
	return performRequestReader(handler, method, path, bytes.NewReader(body), true, token, headers)
}

func performRequestReader(handler Handler, method string, path string, reader *bytes.Reader, jsonBody bool, token string, headers map[string]string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, reader)
	if jsonBody {
		req.Header.Set("Content-Type", "application/json")
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	for key, value := range headers {
		req.Header.Set(key, value)
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

func importReplaceBody(t *testing.T) map[string]any {
	t.Helper()
	return importReplaceBodyWithSource(t, "")
}

func importReplaceBodyWithSource(t *testing.T, source string) map[string]any {
	t.Helper()
	body := map[string]any{
		"registry": validRegistry(),
	}
	if source != "" {
		body["source"] = source
	}
	return body
}

type failingStore struct {
	err error
}

func (s failingStore) Load(ctx context.Context) (*registry.Registry, error) {
	return nil, s.err
}

type recordingAuditSink struct {
	registryRevisions    []registry.PersistentRegistryRevisionRow
	artifactPublications []registry.PersistentArtifactPublicationRow
	adminEvents          []registry.PersistentAdminAuditEventRow
	err                  error
}

func (s *recordingAuditSink) RecordRegistryRevision(ctx context.Context, row registry.PersistentRegistryRevisionRow) error {
	if s.err != nil {
		return s.err
	}
	s.registryRevisions = append(s.registryRevisions, row)
	return nil
}

func (s *recordingAuditSink) RecordArtifactPublication(ctx context.Context, row registry.PersistentArtifactPublicationRow) error {
	if s.err != nil {
		return s.err
	}
	s.artifactPublications = append(s.artifactPublications, row)
	return nil
}

func (s *recordingAuditSink) RecordAdminAuditEvent(ctx context.Context, row registry.PersistentAdminAuditEventRow) error {
	if s.err != nil {
		return s.err
	}
	s.adminEvents = append(s.adminEvents, row)
	return nil
}

type recordingImportReplacer struct {
	result  registry.ImportReplaceResult
	err     error
	calls   int
	options registry.ImportReplaceOptions
	reg     registry.Registry
}

func (r *recordingImportReplacer) ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error) {
	r.calls++
	r.reg = reg
	r.options = opts
	if r.err != nil {
		return registry.ImportReplaceResult{}, r.err
	}
	return r.result, nil
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
