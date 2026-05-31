package registry

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

func TestPersistentRegistrySQLSchemaContainsRequiredTablesAndConstraints(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "schema", "postgres", "001_persistent_registry_store.sql"))
	if err != nil {
		t.Fatalf("read sql schema: %v", err)
	}
	schema := string(data)

	required := []string{
		"CREATE TABLE projects",
		"CREATE TABLE api_keys",
		"CREATE TABLE capabilities",
		"CREATE TABLE providers",
		"CREATE TABLE credential_metadata",
		"CREATE TABLE routing_policies",
		"CREATE TABLE snapshot_configs",
		"CREATE TABLE registry_revisions",
		"CREATE TABLE snapshot_artifact_publications",
		"CREATE TABLE admin_audit_events",
		"CREATE TABLE admin_mutation_idempotency_records",
		"metadata ? 'base_url'",
		"default_mode TEXT NOT NULL DEFAULT '' CHECK (default_mode = '' OR default_mode IN",
		"routing_policies_one_active_global",
		"snapshot_configs_one_active",
		"snapshot_artifact_publications_one_active_version",
		"admin_mutation_idempotency_records_unique_key",
		"registry_revision_id BIGINT REFERENCES registry_revisions(id)",
		"admin_audit_event_id BIGINT REFERENCES admin_audit_events(id)",
		"key_hash TEXT NOT NULL DEFAULT ''",
		"failover_policy JSONB",
		"metadata JSONB NOT NULL DEFAULT '{}'::jsonb",
	}
	for _, item := range required {
		if !strings.Contains(schema, item) {
			t.Fatalf("schema missing %q", item)
		}
	}
}

func TestMapRegistryToPersistentRowsMapsFileRegistryFixture(t *testing.T) {
	reg := loadValidRegistry(t)

	rows, err := MapRegistryToPersistentRows(reg)
	if err != nil {
		t.Fatalf("map registry rows: %v", err)
	}

	if len(rows.Projects) != 1 {
		t.Fatalf("unexpected projects: %#v", rows.Projects)
	}
	if rows.Projects[0].ID != "local" || rows.Projects[0].DefaultMode != "proxy" {
		t.Fatalf("unexpected project row: %#v", rows.Projects[0])
	}
	if len(rows.APIKeys) != 1 {
		t.Fatalf("unexpected api keys: %#v", rows.APIKeys)
	}
	if rows.APIKeys[0].KeyHash != "" {
		t.Fatalf("file registry import must not invent key hash: %#v", rows.APIKeys[0])
	}
	if len(rows.Capabilities) != 1 || rows.Capabilities[0].Version != "0.1-migrated" {
		t.Fatalf("unexpected capability rows: %#v", rows.Capabilities)
	}
	if len(rows.Providers) != 1 {
		t.Fatalf("unexpected provider rows: %#v", rows.Providers)
	}
	if rows.Providers[0].Metadata["base_url"] != "https://api.ipify.org" {
		t.Fatalf("expected provider base_url metadata, got %#v", rows.Providers[0].Metadata)
	}
	if len(rows.CredentialMetadata) != 1 {
		t.Fatalf("unexpected credential metadata rows: %#v", rows.CredentialMetadata)
	}
	if rows.CredentialMetadata[0].AuthType != "none" || rows.CredentialMetadata[0].InjectionMode != "none" {
		t.Fatalf("unexpected credential metadata row: %#v", rows.CredentialMetadata[0])
	}
	if len(rows.RoutingPolicies) != 1 || rows.RoutingPolicies[0].ID != "global" {
		t.Fatalf("unexpected routing policy rows: %#v", rows.RoutingPolicies)
	}
	if len(rows.SnapshotConfigs) != 1 || rows.SnapshotConfigs[0].Version != "snapshot_control_plane_public_ip_v1" {
		t.Fatalf("unexpected snapshot config rows: %#v", rows.SnapshotConfigs)
	}
	if rows.SnapshotConfigs[0].FetchedAt != "2026-05-30T00:00:00Z" {
		t.Fatalf("unexpected fetched_at format: %#v", rows.SnapshotConfigs[0])
	}
	if len(rows.RegistryRevisions) != 1 {
		t.Fatalf("unexpected registry revision rows: %#v", rows.RegistryRevisions)
	}
	if !strings.HasPrefix(rows.RegistryRevisions[0].RegistryFingerprint, "sha256:") {
		t.Fatalf("expected registry fingerprint, got %#v", rows.RegistryRevisions[0])
	}
	if len(rows.ArtifactPublications) != 0 {
		t.Fatalf("mapping should not invent artifact publication rows: %#v", rows.ArtifactPublications)
	}
	if len(rows.AdminAuditEvents) != 0 {
		t.Fatalf("mapping should not invent admin audit rows: %#v", rows.AdminAuditEvents)
	}
}

func TestBuildRegistryFromPersistentRowsRoundTripsFileRegistryFixture(t *testing.T) {
	reg := loadValidRegistry(t)
	rows, err := MapRegistryToPersistentRows(reg)
	if err != nil {
		t.Fatalf("map registry rows: %v", err)
	}

	rebuilt, err := BuildRegistryFromPersistentRows(rows)
	if err != nil {
		t.Fatalf("build registry from persistent rows: %v", err)
	}
	originalSnapshot, err := CanonicalRegistry(reg).ExportSnapshot()
	if err != nil {
		t.Fatalf("export original snapshot: %v", err)
	}
	rebuiltSnapshot, err := rebuilt.ExportSnapshot()
	if err != nil {
		t.Fatalf("export rebuilt snapshot: %v", err)
	}

	if !reflect.DeepEqual(rebuiltSnapshot.Capabilities, originalSnapshot.Capabilities) {
		t.Fatalf("capability snapshot mismatch: %#v vs %#v", rebuiltSnapshot.Capabilities, originalSnapshot.Capabilities)
	}
	if !reflect.DeepEqual(rebuiltSnapshot.Providers, originalSnapshot.Providers) {
		t.Fatalf("provider snapshot mismatch: %#v vs %#v", rebuiltSnapshot.Providers, originalSnapshot.Providers)
	}
	if !reflect.DeepEqual(rebuiltSnapshot.RoutingPolicy, originalSnapshot.RoutingPolicy) {
		t.Fatalf("routing policy mismatch: %#v vs %#v", rebuiltSnapshot.RoutingPolicy, originalSnapshot.RoutingPolicy)
	}
	if rebuiltSnapshot.Metadata["registry_fingerprint"] != originalSnapshot.Metadata["registry_fingerprint"] {
		t.Fatalf("fingerprint mismatch: %#v vs %#v", rebuiltSnapshot.Metadata, originalSnapshot.Metadata)
	}
}

func TestCanonicalRegistrySortsCollectionsWithoutMutatingInput(t *testing.T) {
	seed := "seed"
	reg := Registry{
		Projects: []Project{
			{ID: "z"},
			{ID: "a"},
		},
		APIKeys: []APIKey{
			{ID: "key_z", ProjectID: "z"},
			{ID: "key_a", ProjectID: "a"},
		},
		Capabilities: []Capability{
			{ID: "weather.current.get", Version: "2.0.0", Name: "Weather v2"},
			{ID: "network.public_ip.get", Version: "1.0.0", Name: "IP"},
			{ID: "weather.current.get", Version: "1.0.0", Name: "Weather v1"},
		},
		Providers: []Provider{
			{
				ID:                "provider_z",
				CapabilityID:      "weather.current.get",
				CapabilityVersion: "2.0.0",
				ProviderID:        "provider-z",
				ProviderVersion:   "1.0.0",
				MappingVersion:    "1.0.0",
				ToolID:            "weather",
				Regions:           []string{"us-east", "ap-east"},
				GeoAffinity:       "global",
				Metadata:          map[string]string{"base_url": "https://z.example.test"},
			},
			{
				ID:                "provider_a",
				CapabilityID:      "network.public_ip.get",
				CapabilityVersion: "1.0.0",
				ProviderID:        "provider-a",
				ProviderVersion:   "1.0.0",
				MappingVersion:    "1.0.0",
				ToolID:            "ip",
				Regions:           []string{"global"},
				GeoAffinity:       "global",
				Metadata:          map[string]string{"base_url": "https://a.example.test"},
			},
		},
		CredentialMetadata: []CredentialMetadata{
			{
				CredentialID: "cred_z",
				OwnerType:    "project",
				OwnerID:      "z",
				ProviderID:   "provider-z",
				Scope:        []string{"tool:weather", "capability:weather.current.get"},
			},
			{
				CredentialID: "cred_a",
				OwnerType:    "project",
				OwnerID:      "a",
				ProviderID:   "provider-a",
				Scope:        []string{"provider:provider-a"},
			},
		},
		RoutingPolicy: RoutingPolicy{
			Strategy:    "first",
			RoutingMode: "deterministic",
			RoutingSeed: &seed,
		},
		Snapshot: SnapshotExportOptions{
			Version:   "snapshot_test",
			FetchedAt: time.Date(2026, 5, 30, 0, 0, 0, 0, time.UTC),
			TTL:       "24h",
			Source:    "pull",
		},
	}

	originalProviderRegions := append([]string(nil), reg.Providers[0].Regions...)
	originalCredentialScope := append([]string(nil), reg.CredentialMetadata[0].Scope...)

	canonical := CanonicalRegistry(reg)

	if got := collectProjectIDs(canonical.Projects); !reflect.DeepEqual(got, []string{"a", "z"}) {
		t.Fatalf("unexpected project order: %#v", got)
	}
	if got := collectAPIKeyIDs(canonical.APIKeys); !reflect.DeepEqual(got, []string{"key_a", "key_z"}) {
		t.Fatalf("unexpected api key order: %#v", got)
	}
	if got := collectCapabilityKeys(canonical.Capabilities); !reflect.DeepEqual(got, []string{"network.public_ip.get@1.0.0", "weather.current.get@1.0.0", "weather.current.get@2.0.0"}) {
		t.Fatalf("unexpected capability order: %#v", got)
	}
	if got := collectProviderIDs(canonical.Providers); !reflect.DeepEqual(got, []string{"provider_a", "provider_z"}) {
		t.Fatalf("unexpected provider order: %#v", got)
	}
	if !reflect.DeepEqual(canonical.Providers[1].Regions, []string{"ap-east", "us-east"}) {
		t.Fatalf("expected provider regions sorted in canonical copy, got %#v", canonical.Providers[1].Regions)
	}
	if got := collectCredentialIDs(canonical.CredentialMetadata); !reflect.DeepEqual(got, []string{"cred_a", "cred_z"}) {
		t.Fatalf("unexpected credential order: %#v", got)
	}
	if !reflect.DeepEqual(canonical.CredentialMetadata[1].Scope, []string{"capability:weather.current.get", "tool:weather"}) {
		t.Fatalf("expected credential scope sorted in canonical copy, got %#v", canonical.CredentialMetadata[1].Scope)
	}
	if !reflect.DeepEqual(reg.Providers[0].Regions, originalProviderRegions) {
		t.Fatalf("canonicalization mutated provider regions: %#v", reg.Providers[0].Regions)
	}
	if !reflect.DeepEqual(reg.CredentialMetadata[0].Scope, originalCredentialScope) {
		t.Fatalf("canonicalization mutated credential scope: %#v", reg.CredentialMetadata[0].Scope)
	}
}

func collectProjectIDs(projects []Project) []string {
	ids := make([]string, 0, len(projects))
	for _, project := range projects {
		ids = append(ids, project.ID)
	}
	return ids
}

func collectAPIKeyIDs(keys []APIKey) []string {
	ids := make([]string, 0, len(keys))
	for _, key := range keys {
		ids = append(ids, key.ID)
	}
	return ids
}

func collectCapabilityKeys(capabilities []Capability) []string {
	keys := make([]string, 0, len(capabilities))
	for _, capability := range capabilities {
		keys = append(keys, capability.ID+"@"+capability.Version)
	}
	return keys
}

func collectProviderIDs(providers []Provider) []string {
	ids := make([]string, 0, len(providers))
	for _, provider := range providers {
		ids = append(ids, provider.ID)
	}
	return ids
}

func collectCredentialIDs(credentials []CredentialMetadata) []string {
	ids := make([]string, 0, len(credentials))
	for _, credential := range credentials {
		ids = append(ids, credential.CredentialID)
	}
	return ids
}
