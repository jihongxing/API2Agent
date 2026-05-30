package snapshots

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
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
	DistributionVersion   string `json:"distribution_version"`
	SnapshotVersion       string `json:"snapshot_version"`
	SnapshotFile          string `json:"snapshot_file"`
	ManifestFile          string `json:"manifest_file,omitempty"`
	RegistryFingerprint   string `json:"registry_fingerprint,omitempty"`
	SnapshotVersionPolicy string `json:"snapshot_version_policy,omitempty"`
	SnapshotDigest        string `json:"snapshot_digest,omitempty"`
}

type DistributionManifest struct {
	SnapshotFile          string `json:"snapshot_file"`
	SnapshotVersion       string `json:"snapshot_version"`
	SnapshotSource        string `json:"snapshot_source,omitempty"`
	RegistryFingerprint   string `json:"registry_fingerprint,omitempty"`
	SnapshotVersionPolicy string `json:"snapshot_version_policy,omitempty"`
	SnapshotDigest        string `json:"snapshot_digest,omitempty"`
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
	if requiresStrictMetadata(snapshot.Metadata) {
		for _, key := range []string{"schema_version", "registry_fingerprint", "snapshot_version_policy"} {
			if snapshot.Metadata[key] == "" {
				return fmt.Errorf("control plane snapshot metadata.%s is required", key)
			}
		}
	}
	schemaVersion := snapshot.Metadata["schema_version"]
	if schemaVersion != "" && schemaVersion != protocol.SchemaVersion {
		return fmt.Errorf("snapshot schema_version %q is incompatible with data plane schema_version %q", schemaVersion, protocol.SchemaVersion)
	}
	return nil
}

func requiresStrictMetadata(metadata map[string]string) bool {
	return metadata["exporter"] != "" || metadata["registry_fingerprint"] != "" || metadata["snapshot_version_policy"] != ""
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
	snapshotPath, err := safeJoinRelative(baseDir, pointer.SnapshotFile, "distribution pointer snapshot_file", "distribution")
	if err != nil {
		return "", err
	}
	if pointer.ManifestFile != "" {
		manifestPath, err := safeJoinRelative(baseDir, pointer.ManifestFile, "distribution pointer manifest_file", "distribution")
		if err != nil {
			return "", err
		}
		if err := validateDistributionManifest(pointer, manifestPath, snapshotPath); err != nil {
			return "", err
		}
	}
	return snapshotPath, nil
}

func validateDistributionManifest(pointer DistributionPointer, manifestPath string, snapshotPath string) error {
	manifestData, err := os.ReadFile(manifestPath)
	if err != nil {
		return fmt.Errorf("read distribution manifest: %w", err)
	}
	var manifest DistributionManifest
	if err := json.Unmarshal(manifestData, &manifest); err != nil {
		return fmt.Errorf("decode distribution manifest: %w", err)
	}
	if manifest.SnapshotFile == "" {
		return fmt.Errorf("distribution manifest snapshot_file is required")
	}
	if manifest.SnapshotVersion == "" {
		return fmt.Errorf("distribution manifest snapshot_version is required")
	}
	if manifest.RegistryFingerprint == "" {
		return fmt.Errorf("distribution manifest registry_fingerprint is required")
	}
	if manifest.SnapshotVersionPolicy == "" {
		return fmt.Errorf("distribution manifest snapshot_version_policy is required")
	}
	if manifest.SnapshotDigest == "" {
		return fmt.Errorf("distribution manifest snapshot_digest is required")
	}
	manifestSnapshotPath, err := safeJoinRelative(filepath.Dir(manifestPath), manifest.SnapshotFile, "distribution manifest snapshot_file", "artifact")
	if err != nil {
		return err
	}
	if filepath.Clean(manifestSnapshotPath) != filepath.Clean(snapshotPath) {
		return fmt.Errorf("distribution manifest snapshot_file %q does not match pointer snapshot_file %q", manifest.SnapshotFile, pointer.SnapshotFile)
	}
	if manifest.SnapshotVersion != pointer.SnapshotVersion {
		return fmt.Errorf("distribution manifest snapshot_version %q does not match pointer snapshot_version %q", manifest.SnapshotVersion, pointer.SnapshotVersion)
	}
	if pointer.RegistryFingerprint != "" && manifest.RegistryFingerprint != pointer.RegistryFingerprint {
		return fmt.Errorf("distribution manifest registry_fingerprint %q does not match pointer registry_fingerprint %q", manifest.RegistryFingerprint, pointer.RegistryFingerprint)
	}
	if pointer.SnapshotVersionPolicy != "" && manifest.SnapshotVersionPolicy != pointer.SnapshotVersionPolicy {
		return fmt.Errorf("distribution manifest snapshot_version_policy %q does not match pointer snapshot_version_policy %q", manifest.SnapshotVersionPolicy, pointer.SnapshotVersionPolicy)
	}
	if pointer.SnapshotDigest != "" && manifest.SnapshotDigest != pointer.SnapshotDigest {
		return fmt.Errorf("distribution manifest snapshot_digest %q does not match pointer snapshot_digest %q", manifest.SnapshotDigest, pointer.SnapshotDigest)
	}
	snapshotData, err := os.ReadFile(snapshotPath)
	if err != nil {
		return fmt.Errorf("read distribution snapshot: %w", err)
	}
	snapshotDigest := digestBytes(snapshotData)
	if manifest.SnapshotDigest != snapshotDigest {
		return fmt.Errorf("distribution manifest snapshot_digest %q does not match snapshot file digest %q", manifest.SnapshotDigest, snapshotDigest)
	}
	var snapshot Snapshot
	if err := json.Unmarshal(snapshotData, &snapshot); err != nil {
		return fmt.Errorf("decode distribution snapshot: %w", err)
	}
	if snapshot.SnapshotVersion != manifest.SnapshotVersion {
		return fmt.Errorf("distribution manifest snapshot_version %q does not match snapshot snapshot_version %q", manifest.SnapshotVersion, snapshot.SnapshotVersion)
	}
	if manifest.RegistryFingerprint != snapshot.Metadata["registry_fingerprint"] {
		return fmt.Errorf("distribution manifest registry_fingerprint %q does not match snapshot metadata.registry_fingerprint %q", manifest.RegistryFingerprint, snapshot.Metadata["registry_fingerprint"])
	}
	if manifest.SnapshotVersionPolicy != snapshot.Metadata["snapshot_version_policy"] {
		return fmt.Errorf("distribution manifest snapshot_version_policy %q does not match snapshot metadata.snapshot_version_policy %q", manifest.SnapshotVersionPolicy, snapshot.Metadata["snapshot_version_policy"])
	}
	return nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func safeJoinRelative(baseDir string, reference string, field string, scope string) (string, error) {
	if reference == "" {
		return "", fmt.Errorf("%s is required", field)
	}
	relativePath := filepath.FromSlash(reference)
	if filepath.IsAbs(relativePath) {
		return "", fmt.Errorf("%s %q is not safe for %s path", field, reference, scope)
	}
	cleanPath := filepath.Clean(relativePath)
	if cleanPath == "." || cleanPath == ".." || strings.HasPrefix(cleanPath, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("%s %q is not safe for %s path", field, reference, scope)
	}
	return filepath.Join(baseDir, cleanPath), nil
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
