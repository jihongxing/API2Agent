package registry

import (
	"strings"
	"testing"
	"time"
)

const (
	tenantProjectA = "project-alpha"
	tenantProjectB = "project-beta"
)

func TestValidateProjectPartitionMutationAllowsSameProjectMetadataChanges(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.Projects[0].Name = "Alpha Updated"
	proposed.APIKeys[0].Status = "disabled"
	proposed.CredentialMetadata[0].RotationHint = "rotate-soon"

	decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
	if err != nil {
		t.Fatalf("validate project partition mutation: %v decision=%#v", err, decision)
	}
	if !decision.Allowed {
		t.Fatalf("expected decision allowed: %#v", decision)
	}
	if decision.Counts.ProjectsChanged != 1 || decision.Counts.APIKeysChanged != 1 || decision.Counts.CredentialMetadataChanged != 1 {
		t.Fatalf("unexpected changed counts: %#v", decision.Counts)
	}
	if decision.PartitionProjectID != tenantProjectA || decision.Operation != ProjectPartitionReplaceOperation || decision.DiffFingerprint == "" {
		t.Fatalf("unexpected decision metadata: %#v", decision)
	}
	if decision.SnapshotBoundaryChanged {
		t.Fatalf("same-project metadata changes should not touch snapshot boundary: %#v", decision)
	}
}

func TestValidateProjectPartitionMutationAllowsOwnedProviderChange(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.Providers[1].EstimatedCost = 0.25
	proposed.Providers[1].Metadata["base_url"] = "https://alpha-provider-v2.example.test"

	decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
	if err != nil {
		t.Fatalf("validate owned provider mutation: %v decision=%#v", err, decision)
	}
	if decision.Counts.ProvidersChanged != 1 {
		t.Fatalf("expected one provider change, got %#v", decision.Counts)
	}
}

func TestValidateProjectPartitionMutationRejectsCrossProjectChanges(t *testing.T) {
	cases := []struct {
		name       string
		mutate     func(Registry) Registry
		objectType string
		reason     string
	}{
		{
			name: "other project row",
			mutate: func(reg Registry) Registry {
				reg.Projects[1].Name = "Beta Changed"
				return reg
			},
			objectType: "project",
			reason:     "cross_project_change",
		},
		{
			name: "other project api key deletion",
			mutate: func(reg Registry) Registry {
				reg.APIKeys = reg.APIKeys[:1]
				return reg
			},
			objectType: "api_key",
			reason:     "cross_project_change",
		},
		{
			name: "other project credential change",
			mutate: func(reg Registry) Registry {
				reg.CredentialMetadata[1].RotationHint = "changed"
				return reg
			},
			objectType: "credential_metadata",
			reason:     "cross_project_or_platform_change",
		},
		{
			name: "platform credential change",
			mutate: func(reg Registry) Registry {
				reg.CredentialMetadata[2].RotationHint = "changed"
				return reg
			},
			objectType: "credential_metadata",
			reason:     "cross_project_or_platform_change",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			current := tenantPartitionRegistryFixture()
			proposed := tc.mutate(tenantPartitionRegistryFixture())

			decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
			assertPartitionViolation(t, err, decision, tc.objectType, tc.reason)
		})
	}
}

func TestValidateProjectPartitionMutationRejectsGlobalObjectChanges(t *testing.T) {
	cases := []struct {
		name       string
		mutate     func(Registry) Registry
		objectType string
		reason     string
	}{
		{
			name: "capability change",
			mutate: func(reg Registry) Registry {
				reg.Capabilities[0].Name = "Changed Capability"
				return reg
			},
			objectType: "capability",
			reason:     "global_capability_change",
		},
		{
			name: "global routing policy",
			mutate: func(reg Registry) Registry {
				reg.RoutingPolicy.Strategy = "lowest_cost"
				return reg
			},
			objectType: "routing_policy",
			reason:     "global_routing_policy_change",
		},
		{
			name: "snapshot config",
			mutate: func(reg Registry) Registry {
				reg.Snapshot.TTL = "48h"
				return reg
			},
			objectType: "snapshot_config",
			reason:     "global_snapshot_config_change",
		},
		{
			name: "platform owned provider",
			mutate: func(reg Registry) Registry {
				reg.Providers[0].EstimatedCost = 1.23
				return reg
			},
			objectType: "provider",
			reason:     "platform_provider_change",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			current := tenantPartitionRegistryFixture()
			proposed := tc.mutate(tenantPartitionRegistryFixture())

			decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
			assertPartitionViolation(t, err, decision, tc.objectType, tc.reason)
		})
	}
}

func TestValidateProjectPartitionMutationRejectsProviderOwnershipTransfer(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.Providers[1].Metadata[providerOwnerProjectMetadataKey] = tenantProjectB

	decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
	assertPartitionViolation(t, err, decision, "provider", "ownership_transfer")
}

func TestValidateProjectPartitionMutationRejectsInvalidOwnedProviderCapabilityChange(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.Providers[1].CapabilityVersion = "0.2-project"

	decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
	if err == nil {
		t.Fatalf("expected invalid proposed registry error")
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "REGISTRY_MUTATION_INVALID" {
		t.Fatalf("unexpected mutation error: %#v", mutationErr)
	}
	if !hasViolation(decision, "registry", "proposed_registry_invalid") {
		t.Fatalf("expected proposed registry invalid violation: %#v", decision.Violations)
	}
}

func TestValidateProjectPartitionMutationRejectsNewProviderWithoutOwnership(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.Providers = append(proposed.Providers, Provider{
		ID:                "new_unowned_provider",
		CapabilityID:      "network.public_ip.get",
		CapabilityVersion: "0.1-migrated",
		ProviderID:        "new-unowned",
		ProviderVersion:   "v1",
		MappingVersion:    "m1",
		ToolID:            "get_ip_new",
		Regions:           []string{"global"},
		GeoAffinity:       "global",
		Metadata:          map[string]string{"base_url": "https://new.example.test"},
		Status:            "active",
	})

	decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
	assertPartitionViolation(t, err, decision, "provider", "platform_provider_change")
}

func TestValidateProjectPartitionMutationRejectsMissingProjectScope(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.APIKeys[0].Status = "disabled"

	decision, err := ValidateProjectPartitionMutation(current, proposed, " ")
	if err == nil {
		t.Fatalf("expected missing project scope error")
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "AUTHZ_DENIED" || mutationErr.Retryable {
		t.Fatalf("unexpected authz error: %#v", mutationErr)
	}
	if !hasViolation(decision, "principal", "project_scope_required") {
		t.Fatalf("expected project scope violation: %#v", decision)
	}
}

func TestValidateProjectPartitionMutationRejectsInvalidProposedRegistry(t *testing.T) {
	current := tenantPartitionRegistryFixture()
	proposed := tenantPartitionRegistryFixture()
	proposed.Providers[0].Metadata = map[string]string{}

	decision, err := ValidateProjectPartitionMutation(current, proposed, tenantProjectA)
	if err == nil {
		t.Fatalf("expected invalid registry error")
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "REGISTRY_MUTATION_INVALID" {
		t.Fatalf("unexpected invalid registry error: %#v", mutationErr)
	}
	if !hasViolation(decision, "registry", "proposed_registry_invalid") {
		t.Fatalf("expected proposed registry invalid violation: %#v", decision)
	}
}

func TestProjectPartitionIdempotencyScopeIsProjectScoped(t *testing.T) {
	key := "same-raw-idempotency-key"
	left := projectPartitionIdempotencyFingerprint(t, tenantProjectA, key, "sha256:registry-a", "sha256:diff-a")
	right := projectPartitionIdempotencyFingerprint(t, tenantProjectB, key, "sha256:registry-a", "sha256:diff-a")
	changed := projectPartitionIdempotencyFingerprint(t, tenantProjectA, key, "sha256:registry-b", "sha256:diff-b")

	if left == right {
		t.Fatalf("expected same raw key to be isolated by project scope")
	}
	if left == changed {
		t.Fatalf("expected different partition request to change fingerprint")
	}
	if strings.Contains(left, key) {
		t.Fatalf("fingerprint should not contain raw idempotency key: %q", left)
	}
}

func assertPartitionViolation(t *testing.T, err error, decision ProjectPartitionMutationDecision, objectType string, reason string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected partition violation, decision=%#v", decision)
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "REGISTRY_PARTITION_VIOLATION" || mutationErr.Retryable {
		t.Fatalf("unexpected partition error: %#v", mutationErr)
	}
	if decision.Allowed {
		t.Fatalf("expected decision denied: %#v", decision)
	}
	if !hasViolation(decision, objectType, reason) {
		t.Fatalf("expected violation %s/%s, got %#v", objectType, reason, decision.Violations)
	}
	if decision.RejectedCounts[objectType] == 0 {
		t.Fatalf("expected rejected count for %q: %#v", objectType, decision.RejectedCounts)
	}
}

func hasViolation(decision ProjectPartitionMutationDecision, objectType string, reason string) bool {
	for _, violation := range decision.Violations {
		if violation.ObjectType == objectType && violation.Reason == reason {
			return true
		}
	}
	return false
}

func projectPartitionIdempotencyFingerprint(t *testing.T, projectID string, rawKey string, registryFingerprint string, diffFingerprint string) string {
	t.Helper()
	fingerprint, err := hashCanonicalJSON(map[string]string{
		"operation":                     ProjectPartitionReplaceOperation,
		"method":                        "POST",
		"path":                          "/v1/admin/registry/project-partition/replace",
		"project_id":                    projectID,
		"idempotency_key_hash":          hashString(rawKey),
		"proposed_registry_fingerprint": registryFingerprint,
		"partition_diff_fingerprint":    diffFingerprint,
	})
	if err != nil {
		t.Fatalf("hash project partition idempotency fingerprint: %v", err)
	}
	return fingerprint
}

func tenantPartitionRegistryFixture() Registry {
	reg := loadValidRegistryNoT()
	reg.Projects = []Project{
		{ID: tenantProjectA, Name: "Alpha", Status: "active", DefaultMode: "proxy"},
		{ID: tenantProjectB, Name: "Beta", Status: "active", DefaultMode: "proxy"},
	}
	reg.APIKeys = []APIKey{
		{ID: "key-alpha", ProjectID: tenantProjectA, KeyPrefix: "alpha", Status: "active"},
		{ID: "key-beta", ProjectID: tenantProjectB, KeyPrefix: "beta", Status: "active"},
	}
	reg.Providers = []Provider{
		{
			ID:                "platform_ipify_public_ip_v1",
			CapabilityID:      "network.public_ip.get",
			CapabilityVersion: "0.1-migrated",
			ProviderID:        "ipify",
			ProviderVersion:   "v1",
			MappingVersion:    "m1",
			ToolID:            "get_ip",
			Regions:           []string{"global"},
			GeoAffinity:       "global",
			EstimatedCost:     0,
			Metadata:          map[string]string{"base_url": "https://api.ipify.org"},
			Status:            "active",
		},
		{
			ID:                "alpha_httpbin_public_ip_v1",
			CapabilityID:      "network.public_ip.get",
			CapabilityVersion: "0.1-migrated",
			ProviderID:        "httpbin-alpha",
			ProviderVersion:   "v1",
			MappingVersion:    "m1",
			ToolID:            "get_ip_alpha",
			Regions:           []string{"global"},
			GeoAffinity:       "global",
			EstimatedCost:     0.1,
			Metadata: map[string]string{
				"base_url":                      "https://alpha-provider.example.test",
				providerOwnerProjectMetadataKey: tenantProjectA,
			},
			Status: "active",
		},
		{
			ID:                "beta_httpbin_public_ip_v1",
			CapabilityID:      "network.public_ip.get",
			CapabilityVersion: "0.1-migrated",
			ProviderID:        "httpbin-beta",
			ProviderVersion:   "v1",
			MappingVersion:    "m1",
			ToolID:            "get_ip_beta",
			Regions:           []string{"global"},
			GeoAffinity:       "global",
			EstimatedCost:     0.2,
			Metadata: map[string]string{
				"base_url":                      "https://beta-provider.example.test",
				providerOwnerProjectMetadataKey: tenantProjectB,
			},
			Status: "active",
		},
	}
	reg.CredentialMetadata = []CredentialMetadata{
		{
			CredentialID:      "cred-alpha",
			CredentialVersion: "v1",
			OwnerType:         "project",
			OwnerID:           tenantProjectA,
			ProviderID:        "httpbin-alpha",
			AuthType:          "none",
			InjectionMode:     "none",
			Source:            "none",
			Scope:             []string{"provider:httpbin-alpha"},
			Status:            "active",
		},
		{
			CredentialID:      "cred-beta",
			CredentialVersion: "v1",
			OwnerType:         "project",
			OwnerID:           tenantProjectB,
			ProviderID:        "httpbin-beta",
			AuthType:          "none",
			InjectionMode:     "none",
			Source:            "none",
			Scope:             []string{"provider:httpbin-beta"},
			Status:            "active",
		},
		{
			CredentialID:      "cred-platform",
			CredentialVersion: "v1",
			OwnerType:         "platform",
			OwnerID:           "platform",
			ProviderID:        "ipify",
			AuthType:          "none",
			InjectionMode:     "none",
			Source:            "none",
			Scope:             []string{"provider:ipify"},
			Status:            "active",
		},
	}
	return reg
}

func loadValidRegistryNoT() Registry {
	reg := Registry{
		Capabilities: []Capability{
			{ID: "network.public_ip.get", Version: "0.1-migrated", Name: "Public IP"},
		},
		RoutingPolicy: RoutingPolicy{
			Strategy:    "first",
			RoutingMode: "deterministic",
		},
		Snapshot: SnapshotExportOptions{
			Version:   "snapshot_tenant_partition_v1",
			FetchedAt: mustParseTenantPartitionTime("2026-05-30T00:00:00Z"),
			TTL:       "24h",
			Source:    "pull",
		},
	}
	return reg
}

func mustParseTenantPartitionTime(value string) time.Time {
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		panic(err)
	}
	return parsed
}
