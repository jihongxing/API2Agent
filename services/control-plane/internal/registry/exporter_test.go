package registry

import (
	"encoding/json"
	"os"
	"path/filepath"
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
