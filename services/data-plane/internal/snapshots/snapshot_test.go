package snapshots

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"api2agent/services/data-plane/internal/protocol"
)

func TestSnapshotExpiration(t *testing.T) {
	snapshot := Snapshot{
		SnapshotFetchedAt: time.Date(2026, 5, 30, 0, 0, 0, 0, time.UTC),
		SnapshotTTL:       "2h",
	}

	expiresAt, err := snapshot.ExpiresAt()
	if err != nil {
		t.Fatalf("expires at: %v", err)
	}
	if expiresAt == nil {
		t.Fatalf("expected expiration timestamp")
	}
	if want := time.Date(2026, 5, 30, 2, 0, 0, 0, time.UTC); !expiresAt.Equal(want) {
		t.Fatalf("expected expires_at %s, got %s", want, *expiresAt)
	}
	expired, err := snapshot.IsExpired(time.Date(2026, 5, 30, 1, 59, 0, 0, time.UTC))
	if err != nil {
		t.Fatalf("is expired before ttl: %v", err)
	}
	if expired {
		t.Fatalf("expected snapshot to be active before ttl")
	}
	expired, err = snapshot.IsExpired(time.Date(2026, 5, 30, 2, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatalf("is expired at ttl: %v", err)
	}
	if !expired {
		t.Fatalf("expected snapshot to be expired at ttl")
	}
}

func TestSnapshotExpirationIgnoresMissingTTL(t *testing.T) {
	snapshot := Snapshot{SnapshotFetchedAt: time.Date(2026, 5, 30, 0, 0, 0, 0, time.UTC)}

	expiresAt, err := snapshot.ExpiresAt()
	if err != nil {
		t.Fatalf("expires at: %v", err)
	}
	if expiresAt != nil {
		t.Fatalf("expected nil expiration without ttl")
	}
	expired, err := snapshot.IsExpired(time.Date(2027, 5, 30, 0, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatalf("is expired: %v", err)
	}
	if expired {
		t.Fatalf("expected snapshot without ttl to remain active")
	}
}

func TestLoadControlPlaneExportedSnapshotMetadata(t *testing.T) {
	snapshot, err := LoadFile(filepath.Join("..", "..", "testdata", "snapshots", "control-plane-public-ip.json"))
	if err != nil {
		t.Fatalf("load control plane snapshot: %v", err)
	}
	if snapshot.Metadata["exporter"] != "api2agent-control-plane-minimum-v0" {
		t.Fatalf("expected exporter metadata, got %#v", snapshot.Metadata)
	}
	if len(snapshot.Providers) != 1 || snapshot.Providers[0].ProviderID != "ipify" {
		t.Fatalf("unexpected providers: %#v", snapshot.Providers)
	}
}

func TestLoadRejectsIncompatibleSchemaVersion(t *testing.T) {
	source := filepath.Join("..", "..", "testdata", "snapshots", "control-plane-public-ip.json")
	data, err := os.ReadFile(source)
	if err != nil {
		t.Fatalf("read source snapshot: %v", err)
	}
	var payload map[string]any
	if err := json.Unmarshal(data, &payload); err != nil {
		t.Fatalf("decode source snapshot: %v", err)
	}
	metadata, _ := payload["metadata"].(map[string]any)
	if metadata == nil {
		metadata = map[string]any{}
		payload["metadata"] = metadata
	}
	metadata["schema_version"] = "api2agent.protocol.v9"
	path := filepath.Join(t.TempDir(), "snapshot.json")
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		t.Fatalf("encode incompatible snapshot: %v", err)
	}
	if err := os.WriteFile(path, encoded, 0o644); err != nil {
		t.Fatalf("write incompatible snapshot: %v", err)
	}

	if _, err := LoadFile(path); err == nil {
		t.Fatalf("expected incompatible schema version to fail")
	}
}

func TestValidateCompatibilityAcceptsCurrentSchemaVersion(t *testing.T) {
	snapshot := &Snapshot{Metadata: map[string]string{"schema_version": protocol.SchemaVersion}}
	if err := ValidateCompatibility(snapshot); err != nil {
		t.Fatalf("expected current schema version to pass: %v", err)
	}
}

func TestValidateCompatibilityAcceptsLegacyLocalSnapshotWithoutMetadata(t *testing.T) {
	for _, snapshot := range []*Snapshot{
		{},
		{Metadata: map[string]string{}},
	} {
		if err := ValidateCompatibility(snapshot); err != nil {
			t.Fatalf("expected legacy local snapshot to pass: %v", err)
		}
	}
}

func TestValidateCompatibilityRequiresStrictControlPlaneMetadata(t *testing.T) {
	base := map[string]string{
		"exporter":                "api2agent-control-plane-minimum-v0",
		"registry_fingerprint":    "sha256:test",
		"schema_version":          protocol.SchemaVersion,
		"snapshot_version_policy": "explicit",
	}

	for _, missingKey := range []string{"schema_version", "registry_fingerprint", "snapshot_version_policy"} {
		metadata := map[string]string{}
		for key, value := range base {
			metadata[key] = value
		}
		delete(metadata, missingKey)

		err := ValidateCompatibility(&Snapshot{Metadata: metadata})
		if err == nil {
			t.Fatalf("expected missing %s to fail", missingKey)
		}
		if want := "control plane snapshot metadata." + missingKey + " is required"; err.Error() != want {
			t.Fatalf("expected error %q, got %q", want, err.Error())
		}
	}
}

func TestLoadSnapshotFromDistributionDirectory(t *testing.T) {
	source := filepath.Join("..", "..", "testdata", "snapshots", "control-plane-public-ip.json")
	distributionDir := t.TempDir()
	artifactDir := filepath.Join(distributionDir, "artifacts", "snapshot_control_plane_public_ip_v1")
	if err := os.MkdirAll(artifactDir, 0o755); err != nil {
		t.Fatalf("create artifact dir: %v", err)
	}
	data, err := os.ReadFile(source)
	if err != nil {
		t.Fatalf("read source snapshot: %v", err)
	}
	if err := os.WriteFile(filepath.Join(artifactDir, "snapshot.json"), data, 0o644); err != nil {
		t.Fatalf("write distributed snapshot: %v", err)
	}
	manifest := []byte(`{
  "artifact_version": "api2agent.snapshot_artifact.v0",
  "snapshot_file": "snapshot.json",
  "snapshot_version": "snapshot_control_plane_public_ip_v1",
  "snapshot_source": "pull",
  "registry_fingerprint": "sha256:test-control-plane-public-ip",
  "snapshot_version_policy": "explicit"
}`)
	if err := os.WriteFile(filepath.Join(artifactDir, "manifest.json"), manifest, 0o644); err != nil {
		t.Fatalf("write distributed manifest: %v", err)
	}
	pointer := []byte(`{
  "distribution_version": "api2agent.snapshot_distribution.v0",
  "snapshot_version": "snapshot_control_plane_public_ip_v1",
  "snapshot_file": "artifacts/snapshot_control_plane_public_ip_v1/snapshot.json",
  "manifest_file": "artifacts/snapshot_control_plane_public_ip_v1/manifest.json",
  "registry_fingerprint": "sha256:test-control-plane-public-ip",
  "snapshot_version_policy": "explicit"
}`)
	if err := os.WriteFile(filepath.Join(distributionDir, "current.json"), pointer, 0o644); err != nil {
		t.Fatalf("write current pointer: %v", err)
	}

	snapshot, err := LoadFile(distributionDir)
	if err != nil {
		t.Fatalf("load snapshot from distribution: %v", err)
	}
	if snapshot.SnapshotVersion != "snapshot_control_plane_public_ip_v1" {
		t.Fatalf("unexpected snapshot version: %q", snapshot.SnapshotVersion)
	}
}

func TestLoadSnapshotFromDistributionDirectoryRejectsManifestSnapshotMismatch(t *testing.T) {
	source := filepath.Join("..", "..", "testdata", "snapshots", "control-plane-public-ip.json")
	distributionDir := t.TempDir()
	artifactDir := filepath.Join(distributionDir, "artifacts", "snapshot_control_plane_public_ip_v1")
	if err := os.MkdirAll(artifactDir, 0o755); err != nil {
		t.Fatalf("create artifact dir: %v", err)
	}
	data, err := os.ReadFile(source)
	if err != nil {
		t.Fatalf("read source snapshot: %v", err)
	}
	if err := os.WriteFile(filepath.Join(artifactDir, "snapshot.json"), data, 0o644); err != nil {
		t.Fatalf("write distributed snapshot: %v", err)
	}
	manifest := []byte(`{
  "artifact_version": "api2agent.snapshot_artifact.v0",
  "snapshot_file": "snapshot.json",
  "snapshot_version": "snapshot_control_plane_public_ip_v1",
  "snapshot_source": "pull",
  "registry_fingerprint": "sha256:other",
  "snapshot_version_policy": "explicit"
}`)
	if err := os.WriteFile(filepath.Join(artifactDir, "manifest.json"), manifest, 0o644); err != nil {
		t.Fatalf("write distributed manifest: %v", err)
	}
	pointer := []byte(`{
  "distribution_version": "api2agent.snapshot_distribution.v0",
  "snapshot_version": "snapshot_control_plane_public_ip_v1",
  "snapshot_file": "artifacts/snapshot_control_plane_public_ip_v1/snapshot.json",
  "manifest_file": "artifacts/snapshot_control_plane_public_ip_v1/manifest.json",
  "registry_fingerprint": "sha256:other",
  "snapshot_version_policy": "explicit"
}`)
	if err := os.WriteFile(filepath.Join(distributionDir, "current.json"), pointer, 0o644); err != nil {
		t.Fatalf("write current pointer: %v", err)
	}

	_, err = LoadFile(distributionDir)
	if err == nil {
		t.Fatalf("expected manifest consistency failure")
	}
	if want := "distribution manifest registry_fingerprint"; !strings.Contains(err.Error(), want) {
		t.Fatalf("expected error containing %q, got %q", want, err.Error())
	}
}
