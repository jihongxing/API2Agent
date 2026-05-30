package main

import (
	"path/filepath"
	"testing"
)

func TestRunAcceptsControlPlaneExportedSnapshot(t *testing.T) {
	report, err := run(filepath.Join("..", "..", "testdata", "snapshots", "control-plane-public-ip.json"))
	if err != nil {
		t.Fatalf("run snapshot check: %v", err)
	}
	if report.SnapshotVersion != "snapshot_control_plane_public_ip_v1" {
		t.Fatalf("unexpected snapshot version: %q", report.SnapshotVersion)
	}
	if report.Exporter != "api2agent-control-plane-minimum-v0" {
		t.Fatalf("unexpected exporter: %q", report.Exporter)
	}
}

func TestRunRejectsMissingSnapshotPath(t *testing.T) {
	if _, err := run(""); err == nil {
		t.Fatalf("expected missing path error")
	}
}
