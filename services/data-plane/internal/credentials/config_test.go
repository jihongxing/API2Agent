package credentials

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadConfigFileReadsObjectOrList(t *testing.T) {
	dir := t.TempDir()
	objectPath := filepath.Join(dir, "credentials.json")
	if err := os.WriteFile(objectPath, []byte(`{"credentials":[{"credential_id":"cred_demo","provider_id":"demo","source":"config","secret_ref":"TEST_CONFIG_SECRET"}]}`), 0o644); err != nil {
		t.Fatalf("write object config: %v", err)
	}
	listPath := filepath.Join(dir, "credentials-list.json")
	if err := os.WriteFile(listPath, []byte(`[{"credential_id":"cred_list","provider_id":"demo","source":"config","secret_ref":"TEST_LIST_SECRET"}]`), 0o644); err != nil {
		t.Fatalf("write list config: %v", err)
	}

	objectCredentials, err := LoadConfigFile(objectPath)
	if err != nil {
		t.Fatalf("load object config: %v", err)
	}
	if len(objectCredentials) != 1 || objectCredentials[0].CredentialID != "cred_demo" {
		t.Fatalf("unexpected object credentials: %#v", objectCredentials)
	}

	listCredentials, err := LoadConfigFile(listPath)
	if err != nil {
		t.Fatalf("load list config: %v", err)
	}
	if len(listCredentials) != 1 || listCredentials[0].CredentialID != "cred_list" {
		t.Fatalf("unexpected list credentials: %#v", listCredentials)
	}
}

func TestResolverUsesConfigCredentialWhenRequestCredentialMissing(t *testing.T) {
	t.Setenv("TEST_CONFIG_SECRET", "config-secret")
	resolver := NewLocalResolver([]CredentialDefinition{
		{
			CredentialID:  "cred_demo",
			OwnerType:     "project",
			OwnerID:       "project_a",
			ProviderID:    "demo",
			AuthType:      "bearer",
			InjectionMode: "header",
			InjectionName: "Authorization",
			Source:        "config",
			SecretRef:     "TEST_CONFIG_SECRET",
		},
	})

	result := resolver.Resolve(CredentialResolutionRequest{
		ProjectID:    "project_a",
		CapabilityID: "demo.get",
		ProviderID:   "demo",
		ToolID:       "get",
	})

	if !result.Resolved {
		t.Fatalf("expected config credential to resolve: %#v", result)
	}
	if result.CredentialReference != "config:cred_demo" {
		t.Fatalf("expected config credential reference, got %q", result.CredentialReference)
	}
	if got := result.InjectionPatch.Headers["Authorization"]; got != "Bearer config-secret" {
		t.Fatalf("expected injected bearer secret, got %#v", result.InjectionPatch.Headers)
	}
}

func TestResolverDeniesOutOfScopeConfigCredential(t *testing.T) {
	t.Setenv("TEST_CONFIG_SECRET", "config-secret")
	resolver := NewLocalResolver([]CredentialDefinition{
		{
			CredentialID:  "cred_demo",
			OwnerType:     "project",
			OwnerID:       "project_a",
			ProviderID:    "demo",
			AuthType:      "api_key",
			InjectionMode: "query",
			Source:        "config",
			SecretRef:     "TEST_CONFIG_SECRET",
			Scope:         []string{"capability:demo.create"},
		},
	})

	result := resolver.Resolve(CredentialResolutionRequest{
		ProjectID:    "project_a",
		CapabilityID: "demo.get",
		ProviderID:   "demo",
		ToolID:       "get",
	})

	if result.Resolved {
		t.Fatalf("expected scope denial, got %#v", result)
	}
	if result.ErrorType != "credential_scope_denied" {
		t.Fatalf("expected credential_scope_denied, got %q", result.ErrorType)
	}
}
