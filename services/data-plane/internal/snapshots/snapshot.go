package snapshots

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"api2agent/services/data-plane/internal/protocol"
)

type Snapshot struct {
	SnapshotVersion   string              `json:"snapshot_version"`
	SnapshotFetchedAt time.Time           `json:"snapshot_fetched_at"`
	SnapshotTTL       string              `json:"snapshot_ttl"`
	SnapshotSource    string              `json:"snapshot_source"`
	Capabilities      []Capability        `json:"capabilities"`
	Providers         []ProviderCandidate `json:"providers"`
	RoutingPolicy     RoutingPolicy       `json:"routing_policy"`
	Metadata          map[string]string   `json:"metadata,omitempty"`
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
	Strategy       string          `json:"strategy"`
	RoutingMode    string          `json:"routing_mode"`
	RoutingSeed    *string         `json:"routing_seed,omitempty"`
	FailoverPolicy *FailoverPolicy `json:"failover_policy,omitempty"`
}

type FailoverPolicy struct {
	Enabled              bool     `json:"enabled"`
	MaxAttempts          int      `json:"max_attempts"`
	RetryOnErrorTypes    []string `json:"retry_on_error_types,omitempty"`
	RetryOnStatusCodes   []int    `json:"retry_on_status_codes,omitempty"`
	AttemptTimeoutPolicy string   `json:"attempt_timeout_policy,omitempty"`
}

type DistributionPointer struct {
	DistributionVersion string `json:"distribution_version"`
	SnapshotVersion     string `json:"snapshot_version"`
	SnapshotFile        string `json:"snapshot_file"`
	ManifestFile        string `json:"manifest_file,omitempty"`
	RegistryFingerprint string `json:"registry_fingerprint,omitempty"`
}

func LoadFile(path string) (*Snapshot, error) {
	resolvedPath, err := ResolvePath(path)
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(resolvedPath)
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
	if err := ValidateCompatibility(&snapshot); err != nil {
		return nil, err
	}
	return &snapshot, nil
}

func ValidateCompatibility(snapshot *Snapshot) error {
	if snapshot == nil {
		return fmt.Errorf("snapshot is required")
	}
	schemaVersion := snapshot.Metadata["schema_version"]
	if schemaVersion != "" && schemaVersion != protocol.SchemaVersion {
		return fmt.Errorf("snapshot schema_version %q is incompatible with data plane schema_version %q", schemaVersion, protocol.SchemaVersion)
	}
	return nil
}

func ResolvePath(path string) (string, error) {
	if path == "" {
		return "", fmt.Errorf("snapshot path is required")
	}
	info, err := os.Stat(path)
	if err != nil {
		return "", fmt.Errorf("stat snapshot path: %w", err)
	}
	if info.IsDir() {
		return resolveDistributionPointer(filepath.Join(path, "current.json"), path)
	}
	if filepath.Base(path) == "current.json" {
		return resolveDistributionPointer(path, filepath.Dir(path))
	}
	return path, nil
}

func resolveDistributionPointer(path string, baseDir string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read distribution pointer: %w", err)
	}
	var pointer DistributionPointer
	if err := json.Unmarshal(data, &pointer); err != nil {
		return "", fmt.Errorf("decode distribution pointer: %w", err)
	}
	if pointer.SnapshotFile == "" {
		return "", fmt.Errorf("distribution pointer snapshot_file is required")
	}
	if pointer.SnapshotVersion == "" {
		return "", fmt.Errorf("distribution pointer snapshot_version is required")
	}
	snapshotPath := filepath.FromSlash(pointer.SnapshotFile)
	if !filepath.IsAbs(snapshotPath) {
		snapshotPath = filepath.Join(baseDir, snapshotPath)
	}
	return snapshotPath, nil
}

func (s Snapshot) TTLDuration() (time.Duration, error) {
	if s.SnapshotTTL == "" {
		return 0, nil
	}
	duration, err := time.ParseDuration(s.SnapshotTTL)
	if err != nil {
		return 0, fmt.Errorf("parse snapshot_ttl: %w", err)
	}
	return duration, nil
}

func (s Snapshot) ExpiresAt() (*time.Time, error) {
	duration, err := s.TTLDuration()
	if err != nil {
		return nil, err
	}
	if duration == 0 || s.SnapshotFetchedAt.IsZero() {
		return nil, nil
	}
	expiresAt := s.SnapshotFetchedAt.Add(duration)
	return &expiresAt, nil
}

func (s Snapshot) IsExpired(now time.Time) (bool, error) {
	expiresAt, err := s.ExpiresAt()
	if err != nil {
		return false, err
	}
	if expiresAt == nil {
		return false, nil
	}
	return !now.Before(*expiresAt), nil
}
