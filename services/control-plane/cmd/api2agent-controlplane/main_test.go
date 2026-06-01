package main

import (
	"bytes"
	"context"
	"database/sql"
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"api2agent/services/control-plane/internal/httpapi"
	"api2agent/services/control-plane/internal/registry"
)

func TestRequiresLocalAdminToken(t *testing.T) {
	tests := []struct {
		name              string
		identityMode      string
		authenticatorMode string
		want              bool
	}{
		{
			name: "default local private",
			want: true,
		},
		{
			name:         "explicit local private identity",
			identityMode: httpapi.AdminIdentityModeLocalPrivate,
			want:         true,
		},
		{
			name:              "explicit local private authenticator",
			identityMode:      httpapi.AdminIdentityModeHosted,
			authenticatorMode: httpapi.AdminAuthenticatorModeLocalPrivate,
			want:              true,
		},
		{
			name:              "hosted trusted gateway",
			identityMode:      httpapi.AdminIdentityModeHosted,
			authenticatorMode: httpapi.AdminAuthenticatorModeTrustedGateway,
			want:              false,
		},
		{
			name:         "hosted without authenticator fails closed at request time",
			identityMode: httpapi.AdminIdentityModeHosted,
			want:         false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := requiresLocalAdminToken(test.identityMode, test.authenticatorMode); got != test.want {
				t.Fatalf("requiresLocalAdminToken() = %t, want %t", got, test.want)
			}
		})
	}
}

func TestParseTrustedGatewaySecrets(t *testing.T) {
	got := parseTrustedGatewaySecrets(" old-secret, new-secret ,, old-secret ")
	want := []string{"old-secret", "new-secret"}
	if len(got) != len(want) {
		t.Fatalf("parseTrustedGatewaySecrets() = %#v, want %#v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("parseTrustedGatewaySecrets() = %#v, want %#v", got, want)
		}
	}
}

func TestOpenRegistryRuntimeHostedPolicyMutatorBoundary(t *testing.T) {
	registryPath := filepath.Join(t.TempDir(), "registry.json")
	if err := os.WriteFile(registryPath, []byte(`{"projects":[],"api_keys":[],"capabilities":[],"providers":[],"routing_policy":{"strategy":"first"},"snapshot":{"version":"test","ttl":"1h","source":"test"}}`), 0o600); err != nil {
		t.Fatalf("write registry fixture: %v", err)
	}
	fileRuntime, err := openRegistryRuntime(context.Background(), "file", registryPath, "")
	if err != nil {
		t.Fatalf("open file runtime: %v", err)
	}
	defer fileRuntime.Close()
	if fileRuntime.StoreName != "file" || fileRuntime.HostedPolicyMutator != nil {
		t.Fatalf("file runtime must not expose hosted policy mutator: %#v", fileRuntime)
	}

	restore := openPostgresDBForRuntime
	t.Cleanup(func() { openPostgresDBForRuntime = restore })
	openPostgresDBForRuntime = func(ctx context.Context, dsn string) (*sql.DB, error) {
		return nil, fmt.Errorf("sentinel no database")
	}
	_, err = openRegistryRuntime(context.Background(), "postgres", "", "postgres://example")
	if err == nil || err.Error() != "sentinel no database" {
		t.Fatalf("expected postgres opener error, got %v", err)
	}

	adapter := postgresHostedPermissionPolicyMutator{}
	var mutator httpapi.HostedPermissionPolicyMutator = adapter
	_, err = mutator.PromoteHostedPermissionPolicyDraft(context.Background(), registry.HostedPermissionPolicyMutationOptions{
		ProjectID:           "project-a",
		OrganizationID:      "org-a",
		ActorID:             "actor-a",
		RequestID:           "req-promote",
		IdempotencyKey:      "idem-promote",
		PolicySource:        "hosted_permission_store",
		DraftID:             "draft-a",
		BasePolicyVersion:   "policy-v1",
		DraftPolicyVersion:  "policy-v2",
		MutationFingerprint: "sha256:policy-v2",
	})
	var mutationErr registry.RegistryMutationError
	if !errors.As(err, &mutationErr) || mutationErr.ErrorType != "PERSISTENT_STORE_WRITE_FAILED" {
		t.Fatalf("nil-db durable adapter should fail closed through registry helper, got %T %v", err, err)
	}
}

func TestServeHostedPermissionPolicyMutationBoundaryDogfood(t *testing.T) {
	fileRegistryPath := filepath.Join(t.TempDir(), "registry.json")
	if err := os.WriteFile(fileRegistryPath, []byte(`{"projects":[],"api_keys":[],"capabilities":[],"providers":[],"routing_policy":{"strategy":"first"},"snapshot":{"version":"test","ttl":"1h","source":"test"}}`), 0o600); err != nil {
		t.Fatalf("write registry fixture: %v", err)
	}

	fileMux := captureServeMux(t)
	if err := serve([]string{
		"--registry-store", "file",
		"--registry", fileRegistryPath,
		"--addr", "127.0.0.1:0",
		"--admin-identity-mode", httpapi.AdminIdentityModeHosted,
		"--admin-authenticator", httpapi.AdminAuthenticatorModeTrustedGateway,
		"--trusted-gateway-secret", "gateway-secret",
	}); err != errServeBoundaryStop {
		t.Fatalf("serve file boundary: %v", err)
	}
	fileResponse := performServeBoundaryRequest(fileMux, registry.HostedPermissionPolicyMutationBeginDraftOperation, "", map[string]any{
		"policy_source":        "hosted_permission_store",
		"base_policy_version":  "policy-v1",
		"draft_policy_version": "policy-v2",
	})
	if fileResponse.Code != http.StatusConflict {
		t.Fatalf("expected file serve mutation boundary 409, got %d: %s", fileResponse.Code, fileResponse.Body.String())
	}
	var fileError httpapi.ErrorResponse
	decodeServeBoundaryResponse(t, fileResponse, &fileError)
	if fileError.Error.ErrorType != "REGISTRY_MUTATION_UNAVAILABLE" || fileError.Error.ErrorScope != "platform" {
		t.Fatalf("unexpected file-mode mutation error: %#v", fileError)
	}

	restorePostgres := openPostgresDBForRuntime
	t.Cleanup(func() { openPostgresDBForRuntime = restorePostgres })
	openPostgresDBForRuntime = func(ctx context.Context, dsn string) (*sql.DB, error) {
		return sql.OpenDB(serveBoundaryConnector{}), nil
	}
	postgresMux := captureServeMux(t)
	if err := serve([]string{
		"--registry-store", "postgres",
		"--postgres-dsn", "postgres://dogfood",
		"--addr", "127.0.0.1:0",
		"--admin-identity-mode", httpapi.AdminIdentityModeHosted,
		"--admin-authenticator", httpapi.AdminAuthenticatorModeTrustedGateway,
		"--trusted-gateway-secret", "gateway-secret",
	}); err != errServeBoundaryStop {
		t.Fatalf("serve postgres boundary: %v", err)
	}
	postgresResponse := performServeBoundaryRequest(postgresMux, registry.HostedPermissionPolicyMutationPromoteOperation, "serve-boundary-promote-key", map[string]any{
		"draft_id":             "draft-a",
		"base_policy_version":  "policy-v1",
		"draft_policy_version": "policy-v2",
		"mutation_fingerprint": "sha256:policy-v2",
	})
	if postgresResponse.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected postgres serve mutation boundary 503, got %d: %s", postgresResponse.Code, postgresResponse.Body.String())
	}
	var postgresError httpapi.ErrorResponse
	decodeServeBoundaryResponse(t, postgresResponse, &postgresError)
	if postgresError.Error.ErrorType != "PERSISTENT_STORE_WRITE_FAILED" || postgresError.Error.ErrorScope != "platform" || !postgresError.Error.Retryable {
		t.Fatalf("unexpected postgres-mode mutation error: %#v", postgresError)
	}
}

var errServeBoundaryStop = errors.New("serve boundary stop")

func captureServeMux(t *testing.T) http.Handler {
	t.Helper()
	restore := listenAndServeControlPlane
	var captured http.Handler
	listenAndServeControlPlane = func(addr string, handler http.Handler) error {
		captured = handler
		return errServeBoundaryStop
	}
	t.Cleanup(func() { listenAndServeControlPlane = restore })
	return &serveBoundaryMux{t: t, handler: &captured}
}

type serveBoundaryMux struct {
	t       *testing.T
	handler *http.Handler
}

func (m *serveBoundaryMux) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	m.t.Helper()
	if *m.handler == nil {
		m.t.Fatalf("serve did not register handler")
	}
	(*m.handler).ServeHTTP(w, r)
}

func performServeBoundaryRequest(handler http.Handler, operation string, idempotencyKey string, fields map[string]any) *httptest.ResponseRecorder {
	body := map[string]any{"operation": operation}
	for key, value := range fields {
		body[key] = value
	}
	data, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/v1/private/hosted/permission-policy/mutation", bytes.NewReader(data))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-ID", "req-serve-boundary-"+strings.ReplaceAll(strings.TrimPrefix(operation, "policy_mutation."), "_", "-"))
	req.Header.Set("X-API2Agent-Gateway-Authorization", "Bearer gateway-secret")
	req.Header.Set("X-API2Agent-Gateway-Key-ID", "key-1")
	req.Header.Set("X-API2Agent-Principal-ID", "principal-1")
	req.Header.Set("X-API2Agent-Project-ID", "project-1")
	req.Header.Set("X-API2Agent-Organization-ID", "org-1")
	req.Header.Set("X-API2Agent-Token-ID", "token-1")
	req.Header.Set("X-API2Agent-Roles", "control_plane_admin")
	req.Header.Set("X-API2Agent-Permissions", serveBoundaryPermission(operation))
	if idempotencyKey != "" {
		req.Header.Set("Idempotency-Key", idempotencyKey)
	}
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, req)
	return response
}

func serveBoundaryPermission(operation string) string {
	switch operation {
	case registry.HostedPermissionPolicyMutationBeginDraftOperation, registry.HostedPermissionPolicyMutationApplyChangeOperation:
		return registry.PermissionHostedPermissionPolicyDraftWrite
	case registry.HostedPermissionPolicyMutationRequestReviewOperation:
		return registry.PermissionHostedPermissionPolicyRequestReview
	case registry.HostedPermissionPolicyMutationPromoteOperation:
		return registry.PermissionHostedPermissionPolicyPromote
	case registry.HostedPermissionPolicyMutationRollbackOperation:
		return registry.PermissionHostedPermissionPolicyRollback
	default:
		return registry.PermissionRegistryValidate
	}
}

func decodeServeBoundaryResponse(t *testing.T, response *httptest.ResponseRecorder, target any) {
	t.Helper()
	if err := json.Unmarshal(response.Body.Bytes(), target); err != nil {
		t.Fatalf("decode response: %v; body=%s", err, response.Body.String())
	}
}

type serveBoundaryConnector struct{}

func (serveBoundaryConnector) Connect(ctx context.Context) (driver.Conn, error) {
	return serveBoundaryConn{}, nil
}

func (serveBoundaryConnector) Driver() driver.Driver {
	return serveBoundaryDriver{}
}

type serveBoundaryDriver struct{}

func (serveBoundaryDriver) Open(name string) (driver.Conn, error) {
	return serveBoundaryConn{}, nil
}

type serveBoundaryConn struct{}

func (serveBoundaryConn) Prepare(query string) (driver.Stmt, error) {
	return nil, errors.New("prepare is not supported")
}

func (serveBoundaryConn) Close() error {
	return nil
}

func (serveBoundaryConn) Begin() (driver.Tx, error) {
	return nil, errors.New("serve boundary postgres unavailable")
}
