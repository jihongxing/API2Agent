package registry

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestExportSnapshotFromRegistry(t *testing.T) {
	reg, err := LoadFile(filepath.Join("..", "..", "testdata", "registry", "network.public_ip.get.json"))
	if err != nil {
		t.Fatalf("load registry: %v", err)
	}

	snapshot, err := reg.ExportSnapshot()
	if err != nil {
		t.Fatalf("export snapshot: %v", err)
	}

	if snapshot.SnapshotVersion != "snapshot_control_plane_public_ip_v1" {
		t.Fatalf("unexpected snapshot version: %q", snapshot.SnapshotVersion)
	}
	if len(snapshot.Capabilities) != 1 || snapshot.Capabilities[0].ID != "network.public_ip.get" {
		t.Fatalf("unexpected capabilities: %#v", snapshot.Capabilities)
	}
	if len(snapshot.Providers) != 1 || snapshot.Providers[0].ProviderID != "ipify" {
		t.Fatalf("unexpected providers: %#v", snapshot.Providers)
	}
	if snapshot.RoutingPolicy.Strategy != "first" || snapshot.RoutingPolicy.RoutingMode != "deterministic" {
		t.Fatalf("unexpected routing policy: %#v", snapshot.RoutingPolicy)
	}
	if snapshot.Metadata["exporter"] != "api2agent-control-plane-minimum-v0" {
		t.Fatalf("unexpected metadata: %#v", snapshot.Metadata)
	}
	if !strings.HasPrefix(snapshot.Metadata["registry_fingerprint"], "sha256:") {
		t.Fatalf("expected registry fingerprint metadata, got %#v", snapshot.Metadata)
	}
	if snapshot.Metadata["snapshot_version_policy"] != "explicit" {
		t.Fatalf("expected explicit snapshot version policy, got %#v", snapshot.Metadata)
	}
}

func TestWriteSnapshotFile(t *testing.T) {
	reg, err := LoadFile(filepath.Join("..", "..", "testdata", "registry", "network.public_ip.get.json"))
	if err != nil {
		t.Fatalf("load registry: %v", err)
	}
	snapshot, err := reg.ExportSnapshot()
	if err != nil {
		t.Fatalf("export snapshot: %v", err)
	}

	outputPath := filepath.Join(t.TempDir(), "snapshot.json")
	if err := WriteSnapshotFile(outputPath, snapshot); err != nil {
		t.Fatalf("write snapshot: %v", err)
	}
	data, err := os.ReadFile(outputPath)
	if err != nil {
		t.Fatalf("read snapshot: %v", err)
	}
	var decoded RoutingSnapshot
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("decode snapshot: %v", err)
	}
	if decoded.SnapshotVersion != snapshot.SnapshotVersion {
		t.Fatalf("expected roundtrip snapshot version %q, got %q", snapshot.SnapshotVersion, decoded.SnapshotVersion)
	}
}

func TestValidateRejectsProviderCapabilityVersionMismatch(t *testing.T) {
	reg, err := LoadFile(filepath.Join("..", "..", "testdata", "registry", "network.public_ip.get.json"))
	if err != nil {
		t.Fatalf("load registry: %v", err)
	}
	reg.Providers[0].CapabilityVersion = "wrong"

	if _, err := reg.ExportSnapshot(); err == nil {
		t.Fatalf("expected validation error")
	}
}

func TestRegistryFingerprintIsStableAndChangesWithRegistryContent(t *testing.T) {
	reg := loadValidRegistry(t)
	first, err := reg.Fingerprint()
	if err != nil {
		t.Fatalf("fingerprint registry: %v", err)
	}
	second, err := reg.Fingerprint()
	if err != nil {
		t.Fatalf("fingerprint registry again: %v", err)
	}
	if first != second {
		t.Fatalf("expected stable fingerprint, got %q and %q", first, second)
	}
	reg.Providers[0].ProviderVersion = "2.0.0"
	changed, err := reg.Fingerprint()
	if err != nil {
		t.Fatalf("fingerprint changed registry: %v", err)
	}
	if changed == first {
		t.Fatalf("expected fingerprint to change after registry content changed")
	}
}

func TestValidateRejectsDuplicateCapability(t *testing.T) {
	reg := loadValidRegistry(t)
	reg.Capabilities = append(reg.Capabilities, reg.Capabilities[0])

	assertValidationError(t, reg, "capability \"network.public_ip.get\" is duplicated")
}

func TestValidateRejectsAPIKeyUnknownProject(t *testing.T) {
	reg := loadValidRegistry(t)
	reg.APIKeys[0].ProjectID = "missing"

	assertValidationError(t, reg, "api_key \"key_local_dev\" references unknown project \"missing\"")
}

func TestValidateRejectsActiveProviderWithoutBaseURL(t *testing.T) {
	reg := loadValidRegistry(t)
	reg.Providers[0].Metadata = map[string]string{}

	assertValidationError(t, reg, "active provider \"ipify_public_ip_v1\" metadata.base_url is required")
}

func TestValidateRejectsUnknownCredentialScope(t *testing.T) {
	reg := loadValidRegistry(t)
	reg.CredentialMetadata[0].Scope = []string{"capability:missing.capability.get"}

	assertValidationError(t, reg, "credential_metadata \"cred_local_ipify\" scope references unknown capability \"missing.capability.get\"")
}

func TestValidateRejectsInvalidRoutingStrategy(t *testing.T) {
	reg := loadValidRegistry(t)
	reg.RoutingPolicy.Strategy = "magic"

	assertValidationError(t, reg, "routing_policy.strategy \"magic\" is invalid")
}

func TestValidateRejectsNoActiveProviders(t *testing.T) {
	reg := loadValidRegistry(t)
	reg.Providers[0].Status = "disabled"

	assertValidationError(t, reg, "at least one active provider is required")
}

func loadValidRegistry(t *testing.T) Registry {
	t.Helper()
	reg, err := LoadFile(filepath.Join("..", "..", "testdata", "registry", "network.public_ip.get.json"))
	if err != nil {
		t.Fatalf("load registry: %v", err)
	}
	return *reg
}

func assertValidationError(t *testing.T, reg Registry, message string) {
	t.Helper()
	_, err := reg.ExportSnapshot()
	if err == nil {
		t.Fatalf("expected validation error")
	}
	if !strings.Contains(err.Error(), message) {
		t.Fatalf("expected error containing %q, got %q", message, err.Error())
	}
}
