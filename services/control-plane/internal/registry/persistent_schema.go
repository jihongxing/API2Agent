package registry

import (
	"sort"
)

type PersistentRegistryRows struct {
	Projects             []PersistentProjectRow             `json:"projects"`
	APIKeys              []PersistentAPIKeyRow              `json:"api_keys"`
	Capabilities         []PersistentCapabilityRow          `json:"capabilities"`
	Providers            []PersistentProviderRow            `json:"providers"`
	CredentialMetadata   []PersistentCredentialMetadataRow  `json:"credential_metadata"`
	RoutingPolicies      []PersistentRoutingPolicyRow       `json:"routing_policies"`
	SnapshotConfigs      []PersistentSnapshotConfigRow      `json:"snapshot_configs"`
	RegistryRevisions    []PersistentRegistryRevisionRow    `json:"registry_revisions"`
	ArtifactPublications []PersistentArtifactPublicationRow `json:"snapshot_artifact_publications"`
	AdminAuditEvents     []PersistentAdminAuditEventRow     `json:"admin_audit_events"`
	IdempotencyRecords   []PersistentIdempotencyRecordRow   `json:"admin_mutation_idempotency_records"`
	HostedPolicyVersions []PersistentHostedPolicyVersionRow `json:"hosted_policy_versions"`
	PolicyMutationDrafts []PersistentPolicyMutationDraftRow `json:"hosted_policy_mutation_drafts"`
	PolicyDraftChanges   []PersistentPolicyDraftChangeRow   `json:"hosted_policy_mutation_draft_changes"`
}

type PersistentProjectRow struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Status      string `json:"status"`
	DefaultMode string `json:"default_mode"`
}

type PersistentAPIKeyRow struct {
	ID        string `json:"id"`
	ProjectID string `json:"project_id"`
	KeyPrefix string `json:"key_prefix"`
	KeyHash   string `json:"key_hash"`
	Status    string `json:"status"`
}

type PersistentCapabilityRow struct {
	ID      string `json:"id"`
	Version string `json:"version"`
	Name    string `json:"name"`
	Status  string `json:"status"`
}

type PersistentProviderRow struct {
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
	Status            string            `json:"status"`
}

type PersistentCredentialMetadataRow struct {
	CredentialID      string   `json:"credential_id"`
	CredentialVersion string   `json:"credential_version"`
	OwnerType         string   `json:"owner_type"`
	OwnerID           string   `json:"owner_id"`
	ProviderID        string   `json:"provider_id"`
	AuthType          string   `json:"auth_type"`
	InjectionMode     string   `json:"injection_mode"`
	Source            string   `json:"source"`
	Scope             []string `json:"scope"`
	Status            string   `json:"status"`
	RotationHint      string   `json:"rotation_hint"`
}

type PersistentRoutingPolicyRow struct {
	ID             string          `json:"id"`
	ScopeType      string          `json:"scope_type"`
	ScopeID        string          `json:"scope_id"`
	Strategy       string          `json:"strategy"`
	RoutingMode    string          `json:"routing_mode"`
	RoutingSeed    *string         `json:"routing_seed,omitempty"`
	FailoverPolicy *FailoverPolicy `json:"failover_policy,omitempty"`
	Status         string          `json:"status"`
}

type PersistentSnapshotConfigRow struct {
	ID        string `json:"id"`
	Version   string `json:"version"`
	FetchedAt string `json:"fetched_at"`
	TTL       string `json:"ttl"`
	Source    string `json:"source"`
	Status    string `json:"status"`
}

type PersistentRegistryRevisionRow struct {
	ID                  int64  `json:"id,omitempty"`
	RegistryFingerprint string `json:"registry_fingerprint"`
	SnapshotVersion     string `json:"snapshot_version"`
	SourceStore         string `json:"source_store"`
	SourceRevision      string `json:"source_revision"`
}

type PersistentArtifactPublicationRow struct {
	SnapshotVersion     string `json:"snapshot_version"`
	RegistryFingerprint string `json:"registry_fingerprint"`
	SnapshotDigest      string `json:"snapshot_digest"`
	ArtifactURI         string `json:"artifact_uri"`
	ManifestURI         string `json:"manifest_uri"`
	DistributionURI     string `json:"distribution_uri"`
	Status              string `json:"status"`
}

type PersistentAdminAuditEventRow struct {
	ID           int64             `json:"id,omitempty"`
	ActorID      string            `json:"actor_id"`
	Action       string            `json:"action"`
	ResourceType string            `json:"resource_type"`
	ResourceID   string            `json:"resource_id"`
	RequestID    string            `json:"request_id"`
	Outcome      string            `json:"outcome"`
	ErrorType    string            `json:"error_type"`
	Metadata     map[string]string `json:"metadata"`
}

type PersistentIdempotencyRecordRow struct {
	ID                          int64             `json:"id,omitempty"`
	ProjectID                   string            `json:"project_id"`
	ActorID                     string            `json:"actor_id"`
	Operation                   string            `json:"operation"`
	IdempotencyKeyHash          string            `json:"idempotency_key_hash"`
	IdempotencyKeyPrefix        string            `json:"idempotency_key_prefix"`
	RequestFingerprint          string            `json:"request_fingerprint"`
	RequestSummary              map[string]string `json:"request_summary"`
	FirstRequestID              string            `json:"first_request_id"`
	Status                      string            `json:"status"`
	ResponseStatusCode          int               `json:"response_status_code,omitempty"`
	ResponseBody                string            `json:"response_body,omitempty"`
	ResponseFingerprint         string            `json:"response_fingerprint,omitempty"`
	RegistryFingerprint         string            `json:"registry_fingerprint,omitempty"`
	PreviousRegistryFingerprint string            `json:"previous_registry_fingerprint,omitempty"`
	SnapshotVersion             string            `json:"snapshot_version,omitempty"`
	Noop                        bool              `json:"noop"`
	RegistryRevisionID          *int64            `json:"registry_revision_id,omitempty"`
	AdminAuditEventID           *int64            `json:"admin_audit_event_id,omitempty"`
	ReplayCount                 int64             `json:"replay_count"`
	LastReplayRequestID         string            `json:"last_replay_request_id,omitempty"`
}

type PersistentHostedPolicyVersionRow struct {
	PolicySource      string            `json:"policy_source"`
	PolicyVersion     string            `json:"policy_version"`
	PolicyFingerprint string            `json:"policy_fingerprint"`
	Status            string            `json:"status"`
	Metadata          map[string]string `json:"metadata"`
}

type PersistentPolicyMutationDraftRow struct {
	ID                     string            `json:"id"`
	ProjectID              string            `json:"project_id"`
	OrganizationID         string            `json:"organization_id"`
	PolicySource           string            `json:"policy_source"`
	BasePolicyVersion      string            `json:"base_policy_version"`
	DraftPolicyVersion     string            `json:"draft_policy_version"`
	DraftPolicyFingerprint string            `json:"draft_policy_fingerprint"`
	Status                 string            `json:"status"`
	ActorID                string            `json:"actor_id"`
	ReviewRequestedBy      string            `json:"review_requested_by,omitempty"`
	PromotedPolicyVersion  string            `json:"promoted_policy_version,omitempty"`
	AdminAuditEventID      *int64            `json:"admin_audit_event_id,omitempty"`
	Metadata               map[string]string `json:"metadata"`
}

type PersistentPolicyDraftChangeRow struct {
	ID               int64             `json:"id,omitempty"`
	DraftID          string            `json:"draft_id"`
	ChangeSeq        int               `json:"change_seq"`
	ObjectType       string            `json:"object_type"`
	Operation        string            `json:"operation"`
	ObjectID         string            `json:"object_id"`
	ProjectID        string            `json:"project_id"`
	OrganizationID   string            `json:"organization_id"`
	PatchFingerprint string            `json:"patch_fingerprint"`
	PatchSummary     map[string]string `json:"patch_summary"`
}

func MapRegistryToPersistentRows(reg Registry) (PersistentRegistryRows, error) {
	canonical := CanonicalRegistry(reg)
	if err := canonical.Validate(); err != nil {
		return PersistentRegistryRows{}, err
	}
	fingerprint, err := canonical.Fingerprint()
	if err != nil {
		return PersistentRegistryRows{}, err
	}
	rows := PersistentRegistryRows{}
	for _, project := range canonical.Projects {
		rows.Projects = append(rows.Projects, PersistentProjectRow{
			ID:          project.ID,
			Name:        project.Name,
			Status:      defaultString(project.Status, "active"),
			DefaultMode: project.DefaultMode,
		})
	}
	for _, apiKey := range canonical.APIKeys {
		rows.APIKeys = append(rows.APIKeys, PersistentAPIKeyRow{
			ID:        apiKey.ID,
			ProjectID: apiKey.ProjectID,
			KeyPrefix: apiKey.KeyPrefix,
			KeyHash:   "",
			Status:    defaultString(apiKey.Status, "active"),
		})
	}
	for _, capability := range canonical.Capabilities {
		rows.Capabilities = append(rows.Capabilities, PersistentCapabilityRow{
			ID:      capability.ID,
			Version: capability.Version,
			Name:    capability.Name,
			Status:  "active",
		})
	}
	for _, provider := range canonical.Providers {
		rows.Providers = append(rows.Providers, PersistentProviderRow{
			ID:                provider.ID,
			CapabilityID:      provider.CapabilityID,
			CapabilityVersion: provider.CapabilityVersion,
			ProviderID:        provider.ProviderID,
			ProviderVersion:   provider.ProviderVersion,
			MappingVersion:    provider.MappingVersion,
			ToolID:            provider.ToolID,
			Regions:           append([]string(nil), provider.Regions...),
			GeoAffinity:       provider.GeoAffinity,
			EstimatedCost:     provider.EstimatedCost,
			Metadata:          copyStringMap(provider.Metadata),
			Status:            defaultString(provider.Status, "active"),
		})
	}
	for _, credential := range canonical.CredentialMetadata {
		rows.CredentialMetadata = append(rows.CredentialMetadata, PersistentCredentialMetadataRow{
			CredentialID:      credential.CredentialID,
			CredentialVersion: credential.CredentialVersion,
			OwnerType:         credential.OwnerType,
			OwnerID:           credential.OwnerID,
			ProviderID:        credential.ProviderID,
			AuthType:          defaultString(credential.AuthType, "none"),
			InjectionMode:     defaultString(credential.InjectionMode, "none"),
			Source:            defaultString(credential.Source, "none"),
			Scope:             append([]string(nil), credential.Scope...),
			Status:            defaultString(credential.Status, "active"),
			RotationHint:      credential.RotationHint,
		})
	}
	policy := defaultRoutingPolicy(canonical.RoutingPolicy)
	rows.RoutingPolicies = append(rows.RoutingPolicies, PersistentRoutingPolicyRow{
		ID:             "global",
		ScopeType:      "global",
		ScopeID:        "",
		Strategy:       policy.Strategy,
		RoutingMode:    policy.RoutingMode,
		RoutingSeed:    policy.RoutingSeed,
		FailoverPolicy: policy.FailoverPolicy,
		Status:         "active",
	})
	source := canonical.Snapshot.Source
	if source == "" {
		source = "pull"
	}
	rows.SnapshotConfigs = append(rows.SnapshotConfigs, PersistentSnapshotConfigRow{
		ID:        "active",
		Version:   canonical.Snapshot.Version,
		FetchedAt: canonical.Snapshot.FetchedAt.UTC().Format("2006-01-02T15:04:05Z07:00"),
		TTL:       canonical.Snapshot.TTL,
		Source:    source,
		Status:    "active",
	})
	rows.RegistryRevisions = append(rows.RegistryRevisions, PersistentRegistryRevisionRow{
		RegistryFingerprint: fingerprint,
		SnapshotVersion:     canonical.Snapshot.Version,
		SourceStore:         "file",
		SourceRevision:      "",
	})
	return rows, nil
}

func CanonicalRegistry(reg Registry) Registry {
	canonical := reg
	canonical.Projects = append([]Project(nil), reg.Projects...)
	canonical.APIKeys = append([]APIKey(nil), reg.APIKeys...)
	canonical.Capabilities = append([]Capability(nil), reg.Capabilities...)
	canonical.Providers = append([]Provider(nil), reg.Providers...)
	canonical.CredentialMetadata = append([]CredentialMetadata(nil), reg.CredentialMetadata...)

	sort.Slice(canonical.Projects, func(i, j int) bool {
		return canonical.Projects[i].ID < canonical.Projects[j].ID
	})
	sort.Slice(canonical.APIKeys, func(i, j int) bool {
		return canonical.APIKeys[i].ID < canonical.APIKeys[j].ID
	})
	sort.Slice(canonical.Capabilities, func(i, j int) bool {
		if canonical.Capabilities[i].ID == canonical.Capabilities[j].ID {
			return canonical.Capabilities[i].Version < canonical.Capabilities[j].Version
		}
		return canonical.Capabilities[i].ID < canonical.Capabilities[j].ID
	})
	sort.Slice(canonical.Providers, func(i, j int) bool {
		return canonical.Providers[i].ID < canonical.Providers[j].ID
	})
	for i := range canonical.Providers {
		canonical.Providers[i].Regions = append([]string(nil), canonical.Providers[i].Regions...)
		sort.Strings(canonical.Providers[i].Regions)
		canonical.Providers[i].Metadata = copyStringMap(canonical.Providers[i].Metadata)
	}
	sort.Slice(canonical.CredentialMetadata, func(i, j int) bool {
		return canonical.CredentialMetadata[i].CredentialID < canonical.CredentialMetadata[j].CredentialID
	})
	for i := range canonical.CredentialMetadata {
		canonical.CredentialMetadata[i].Scope = append([]string(nil), canonical.CredentialMetadata[i].Scope...)
		sort.Strings(canonical.CredentialMetadata[i].Scope)
	}
	return canonical
}

func copyStringMap(values map[string]string) map[string]string {
	if values == nil {
		return nil
	}
	copied := map[string]string{}
	for key, value := range values {
		copied[key] = value
	}
	return copied
}
