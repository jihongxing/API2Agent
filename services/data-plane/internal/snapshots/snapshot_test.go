package snapshots

import (
	"path/filepath"
	"testing"
	"time"
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
