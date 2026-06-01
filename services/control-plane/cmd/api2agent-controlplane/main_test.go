package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
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
