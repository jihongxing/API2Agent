package registry

import "time"

type Registry struct {
	Projects           []Project             `json:"projects,omitempty"`
	APIKeys            []APIKey              `json:"api_keys,omitempty"`
	Capabilities       []Capability          `json:"capabilities"`
	Providers          []Provider            `json:"providers"`
	CredentialMetadata []CredentialMetadata  `json:"credential_metadata,omitempty"`
	RoutingPolicy      RoutingPolicy         `json:"routing_policy"`
	Snapshot           SnapshotExportOptions `json:"snapshot"`
}

type Project struct {
	ID          string `json:"id"`
	Name        string `json:"name,omitempty"`
	Status      string `json:"status,omitempty"`
	DefaultMode string `json:"default_mode,omitempty"`
}

type APIKey struct {
	ID        string `json:"id"`
	ProjectID string `json:"project_id"`
	KeyPrefix string `json:"key_prefix,omitempty"`
	Status    string `json:"status,omitempty"`
}

type Capability struct {
	ID      string `json:"id"`
	Version string `json:"version"`
	Name    string `json:"name"`
}

type Provider struct {
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
	Metadata          map[string]string `json:"metadata,omitempty"`
	Status            string            `json:"status,omitempty"`
}

type CredentialMetadata struct {
	CredentialID      string   `json:"credential_id"`
	CredentialVersion string   `json:"credential_version,omitempty"`
	OwnerType         string   `json:"owner_type"`
	OwnerID           string   `json:"owner_id"`
	ProviderID        string   `json:"provider_id"`
	AuthType          string   `json:"auth_type,omitempty"`
	InjectionMode     string   `json:"injection_mode,omitempty"`
	Source            string   `json:"source,omitempty"`
	Scope             []string `json:"scope,omitempty"`
	Status            string   `json:"status,omitempty"`
	RotationHint      string   `json:"rotation_hint,omitempty"`
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

type SnapshotExportOptions struct {
	Version   string    `json:"version"`
	FetchedAt time.Time `json:"fetched_at"`
	TTL       string    `json:"ttl"`
	Source    string    `json:"source,omitempty"`
}

type RoutingSnapshot struct {
	SnapshotVersion   string            `json:"snapshot_version"`
	SnapshotFetchedAt time.Time         `json:"snapshot_fetched_at"`
	SnapshotTTL       string            `json:"snapshot_ttl"`
	SnapshotSource    string            `json:"snapshot_source"`
	Capabilities      []Capability      `json:"capabilities"`
	Providers         []Provider        `json:"providers"`
	RoutingPolicy     RoutingPolicy     `json:"routing_policy"`
	Metadata          map[string]string `json:"metadata,omitempty"`
}

type ExportArtifactManifest struct {
	ArtifactVersion       string                 `json:"artifact_version"`
	ExportedAt            time.Time              `json:"exported_at"`
	RegistryStore         string                 `json:"registry_store"`
	RegistrySource        string                 `json:"registry_source,omitempty"`
	SnapshotFile          string                 `json:"snapshot_file"`
	SnapshotVersion       string                 `json:"snapshot_version"`
	SnapshotSource        string                 `json:"snapshot_source"`
	SnapshotVersionPolicy string                 `json:"snapshot_version_policy"`
	RegistryFingerprint   string                 `json:"registry_fingerprint"`
	Validation            ExportValidationReport `json:"validation"`
}

type ExportValidationReport struct {
	Valid                   bool `json:"valid"`
	ProjectCount            int  `json:"project_count"`
	APIKeyCount             int  `json:"api_key_count"`
	CapabilityCount         int  `json:"capability_count"`
	ProviderCount           int  `json:"provider_count"`
	ActiveProviderCount     int  `json:"active_provider_count"`
	CredentialMetadataCount int  `json:"credential_metadata_count"`
}
