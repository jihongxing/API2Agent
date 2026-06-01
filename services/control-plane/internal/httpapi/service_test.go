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
	if event.ActorID != "admin" {
		t.Fatalf("expected local admin audit actor, got %q", event.ActorID)
	}
	if event.Metadata["registry_store"] != "file" || event.Metadata["project_id"] != "control_plane" || event.Metadata["auth_method"] != registry.AdminAuthMethodLocalAdminToken || event.Metadata["local_private"] != "true" {
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
	if replacer.options.ProjectID != "control_plane" || replacer.options.ActorID != "local-admin" || replacer.options.RequestID != "req-http" || replacer.options.IdempotencyKey != "idem-http" || replacer.options.Source != "admin_upload" {
		t.Fatalf("unexpected import options: %#v", replacer.options)
	}
}

func TestImportReplaceRegistryUsesHostedPrincipalForIdentityScope(t *testing.T) {
	replacer := &recordingImportReplacer{result: registry.ImportReplaceResult{
		RegistryFingerprint: "sha256:new",
		SnapshotVersion:     "snapshot_http_import_v1",
		Counts:              registry.ImportReplaceCounts{Projects: 1, Providers: 1},
	}}
	authenticator := &recordingAdminAuthenticator{
		principal: registry.AdminPrincipal{
			SubjectID:      "subject-hosted",
			ActorID:        "hosted-actor",
			ProjectID:      "project-hosted",
			OrganizationID: "org-hosted",
			AuthMethod:     registry.AdminAuthMethodHostedAdminToken,
			TokenID:        "token-123",
			Permissions:    []string{registry.PermissionRegistryImportReplace},
		},
	}
	handler := newPostgresImportHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.Authenticator = authenticator

	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", map[string]string{
		"X-Request-ID":      "req-hosted",
		"Idempotency-Key":   "idem-hosted",
		"X-Actor-ID":        "caller-controlled",
		"X-Project-ID":      "caller-project",
		"X-Organization-ID": "caller-org",
	})
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	if authenticator.requiredPermission != registry.PermissionRegistryImportReplace {
		t.Fatalf("unexpected required permission %q", authenticator.requiredPermission)
	}
	if replacer.options.ProjectID != "project-hosted" || replacer.options.ActorID != "hosted-actor" {
		t.Fatalf("expected hosted principal identity scope, got %#v", replacer.options)
	}
	if replacer.options.SubjectID != "subject-hosted" || replacer.options.OrganizationID != "org-hosted" || replacer.options.AuthMethod != registry.AdminAuthMethodHostedAdminToken || replacer.options.TokenID != "token-123" || replacer.options.LocalPrivate {
		t.Fatalf("expected hosted principal evidence, got %#v", replacer.options)
	}
}

func TestHostedAdminPermissionDeniedBeforeMutation(t *testing.T) {
	replacer := &recordingImportReplacer{result: registry.ImportReplaceResult{}}
	handler := newPostgresImportHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.Authenticator = &recordingAdminAuthenticator{
		principal: registry.AdminPrincipal{
			ActorID:     "hosted-actor",
			ProjectID:   "project-hosted",
			AuthMethod:  registry.AdminAuthMethodHostedAdminToken,
			Permissions: []string{registry.PermissionRegistryValidate},
		},
	}
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", map[string]string{
		"X-Request-ID":    "req-denied",
		"Idempotency-Key": "idem-denied",
	})
	if response.Code != http.StatusForbidden {
		t.Fatalf("expected status 403, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUTHZ_DENIED" || errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
	if replacer.calls != 0 {
		t.Fatalf("mutation should not run after authz denial, got %d calls", replacer.calls)
	}
}

func TestHostedAdminAuthenticatorUnavailable(t *testing.T) {
	handler := newPostgresImportHandler(registry.ImportReplaceResult{})
	handler.AdminIdentityMode = AdminIdentityModeHosted
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", map[string]string{
		"X-Request-ID":    "req-unavailable",
		"Idempotency-Key": "idem-unavailable",
	})
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUTH_SERVICE_UNAVAILABLE" || errorResponse.Error.ErrorScope != "platform" || !errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestHostedAdminMalformedIdentityReturnsAuthError(t *testing.T) {
	handler := newPostgresImportHandler(registry.ImportReplaceResult{})
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.Authenticator = &recordingAdminAuthenticator{err: AdminAuthError{
		ErrorType: "AUTH_ERROR",
		Scope:     "caller",
		Message:   "malformed trusted gateway identity",
	}}
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", map[string]string{
		"X-Request-ID":    "req-malformed",
		"Idempotency-Key": "idem-malformed",
	})
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected status 401, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUTH_ERROR" || !strings.Contains(errorResponse.Error.Message, "malformed") {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestHostedAdminAuditUsesResolvedPrincipal(t *testing.T) {
	audit := &recordingAuditSink{}
	handler := newTestHandler(t, "")
	handler.AuditSink = audit
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.Authenticator = &recordingAdminAuthenticator{
		principal: registry.AdminPrincipal{
			SubjectID:      "subject-hosted",
			ActorID:        "hosted-actor",
			ProjectID:      "project-hosted",
			OrganizationID: "org-hosted",
			AuthMethod:     registry.AdminAuthMethodTrustedGateway,
			TokenID:        "token-456",
			Permissions:    []string{registry.PermissionRegistryValidate},
		},
	}
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "", map[string]string{
		"X-Actor-ID": "caller-controlled",
	})
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one audit event, got %#v", audit.adminEvents)
	}
	event := audit.adminEvents[0]
	if event.ActorID != "hosted-actor" {
		t.Fatalf("expected hosted actor, got %#v", event)
	}
	if event.Metadata["project_id"] != "project-hosted" || event.Metadata["principal_subject_id"] != "subject-hosted" || event.Metadata["organization_id"] != "org-hosted" || event.Metadata["auth_method"] != registry.AdminAuthMethodTrustedGateway || event.Metadata["token_id"] != "token-456" || event.Metadata["local_private"] != "false" {
		t.Fatalf("unexpected hosted audit metadata: %#v", event.Metadata)
	}
}

func TestTrustedGatewayValidateRecordsAuditAndIgnoresPublicIdentityHeaders(t *testing.T) {
	audit := &recordingAuditSink{}
	handler := newTestHandler(t, "")
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	handler.AuditSink = audit
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "public-token", trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Actor-ID":             "public-actor",
		"X-Project-ID":           "public-project",
		trustedActorIDHeader:     "trusted-actor",
		trustedPermissionsHeader: registry.PermissionRegistryValidate,
	}))
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if len(audit.adminEvents) != 1 {
		t.Fatalf("expected one audit event, got %#v", audit.adminEvents)
	}
	event := audit.adminEvents[0]
	if event.ActorID != "trusted-actor" {
		t.Fatalf("expected trusted actor, got %#v", event)
	}
	if event.Metadata["principal_subject_id"] != "principal-1" || event.Metadata["project_id"] != "project-1" || event.Metadata["organization_id"] != "org-1" || event.Metadata["auth_method"] != registry.AdminAuthMethodTrustedGateway || event.Metadata["token_id"] != "token-1" || event.Metadata["gateway_key_id"] != "key-1" || event.Metadata["local_private"] != "false" {
		t.Fatalf("unexpected audit metadata: %#v", event.Metadata)
	}
	for key, value := range event.Metadata {
		if strings.Contains(value, "gateway-secret") || strings.Contains(key, "gateway-secret") {
			t.Fatalf("gateway secret leaked into audit metadata: %#v", event.Metadata)
		}
	}
}

func TestTrustedGatewayImportReplacePassesPrincipalScope(t *testing.T) {
	replacer := &recordingImportReplacer{result: registry.ImportReplaceResult{
		RegistryFingerprint: "sha256:new",
		SnapshotVersion:     "snapshot_http_import_v1",
		Counts:              registry.ImportReplaceCounts{Projects: 1, Providers: 1},
	}}
	handler := newPostgresImportHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-gateway",
		"Idempotency-Key":        "idem-gateway",
		trustedActorIDHeader:     "trusted-actor",
		trustedProjectIDHeader:   "project-2",
		trustedPermissionsHeader: registry.PermissionRegistryImportReplace,
	}))
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	if replacer.options.ProjectID != "project-2" || replacer.options.ActorID != "trusted-actor" || replacer.options.RequestID != "req-gateway" || replacer.options.IdempotencyKey != "idem-gateway" {
		t.Fatalf("unexpected import options: %#v", replacer.options)
	}
	if replacer.options.SubjectID != "principal-1" || replacer.options.OrganizationID != "org-1" || replacer.options.AuthMethod != registry.AdminAuthMethodTrustedGateway || replacer.options.TokenID != "token-1" || replacer.options.GatewayKeyID != "key-1" || replacer.options.LocalPrivate {
		t.Fatalf("expected trusted gateway principal evidence, got %#v", replacer.options)
	}
}

func TestTrustedGatewayAcceptsMultipleActiveSecretsAndRejectsRemovedSecret(t *testing.T) {
	handler := newTestHandler(t, "")
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecrets = []string{"old-secret", "new-secret"}
	for _, secret := range []string{"old-secret", "new-secret"} {
		response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "", trustedGatewayHeaders(secret, map[string]string{
			trustedPermissionsHeader: registry.PermissionRegistryValidate,
		}))
		if response.Code != http.StatusOK {
			t.Fatalf("expected active secret %q to be accepted, got %d: %s", secret, response.Code, response.Body.String())
		}
	}

	handler.TrustedGatewaySecrets = []string{"new-secret"}
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "", trustedGatewayHeaders("old-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryValidate,
	}))
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected removed old secret to be rejected, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "AUTH_ERROR" {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestTrustedGatewayUsesConfiguredKeyIDWhenHeaderAbsent(t *testing.T) {
	authenticator := TrustedGatewayAuthenticator{
		GatewaySecrets: []string{"gateway-secret"},
		GatewayKeyID:   "configured-key",
	}
	req := httptest.NewRequest(http.MethodPost, "/v1/admin/registry/validate", nil)
	for key, value := range trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedGatewayKeyIDHeader: "",
		trustedPermissionsHeader:  registry.PermissionRegistryValidate,
	}) {
		req.Header.Set(key, value)
	}
	principal, err := authenticator.ResolveAdminPrincipal(req, registry.PermissionRegistryValidate)
	if err != nil {
		t.Fatalf("resolve principal: %v", err)
	}
	if principal.GatewayKeyID != "configured-key" {
		t.Fatalf("expected configured gateway key id, got %#v", principal)
	}
}

func TestTrustedGatewayActorDefaultsToPrincipalID(t *testing.T) {
	authenticator := TrustedGatewayAuthenticator{GatewaySecret: "gateway-secret"}
	req := httptest.NewRequest(http.MethodPost, "/v1/admin/registry/validate", nil)
	for key, value := range trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedActorIDHeader:     "",
		trustedPermissionsHeader: registry.PermissionRegistryValidate,
	}) {
		req.Header.Set(key, value)
	}
	principal, err := authenticator.ResolveAdminPrincipal(req, registry.PermissionRegistryValidate)
	if err != nil {
		t.Fatalf("resolve principal: %v", err)
	}
	if principal.ActorID != "principal-1" || principal.SubjectID != "principal-1" || principal.ProjectID != "project-1" {
		t.Fatalf("unexpected principal: %#v", principal)
	}
}

func TestTrustedGatewayAuthenticationFailures(t *testing.T) {
	tests := []struct {
		name      string
		secret    string
		headers   map[string]string
		status    int
		errorType string
	}{
		{
			name:      "missing server secret",
			secret:    "",
			headers:   trustedGatewayHeaders("gateway-secret", map[string]string{trustedPermissionsHeader: registry.PermissionRegistryImportReplace}),
			status:    http.StatusServiceUnavailable,
			errorType: "AUTH_SERVICE_UNAVAILABLE",
		},
		{
			name:      "missing gateway authorization",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("", map[string]string{trustedGatewayAuthorizationHeader: "", trustedPermissionsHeader: registry.PermissionRegistryImportReplace}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:   "malformed gateway authorization",
			secret: "gateway-secret",
			headers: trustedGatewayHeaders("gateway-secret", map[string]string{
				trustedGatewayAuthorizationHeader: "Token gateway-secret",
				trustedPermissionsHeader:          registry.PermissionRegistryImportReplace,
			}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:      "wrong gateway secret",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("wrong-secret", map[string]string{trustedPermissionsHeader: registry.PermissionRegistryImportReplace}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:      "missing principal",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("gateway-secret", map[string]string{trustedPrincipalIDHeader: "", trustedPermissionsHeader: registry.PermissionRegistryImportReplace}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:      "missing project",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("gateway-secret", map[string]string{trustedProjectIDHeader: "", trustedPermissionsHeader: registry.PermissionRegistryImportReplace}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:      "missing permissions",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("gateway-secret", map[string]string{trustedPermissionsHeader: ""}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:      "malformed permissions",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("gateway-secret", map[string]string{trustedPermissionsHeader: registry.PermissionRegistryImportReplace + ",," + registry.PermissionRegistryValidate}),
			status:    http.StatusUnauthorized,
			errorType: "AUTH_ERROR",
		},
		{
			name:      "permission denied",
			secret:    "gateway-secret",
			headers:   trustedGatewayHeaders("gateway-secret", map[string]string{trustedPermissionsHeader: registry.PermissionRegistryValidate}),
			status:    http.StatusForbidden,
			errorType: "AUTHZ_DENIED",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			replacer := &recordingImportReplacer{result: registry.ImportReplaceResult{}}
			handler := newPostgresImportHandlerWithReplacer(replacer)
			handler.AdminIdentityMode = AdminIdentityModeHosted
			handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
			handler.TrustedGatewaySecret = test.secret
			response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "", test.headers)
			if response.Code != test.status {
				t.Fatalf("expected status %d, got %d: %s", test.status, response.Code, response.Body.String())
			}
			var errorResponse ErrorResponse
			decodeResponse(t, response, &errorResponse)
			if errorResponse.Error.ErrorType != test.errorType {
				t.Fatalf("unexpected error response: %#v", errorResponse)
			}
			if replacer.calls != 0 {
				t.Fatalf("mutation should not run after auth failure, got %d calls", replacer.calls)
			}
		})
	}
}

func TestAdminAuthenticatorModeCombinationsFailClosed(t *testing.T) {
	tests := []struct {
		name              string
		identityMode      string
		authenticatorMode string
	}{
		{
			name:              "trusted gateway requires hosted identity mode",
			identityMode:      AdminIdentityModeLocalPrivate,
			authenticatorMode: AdminAuthenticatorModeTrustedGateway,
		},
		{
			name:              "local private authenticator requires local private mode",
			identityMode:      AdminIdentityModeHosted,
			authenticatorMode: AdminAuthenticatorModeLocalPrivate,
		},
		{
			name:              "unsupported authenticator mode",
			identityMode:      AdminIdentityModeHosted,
			authenticatorMode: "bogus",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			handler := newTestHandler(t, "")
			handler.AdminIdentityMode = test.identityMode
			handler.AdminAuthenticatorMode = test.authenticatorMode
			handler.TrustedGatewaySecret = "gateway-secret"
			response := performRequest(handler, http.MethodPost, "/v1/admin/registry/validate", nil, "secret")
			if response.Code != http.StatusServiceUnavailable {
				t.Fatalf("expected status 503, got %d: %s", response.Code, response.Body.String())
			}
			var errorResponse ErrorResponse
			decodeResponse(t, response, &errorResponse)
			if errorResponse.Error.ErrorType != "AUTH_SERVICE_UNAVAILABLE" || !errorResponse.Error.Retryable {
				t.Fatalf("unexpected error response: %#v", errorResponse)
			}
		})
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

func TestImportReplaceRegistryMarksReplayedIdempotencyResponse(t *testing.T) {
	result := registry.ImportReplaceResult{
		RegistryFingerprint:         "sha256:new",
		PreviousRegistryFingerprint: "sha256:old",
		SnapshotVersion:             "snapshot_http_import_v1",
		Noop:                        false,
		Counts:                      registry.ImportReplaceCounts{Projects: 1, Providers: 1},
		Replayed:                    true,
		IdempotencyRecordID:         42,
	}
	replacer := &recordingImportReplacer{result: result}
	handler := newPostgresImportHandlerWithReplacer(replacer)
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/import-replace", importReplaceBody(t), "secret", map[string]string{
		"X-Request-ID":    "req-replay",
		"Idempotency-Key": "idem-replay",
	})
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	if response.Header().Get("Idempotency-Replayed") != "true" || response.Header().Get("Idempotency-Record-ID") != "42" {
		t.Fatalf("expected replay headers, got %#v", response.Header())
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
		{"REGISTRY_PARTITION_VIOLATION", "caller", false, http.StatusForbidden},
		{"REGISTRY_MUTATION_CONFLICT", "platform", true, http.StatusConflict},
		{"PERSISTENT_STORE_READ_FAILED", "platform", true, http.StatusServiceUnavailable},
		{"PERSISTENT_STORE_WRITE_FAILED", "platform", true, http.StatusServiceUnavailable},
		{"AUDIT_WRITE_FAILED", "platform", true, http.StatusInternalServerError},
		{"IDEMPOTENCY_KEY_CONFLICT", "caller", false, http.StatusConflict},
		{"IDEMPOTENCY_REQUEST_IN_PROGRESS", "platform", true, http.StatusConflict},
		{"IDEMPOTENCY_STORE_READ_FAILED", "platform", true, http.StatusServiceUnavailable},
		{"IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, http.StatusServiceUnavailable},
		{"IDEMPOTENCY_RESPONSE_REPLAY_FAILED", "platform", true, http.StatusInternalServerError},
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

func TestProjectPartitionReplaceRequiresTrustedGatewayPrincipal(t *testing.T) {
	replacer := &recordingProjectPartitionReplacer{}
	handler := newPostgresProjectPartitionHandlerWithReplacer(replacer)
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBody(t), "secret", map[string]string{
		"X-Request-ID":    "req-partition",
		"Idempotency-Key": "idem-partition",
	})
	if response.Code != http.StatusForbidden {
		t.Fatalf("expected local/private principal to be rejected with 403, got %d: %s", response.Code, response.Body.String())
	}
	if replacer.calls != 0 {
		t.Fatalf("mutation should not run for local/private principal, got %d calls", replacer.calls)
	}
}

func TestProjectPartitionReplaceRequiresPermissionAndHeaders(t *testing.T) {
	replacer := &recordingProjectPartitionReplacer{}
	handler := newPostgresProjectPartitionHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"

	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBody(t), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryImportReplace,
		"X-Request-ID":           "req-partition",
		"Idempotency-Key":        "idem-partition",
	}))
	if response.Code != http.StatusForbidden {
		t.Fatalf("expected broad import permission to be insufficient, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBody(t), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryProjectPartitionReplace,
	}))
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing request id status 400, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBody(t), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryProjectPartitionReplace,
		"X-Request-ID":           "req-partition",
	}))
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing idempotency key status 400, got %d: %s", response.Code, response.Body.String())
	}
	if replacer.calls != 0 {
		t.Fatalf("mutation should not run before required headers, got %d calls", replacer.calls)
	}
}

func TestProjectPartitionReplaceRejectsInvalidBodies(t *testing.T) {
	replacer := &recordingProjectPartitionReplacer{}
	handler := newPostgresProjectPartitionHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	headers := trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryProjectPartitionReplace,
		"X-Request-ID":           "req-partition",
		"Idempotency-Key":        "idem-partition",
	})

	response := performRawRequest(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", []byte(`{`), "", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected invalid json status 400, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", map[string]any{"source": "missing-registry"}, "", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing registry status 400, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", map[string]any{
		"registry":             validRegistry(),
		"partition_project_id": "caller-project",
	}, "", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected identity override status 400, got %d: %s", response.Code, response.Body.String())
	}

	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", map[string]any{
		"registry": validRegistry(),
		"dry_run":  true,
	}, "", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected dry_run status 400, got %d: %s", response.Code, response.Body.String())
	}
	if replacer.calls != 0 {
		t.Fatalf("mutation should not run for invalid bodies, got %d calls", replacer.calls)
	}
}

func TestProjectPartitionReplaceReturnsPartitionEvidenceAndOptions(t *testing.T) {
	result := registry.ProjectPartitionReplaceResult{
		RegistryFingerprint:         "sha256:new",
		PreviousRegistryFingerprint: "sha256:old",
		SnapshotVersion:             "snapshot_partition_v1",
		Counts: registry.ImportReplaceCounts{
			Projects:           2,
			APIKeys:            2,
			Capabilities:       1,
			Providers:          1,
			CredentialMetadata: 1,
			RoutingPolicies:    1,
			SnapshotConfigs:    1,
		},
		PartitionDecision: registry.ProjectPartitionMutationDecision{
			PartitionProjectID: "project-2",
			DiffFingerprint:    "sha256:diff",
			Counts: registry.ProjectPartitionMutationCounts{
				APIKeysChanged:            1,
				CredentialMetadataChanged: 1,
			},
		},
	}
	replacer := &recordingProjectPartitionReplacer{result: result}
	handler := newPostgresProjectPartitionHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBodyWithSource(t, "partition-upload"), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedActorIDHeader:     "trusted-actor",
		trustedProjectIDHeader:   "project-2",
		trustedPermissionsHeader: registry.PermissionRegistryProjectPartitionReplace,
		"X-Request-ID":           " req-partition ",
		"Idempotency-Key":        " idem-partition ",
	}))
	if response.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d: %s", response.Code, response.Body.String())
	}
	var replaced ProjectPartitionReplaceResponse
	decodeResponse(t, response, &replaced)
	if replaced.RegistryStore != "postgres" || replaced.PartitionProjectID != "project-2" || replaced.PartitionDiffFingerprint != "sha256:diff" || replaced.PartitionCounts.APIKeysChanged != 1 {
		t.Fatalf("unexpected partition response: %#v", replaced)
	}
	if replacer.calls != 1 {
		t.Fatalf("expected one replacer call, got %d", replacer.calls)
	}
	if replacer.options.Principal.ProjectID != "project-2" || replacer.options.Principal.ActorID != "trusted-actor" || replacer.options.RequestID != "req-partition" || replacer.options.IdempotencyKey != "idem-partition" || replacer.options.Source != "partition-upload" {
		t.Fatalf("unexpected partition options: %#v", replacer.options)
	}
}

func TestProjectPartitionReplaceMapsPartitionViolation(t *testing.T) {
	replacer := &recordingProjectPartitionReplacer{
		err: registry.RegistryMutationError{
			ErrorType:  "REGISTRY_PARTITION_VIOLATION",
			Scope:      "caller",
			Retryable:  false,
			Underlying: fmt.Errorf("cross project change"),
		},
	}
	handler := newPostgresProjectPartitionHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBody(t), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryProjectPartitionReplace,
		"X-Request-ID":           "req-partition",
		"Idempotency-Key":        "idem-partition",
	}))
	if response.Code != http.StatusForbidden {
		t.Fatalf("expected status 403, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "REGISTRY_PARTITION_VIOLATION" || errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestProjectPartitionReplaceReplayUsesOKStatus(t *testing.T) {
	result := registry.ProjectPartitionReplaceResult{
		RegistryFingerprint: "sha256:new",
		SnapshotVersion:     "snapshot_partition_v1",
		Replayed:            true,
		IdempotencyRecordID: 77,
		PartitionDecision: registry.ProjectPartitionMutationDecision{
			PartitionProjectID: "project-1",
			DiffFingerprint:    "sha256:diff",
		},
	}
	replacer := &recordingProjectPartitionReplacer{result: result}
	handler := newPostgresProjectPartitionHandlerWithReplacer(replacer)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/admin/registry/project-partition/replace", importReplaceBody(t), "", trustedGatewayHeaders("gateway-secret", map[string]string{
		trustedPermissionsHeader: registry.PermissionRegistryProjectPartitionReplace,
		"X-Request-ID":           "req-partition",
		"Idempotency-Key":        "idem-partition",
	}))
	if response.Code != http.StatusOK {
		t.Fatalf("expected replay status 200, got %d: %s", response.Code, response.Body.String())
	}
	if response.Header().Get("Idempotency-Replayed") != "true" || response.Header().Get("Idempotency-Record-ID") != "77" {
		t.Fatalf("expected replay headers, got %#v", response.Header())
	}
}

func TestHostedPermissionPolicyMutationRequiresTrustedGatewayPrincipal(t *testing.T) {
	mutator := &recordingHostedPolicyMutator{}
	handler := newPostgresHostedPolicyMutationHandlerWithMutator(mutator)
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation": registry.HostedPermissionPolicyMutationBeginDraftOperation,
	}, "secret", map[string]string{"X-Request-ID": "req-policy-begin"})
	if response.Code != http.StatusForbidden {
		t.Fatalf("expected status 403, got %d: %s", response.Code, response.Body.String())
	}
	if mutator.calls != 0 {
		t.Fatalf("mutation should not run for local/private principal, got %d calls", mutator.calls)
	}
}

func TestTrustedGatewayHostedPermissionPolicyMutationBeginsDraft(t *testing.T) {
	result := registry.HostedPermissionPolicyMutationDurableResult{
		Operation:          registry.HostedPermissionPolicyMutationBeginDraftOperation,
		ProjectID:          "project-2",
		OrganizationID:     "org-1",
		ActorID:            "trusted-actor",
		PolicySource:       "hosted_permission_store",
		DraftID:            "draft-policy-v2",
		BasePolicyVersion:  "policy-v1",
		DraftPolicyVersion: "policy-v2",
	}
	mutator := &recordingHostedPolicyMutator{result: result}
	handler := newPostgresHostedPolicyMutationHandlerWithMutator(mutator)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"

	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation":            registry.HostedPermissionPolicyMutationBeginDraftOperation,
		"policy_source":        "hosted_permission_store",
		"base_policy_version":  "policy-v1",
		"draft_policy_version": "policy-v2",
	}, "", trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-policy-begin",
		trustedActorIDHeader:     "trusted-actor",
		trustedProjectIDHeader:   "project-2",
		trustedPermissionsHeader: registry.PermissionHostedPermissionPolicyDraftWrite,
	}))
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if mutator.operation != registry.HostedPermissionPolicyMutationBeginDraftOperation || mutator.calls != 1 {
		t.Fatalf("unexpected mutator call: op=%q calls=%d", mutator.operation, mutator.calls)
	}
	if mutator.options.ProjectID != "project-2" || mutator.options.OrganizationID != "org-1" || mutator.options.ActorID != "trusted-actor" || mutator.options.RequestID != "req-policy-begin" {
		t.Fatalf("trusted principal scope was not forwarded: %#v", mutator.options)
	}
	if mutator.options.BasePolicyVersion != "policy-v1" || mutator.options.DraftPolicyVersion != "policy-v2" || mutator.options.IdempotencyKey != "" {
		t.Fatalf("unexpected mutation options: %#v", mutator.options)
	}
	var body HostedPermissionPolicyMutationResponse
	decodeResponse(t, response, &body)
	if body.Result.DraftID != "draft-policy-v2" || body.RegistryStore != "postgres" {
		t.Fatalf("unexpected response: %#v", body)
	}
}

func TestTrustedGatewayHostedPermissionPolicyMutationAppliesDraftChange(t *testing.T) {
	mutator := &recordingHostedPolicyMutator{result: registry.HostedPermissionPolicyMutationDurableResult{
		Operation:         registry.HostedPermissionPolicyMutationApplyChangeOperation,
		PolicyFingerprint: "sha256:draft",
	}}
	handler := newPostgresHostedPolicyMutationHandlerWithMutator(mutator)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"

	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation": registry.HostedPermissionPolicyMutationApplyChangeOperation,
		"draft_id":  "draft-policy-v2",
		"change": map[string]any{
			"object_type": "permission_grant",
			"operation":   "upsert",
			"object_id":   "grant-promote",
			"patch_summary": map[string]string{
				"permission": registry.PermissionHostedPermissionPolicyPromote,
			},
		},
	}, "", trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-policy-change",
		trustedPermissionsHeader: registry.PermissionHostedPermissionPolicyDraftWrite,
	}))
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if mutator.operation != registry.HostedPermissionPolicyMutationApplyChangeOperation || mutator.change.ObjectType != "permission_grant" || mutator.change.PatchSummary["permission"] != registry.PermissionHostedPermissionPolicyPromote {
		t.Fatalf("unexpected draft change forwarded: op=%q change=%#v", mutator.operation, mutator.change)
	}
}

func TestTrustedGatewayHostedPermissionPolicyMutationPromoteRequiresIdempotencyAndReturnsReplayHeaders(t *testing.T) {
	mutator := &recordingHostedPolicyMutator{}
	handler := newPostgresHostedPolicyMutationHandlerWithMutator(mutator)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	headers := trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-policy-promote",
		trustedPermissionsHeader: registry.PermissionHostedPermissionPolicyPromote,
	})
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation": registry.HostedPermissionPolicyMutationPromoteOperation,
		"draft_id":  "draft-policy-v2",
	}, "", headers)
	if response.Code != http.StatusBadRequest {
		t.Fatalf("expected missing idempotency status 400, got %d: %s", response.Code, response.Body.String())
	}
	if mutator.calls != 0 {
		t.Fatalf("mutation should not run before required headers, got %d calls", mutator.calls)
	}

	mutator.result = registry.HostedPermissionPolicyMutationDurableResult{
		Operation:           registry.HostedPermissionPolicyMutationPromoteOperation,
		Replayed:            true,
		PolicyVersion:       "policy-v2",
		IdempotencyRecordID: 7,
	}
	headers["Idempotency-Key"] = "idem-policy-promote"
	response = performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation":            registry.HostedPermissionPolicyMutationPromoteOperation,
		"draft_id":             "draft-policy-v2",
		"mutation_fingerprint": "sha256:policy-v2",
		"draft_policy_version": "policy-v2",
		"base_policy_version":  "policy-v1",
	}, "", headers)
	if response.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", response.Code, response.Body.String())
	}
	if response.Header().Get("Idempotency-Replayed") != "true" || response.Header().Get("Idempotency-Record-ID") != "7" {
		t.Fatalf("expected replay headers, got %#v", response.Header())
	}
	if mutator.options.IdempotencyKey != "idem-policy-promote" || mutator.options.DraftID != "draft-policy-v2" || mutator.options.MutationFingerprint != "sha256:policy-v2" {
		t.Fatalf("unexpected promote options: %#v", mutator.options)
	}
}

func TestTrustedGatewayHostedPermissionPolicyMutationMapsPolicyErrors(t *testing.T) {
	mutator := &recordingHostedPolicyMutator{err: registry.RegistryMutationError{
		ErrorType:  "POLICY_VERSION_CONFLICT",
		Scope:      "caller",
		Retryable:  false,
		Underlying: fmt.Errorf("base policy is stale"),
	}}
	handler := newPostgresHostedPolicyMutationHandlerWithMutator(mutator)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation":             registry.HostedPermissionPolicyMutationRollbackOperation,
		"target_policy_version": "policy-v1",
	}, "", trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-policy-rollback",
		"Idempotency-Key":        "idem-policy-rollback",
		trustedPermissionsHeader: registry.PermissionHostedPermissionPolicyRollback,
	}))
	if response.Code != http.StatusConflict {
		t.Fatalf("expected status 409, got %d: %s", response.Code, response.Body.String())
	}
	var errorResponse ErrorResponse
	decodeResponse(t, response, &errorResponse)
	if errorResponse.Error.ErrorType != "POLICY_VERSION_CONFLICT" || errorResponse.Error.Retryable {
		t.Fatalf("unexpected error response: %#v", errorResponse)
	}
}

func TestTrustedGatewayHostedPermissionPolicyMutationEndpointDogfood(t *testing.T) {
	mutator := newHarnessHostedPolicyMutator()
	handler := newPostgresHostedPolicyMutationHandlerWithMutator(mutator)
	handler.AdminIdentityMode = AdminIdentityModeHosted
	handler.AdminAuthenticatorMode = AdminAuthenticatorModeTrustedGateway
	handler.TrustedGatewaySecret = "gateway-secret"

	before := mutator.harness.ResolvePermission("dogfood/idp/admin", registry.PermissionHostedPermissionPolicyPromote, time.Date(2026, 6, 2, 0, 0, 0, 0, time.UTC))
	if before.Allowed {
		t.Fatalf("expected promote permission denied before dogfood mutation: %#v", before)
	}

	begin := hostedPolicyMutationDogfoodRequest(t, handler, registry.HostedPermissionPolicyMutationBeginDraftOperation, registry.PermissionHostedPermissionPolicyDraftWrite, "", map[string]any{
		"policy_source":        "hosted-permission-policy-store-fixture",
		"base_policy_version":  "hosted-permission-policy-v1",
		"draft_policy_version": "hosted-permission-policy-v2",
	})
	if begin.Result.DraftID == "" || begin.Result.BasePolicyVersion != "hosted-permission-policy-v1" {
		t.Fatalf("unexpected begin result: %#v", begin)
	}

	change := hostedPolicyMutationDogfoodRequest(t, handler, registry.HostedPermissionPolicyMutationApplyChangeOperation, registry.PermissionHostedPermissionPolicyDraftWrite, "", map[string]any{
		"draft_id": begin.Result.DraftID,
		"change": map[string]any{
			"object_type": "permission_grant",
			"operation":   "upsert",
			"object_id":   "policy-admin:promote",
			"patch_summary": map[string]string{
				"role_id":    "policy-admin",
				"permission": registry.PermissionHostedPermissionPolicyPromote,
				"scope_type": "project",
				"status":     "active",
			},
		},
	})
	if change.Result.PolicyFingerprint == "" {
		t.Fatalf("expected draft change fingerprint evidence: %#v", change)
	}

	review := hostedPolicyMutationDogfoodRequest(t, handler, registry.HostedPermissionPolicyMutationRequestReviewOperation, registry.PermissionHostedPermissionPolicyRequestReview, "", map[string]any{
		"draft_id": begin.Result.DraftID,
	})
	if review.Result.DraftPolicyVersion != "hosted-permission-policy-v2" {
		t.Fatalf("unexpected review result: %#v", review)
	}

	promote := hostedPolicyMutationDogfoodRequest(t, handler, registry.HostedPermissionPolicyMutationPromoteOperation, registry.PermissionHostedPermissionPolicyPromote, "dogfood-promote-key", map[string]any{
		"draft_id":             begin.Result.DraftID,
		"base_policy_version":  "hosted-permission-policy-v1",
		"draft_policy_version": "hosted-permission-policy-v2",
	})
	if promote.Result.PolicyVersion != "hosted-permission-policy-v2" || promote.Result.PreviousPolicyVersion != "hosted-permission-policy-v1" {
		t.Fatalf("unexpected promote result: %#v", promote)
	}
	afterPromote := mutator.harness.ResolvePermission("dogfood/idp/admin", registry.PermissionHostedPermissionPolicyPromote, time.Date(2026, 6, 2, 0, 1, 0, 0, time.UTC))
	if !afterPromote.Allowed || afterPromote.PolicyVersion != "hosted-permission-policy-v2" {
		t.Fatalf("expected promoted permission decision, got %#v", afterPromote)
	}

	replayResponse := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", map[string]any{
		"operation":            registry.HostedPermissionPolicyMutationPromoteOperation,
		"draft_id":             begin.Result.DraftID,
		"base_policy_version":  "hosted-permission-policy-v1",
		"draft_policy_version": "hosted-permission-policy-v2",
	}, "", trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-dogfood-promote-replay",
		"Idempotency-Key":        "dogfood-promote-key",
		trustedPermissionsHeader: registry.PermissionHostedPermissionPolicyPromote,
	}))
	if replayResponse.Code != http.StatusOK {
		t.Fatalf("expected replay status 200, got %d: %s", replayResponse.Code, replayResponse.Body.String())
	}
	if replayResponse.Header().Get("Idempotency-Replayed") != "true" {
		t.Fatalf("expected replay header, got %#v", replayResponse.Header())
	}
	var replay HostedPermissionPolicyMutationResponse
	decodeResponse(t, replayResponse, &replay)
	if !replay.Result.Replayed || replay.Result.PolicyFingerprint != promote.Result.PolicyFingerprint {
		t.Fatalf("unexpected replay result: first=%#v replay=%#v", promote, replay)
	}

	rollback := hostedPolicyMutationDogfoodRequest(t, handler, registry.HostedPermissionPolicyMutationRollbackOperation, registry.PermissionHostedPermissionPolicyRollback, "dogfood-rollback-key", map[string]any{
		"target_policy_version": "hosted-permission-policy-v1",
	})
	if rollback.Result.TargetPolicyVersion != "hosted-permission-policy-v1" || rollback.Result.PreviousPolicyVersion != "hosted-permission-policy-v2" {
		t.Fatalf("unexpected rollback result: %#v", rollback)
	}
	afterRollback := mutator.harness.ResolvePermission("dogfood/idp/admin", registry.PermissionHostedPermissionPolicyPromote, time.Date(2026, 6, 2, 0, 2, 0, 0, time.UTC))
	if afterRollback.Allowed || afterRollback.PolicyVersion != rollback.Result.PolicyVersion {
		t.Fatalf("expected rollback to remove promote permission, got %#v rollback=%#v", afterRollback, rollback)
	}
	if mutator.rawIdempotencyKeyLeaked("dogfood-promote-key") || mutator.rawIdempotencyKeyLeaked("dogfood-rollback-key") {
		t.Fatalf("raw idempotency key leaked into dogfood audit metadata: %#v", mutator.harness.Audits)
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

func newPostgresProjectPartitionHandlerWithReplacer(replacer *recordingProjectPartitionReplacer) Handler {
	return Handler{
		RegistryStore:            "postgres",
		RegistrySource:           "postgres",
		AdminToken:               "secret",
		ProjectPartitionReplacer: replacer,
		Now: func() time.Time {
			return time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC)
		},
	}
}

func newPostgresHostedPolicyMutationHandlerWithMutator(mutator HostedPermissionPolicyMutator) Handler {
	return Handler{
		RegistryStore:       "postgres",
		RegistrySource:      "postgres",
		AdminToken:          "secret",
		HostedPolicyMutator: mutator,
		Now: func() time.Time {
			return time.Date(2026, 5, 31, 1, 2, 3, 0, time.UTC)
		},
	}
}

func hostedPolicyMutationDogfoodRequest(t *testing.T, handler Handler, operation string, permission string, idempotencyKey string, fields map[string]any) HostedPermissionPolicyMutationResponse {
	t.Helper()
	body := map[string]any{"operation": operation}
	for key, value := range fields {
		body[key] = value
	}
	headers := trustedGatewayHeaders("gateway-secret", map[string]string{
		"X-Request-ID":           "req-dogfood-" + strings.ReplaceAll(strings.TrimPrefix(operation, "policy_mutation."), "_", "-"),
		trustedPermissionsHeader: permission,
	})
	if idempotencyKey != "" {
		headers["Idempotency-Key"] = idempotencyKey
	}
	response := performRequestWithHeaders(handler, http.MethodPost, "/v1/private/hosted/permission-policy/mutation", body, "", headers)
	if response.Code != http.StatusOK {
		t.Fatalf("expected dogfood %s status 200, got %d: %s", operation, response.Code, response.Body.String())
	}
	var decoded HostedPermissionPolicyMutationResponse
	decodeResponse(t, response, &decoded)
	if decoded.RegistryStore != "postgres" || decoded.Result.Operation != operation {
		t.Fatalf("unexpected dogfood %s response: %#v", operation, decoded)
	}
	return decoded
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

func trustedGatewayHeaders(secret string, overrides map[string]string) map[string]string {
	headers := map[string]string{
		trustedGatewayAuthorizationHeader: "Bearer " + secret,
		trustedGatewayKeyIDHeader:         "key-1",
		trustedPrincipalIDHeader:          "principal-1",
		trustedProjectIDHeader:            "project-1",
		trustedOrganizationIDHeader:       "org-1",
		trustedTokenIDHeader:              "token-1",
		trustedRolesHeader:                "control_plane_admin",
		trustedPermissionsHeader:          registry.PermissionRegistryValidate,
	}
	for key, value := range overrides {
		if value == "" {
			delete(headers, key)
			continue
		}
		headers[key] = value
	}
	return headers
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

type recordingProjectPartitionReplacer struct {
	result  registry.ProjectPartitionReplaceResult
	err     error
	calls   int
	options registry.ProjectPartitionReplaceOptions
	reg     registry.Registry
}

func (r *recordingProjectPartitionReplacer) ReplaceProjectPartitionRegistry(ctx context.Context, reg registry.Registry, opts registry.ProjectPartitionReplaceOptions) (registry.ProjectPartitionReplaceResult, error) {
	r.calls++
	r.reg = reg
	r.options = opts
	if r.err != nil {
		return registry.ProjectPartitionReplaceResult{}, r.err
	}
	return r.result, nil
}

type recordingHostedPolicyMutator struct {
	result    registry.HostedPermissionPolicyMutationDurableResult
	err       error
	calls     int
	operation string
	options   registry.HostedPermissionPolicyMutationOptions
	change    registry.HostedPermissionPolicyDraftChange
}

func (m *recordingHostedPolicyMutator) BeginHostedPermissionPolicyDraft(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationBeginDraftOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	return m.finish()
}

func (m *recordingHostedPolicyMutator) ApplyHostedPermissionPolicyDraftChange(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions, change registry.HostedPermissionPolicyDraftChange) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationApplyChangeOperation, opts, change)
	return m.finish()
}

func (m *recordingHostedPolicyMutator) RequestHostedPermissionPolicyReview(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationRequestReviewOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	return m.finish()
}

func (m *recordingHostedPolicyMutator) PromoteHostedPermissionPolicyDraft(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationPromoteOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	return m.finish()
}

func (m *recordingHostedPolicyMutator) RollbackHostedPermissionPolicy(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationRollbackOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	return m.finish()
}

func (m *recordingHostedPolicyMutator) record(operation string, opts registry.HostedPermissionPolicyMutationOptions, change registry.HostedPermissionPolicyDraftChange) {
	m.calls++
	m.operation = operation
	m.options = opts
	m.change = change
}

func (m *recordingHostedPolicyMutator) finish() (registry.HostedPermissionPolicyMutationDurableResult, error) {
	if m.err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, m.err
	}
	return m.result, nil
}

type harnessHostedPolicyMutator struct {
	recordingHostedPolicyMutator
	harness *registry.HostedPermissionPolicyMutationHarness
}

func newHarnessHostedPolicyMutator() *harnessHostedPolicyMutator {
	return &harnessHostedPolicyMutator{
		harness: registry.NewHostedPermissionPolicyMutationHarness(
			"policy-mutation-project",
			"policy-mutation-org",
			"hosted-permission-policy-store-fixture",
			"hosted-permission-policy-v1",
			registry.HostedPermissionPolicySnapshot{
				Subjects: []registry.HostedPermissionPolicySubject{
					{ID: "subject-policy-admin", ExternalSubjectRef: "dogfood/idp/admin", Status: "active"},
				},
				Memberships: []registry.HostedPermissionPolicyMembership{
					{SubjectID: "subject-policy-admin", ActorID: "actor-policy-admin", ProjectID: "policy-mutation-project", OrganizationID: "policy-mutation-org", Status: "active"},
				},
				Roles: []registry.HostedPermissionPolicyRole{
					{ID: "policy-admin", Status: "active"},
				},
				RoleBindings: []registry.HostedPermissionPolicyRoleBinding{
					{SubjectID: "subject-policy-admin", ProjectID: "policy-mutation-project", OrganizationID: "policy-mutation-org", RoleID: "policy-admin", Status: "active"},
				},
				PermissionGrants: []registry.HostedPermissionPolicyGrant{
					{RoleID: "policy-admin", Permission: registry.PermissionHostedPermissionPolicyRequestReview, ScopeType: "project", Status: "active"},
				},
			},
		),
	}
}

func (m *harnessHostedPolicyMutator) BeginHostedPermissionPolicyDraft(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationBeginDraftOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	draft, err := m.harness.BeginDraft(opts.BasePolicyVersion, opts.DraftPolicyVersion)
	if err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	return registry.HostedPermissionPolicyMutationDurableResult{
		Operation:          registry.HostedPermissionPolicyMutationBeginDraftOperation,
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		PolicySource:       m.harness.PolicySource,
		DraftID:            draft.ID,
		BasePolicyVersion:  draft.BaseVersion,
		DraftPolicyVersion: draft.Version,
		PolicyVersion:      m.harness.ActiveVersion,
		PolicyFingerprint:  m.harness.ActiveFingerprint,
		AdminAuditEventID:  int64(len(m.harness.Audits)),
	}, nil
}

func (m *harnessHostedPolicyMutator) ApplyHostedPermissionPolicyDraftChange(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions, change registry.HostedPermissionPolicyDraftChange) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationApplyChangeOperation, opts, change)
	draft, err := m.draft(opts.DraftID)
	if err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	switch change.ObjectType {
	case "permission_grant":
		draft.UpsertGrant(registry.HostedPermissionPolicyGrant{
			RoleID:     change.PatchSummary["role_id"],
			Permission: change.PatchSummary["permission"],
			ScopeType:  change.PatchSummary["scope_type"],
			Status:     change.PatchSummary["status"],
		})
	default:
		return registry.HostedPermissionPolicyMutationDurableResult{}, registry.RegistryMutationError{ErrorType: "POLICY_STATE_CONFLICT", Scope: "caller", Underlying: fmt.Errorf("unsupported dogfood change object type %q", change.ObjectType)}
	}
	validation, err := m.harness.ValidateDraft(draft.ID)
	if err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	return registry.HostedPermissionPolicyMutationDurableResult{
		Operation:          registry.HostedPermissionPolicyMutationApplyChangeOperation,
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		PolicySource:       m.harness.PolicySource,
		DraftID:            draft.ID,
		BasePolicyVersion:  draft.BaseVersion,
		DraftPolicyVersion: draft.Version,
		PolicyFingerprint:  validation.PolicyFingerprint,
		AdminAuditEventID:  int64(len(m.harness.Audits)),
	}, nil
}

func (m *harnessHostedPolicyMutator) RequestHostedPermissionPolicyReview(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationRequestReviewOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	draft, err := m.draft(opts.DraftID)
	if err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := m.harness.RequestReview(draft.ID); err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	return registry.HostedPermissionPolicyMutationDurableResult{
		Operation:          registry.HostedPermissionPolicyMutationRequestReviewOperation,
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		PolicySource:       m.harness.PolicySource,
		DraftID:            draft.ID,
		BasePolicyVersion:  draft.BaseVersion,
		DraftPolicyVersion: draft.Version,
		PolicyFingerprint:  opts.MutationFingerprint,
		AdminAuditEventID:  int64(len(m.harness.Audits)),
	}, nil
}

func (m *harnessHostedPolicyMutator) PromoteHostedPermissionPolicyDraft(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationPromoteOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	result, err := m.harness.PromoteDraft(opts.DraftID, registry.HostedPermissionPolicyMutationRequest{
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		IdempotencyKey:     opts.IdempotencyKey,
		BasePolicyVersion:  opts.BasePolicyVersion,
		DraftPolicyVersion: opts.DraftPolicyVersion,
	})
	if err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	return hostedPolicyMutationDurableResultFromHarness(result), nil
}

func (m *harnessHostedPolicyMutator) RollbackHostedPermissionPolicy(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	m.record(registry.HostedPermissionPolicyMutationRollbackOperation, opts, registry.HostedPermissionPolicyDraftChange{})
	result, err := m.harness.RollbackPolicy(opts.TargetPolicyVersion, registry.HostedPermissionPolicyMutationRequest{
		ProjectID:           opts.ProjectID,
		OrganizationID:      opts.OrganizationID,
		ActorID:             opts.ActorID,
		RequestID:           opts.RequestID,
		IdempotencyKey:      opts.IdempotencyKey,
		TargetPolicyVersion: opts.TargetPolicyVersion,
	})
	if err != nil {
		return registry.HostedPermissionPolicyMutationDurableResult{}, err
	}
	return hostedPolicyMutationDurableResultFromHarness(result), nil
}

func (m *harnessHostedPolicyMutator) draft(draftID string) (*registry.HostedPermissionPolicyDraft, error) {
	draft, ok := m.harness.Drafts[draftID]
	if !ok {
		return nil, registry.RegistryMutationError{ErrorType: "POLICY_STATE_CONFLICT", Scope: "caller", Underlying: fmt.Errorf("draft %q was not found", draftID)}
	}
	return draft, nil
}

func (m *harnessHostedPolicyMutator) rawIdempotencyKeyLeaked(raw string) bool {
	for _, event := range m.harness.Audits {
		for key, value := range event.Metadata {
			if strings.Contains(key, raw) || strings.Contains(value, raw) {
				return true
			}
		}
	}
	return false
}

func hostedPolicyMutationDurableResultFromHarness(result registry.HostedPermissionPolicyMutationResult) registry.HostedPermissionPolicyMutationDurableResult {
	return registry.HostedPermissionPolicyMutationDurableResult{
		Operation:                 result.Operation,
		ProjectID:                 result.ProjectID,
		OrganizationID:            result.OrganizationID,
		ActorID:                   result.ActorID,
		RequestID:                 result.RequestID,
		Replayed:                  result.Replayed,
		PolicySource:              result.PolicySource,
		BasePolicyVersion:         result.BasePolicyVersion,
		DraftPolicyVersion:        result.DraftPolicyVersion,
		PreviousPolicyVersion:     result.PreviousPolicyVersion,
		TargetPolicyVersion:       result.TargetPolicyVersion,
		PolicyVersion:             result.PolicyVersion,
		PreviousPolicyFingerprint: result.PreviousPolicyFingerprint,
		PolicyFingerprint:         result.PolicyFingerprint,
		IdempotencyRecordID:       result.AuditEventID,
		AdminAuditEventID:         result.AuditEventID,
	}
}

type recordingAdminAuthenticator struct {
	principal          registry.AdminPrincipal
	err                error
	requiredPermission string
}

func (a *recordingAdminAuthenticator) ResolveAdminPrincipal(r *http.Request, requiredPermission string) (registry.AdminPrincipal, error) {
	a.requiredPermission = requiredPermission
	if a.err != nil {
		return registry.AdminPrincipal{}, a.err
	}
	return a.principal, nil
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
