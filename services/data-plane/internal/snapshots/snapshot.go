package snapshots

import (
	"encoding/json"
	"fmt"
	"os"
	"time"
)

type Snapshot struct {
	SnapshotVersion   string              `json:"snapshot_version"`
	SnapshotFetchedAt time.Time           `json:"snapshot_fetched_at"`
	SnapshotTTL       string              `json:"snapshot_ttl"`
	SnapshotSource    string              `json:"snapshot_source"`
	Capabilities      []Capability        `json:"capabilities"`
	Providers         []ProviderCandidate `json:"providers"`
	RoutingPolicy     RoutingPolicy       `json:"routing_policy"`
}

type Capability struct {
	ID      string `json:"id"`
	Version string `json:"version"`
	Name    string `json:"name"`
}

type ProviderCandidate struct {
	ID                string            `json:"id"`
	CapabilityID      string            `json:"capability_id"`
	CapabilityVersion string            `json:"capability_version"`
	ProviderID        string            `json:"provider_id"`
	ProviderVersion   string            `json:"provider_version"`
	MappingVersion    string            `json:"mapping_version"`
	ToolID            string            `json:"tool_id"`
	Regions           []string          `json:"regions"`
	GeoAffinity       string            `json:"geo_affinity"`
	EstimatedCost     float64           `json:"estimated_cost"`
	Metadata          map[string]string `json:"metadata"`
}

type RoutingPolicy struct {
	Strategy    string  `json:"strategy"`
	RoutingMode string  `json:"routing_mode"`
	RoutingSeed *string `json:"routing_seed,omitempty"`
}

func LoadFile(path string) (*Snapshot, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read snapshot: %w", err)
	}
	var snapshot Snapshot
	if err := json.Unmarshal(data, &snapshot); err != nil {
		return nil, fmt.Errorf("decode snapshot: %w", err)
	}
	if snapshot.SnapshotVersion == "" {
		return nil, fmt.Errorf("snapshot_version is required")
	}
	if snapshot.SnapshotSource == "" {
		snapshot.SnapshotSource = "pull"
	}
	if snapshot.RoutingPolicy.Strategy == "" {
		snapshot.RoutingPolicy.Strategy = "first"
	}
	if snapshot.RoutingPolicy.RoutingMode == "" {
		snapshot.RoutingPolicy.RoutingMode = "deterministic"
	}
	return &snapshot, nil
}
