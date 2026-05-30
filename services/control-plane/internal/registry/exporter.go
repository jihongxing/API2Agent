package registry

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"
)

func WriteSnapshotFile(path string, snapshot RoutingSnapshot) error {
	data, err := json.MarshalIndent(snapshot, "", "  ")
	if err != nil {
		return fmt.Errorf("encode snapshot: %w", err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(path, data, 0o644); err != nil {
		return fmt.Errorf("write snapshot: %w", err)
	}
	return nil
}

func (r Registry) ExportSnapshot() (RoutingSnapshot, error) {
	if err := r.Validate(); err != nil {
		return RoutingSnapshot{}, err
	}
	fingerprint, err := r.Fingerprint()
	if err != nil {
		return RoutingSnapshot{}, err
	}
	source := r.Snapshot.Source
	if source == "" {
		source = "pull"
	}
	return RoutingSnapshot{
		SnapshotVersion:   r.Snapshot.Version,
		SnapshotFetchedAt: r.Snapshot.FetchedAt,
		SnapshotTTL:       r.Snapshot.TTL,
		SnapshotSource:    source,
		Capabilities:      r.Capabilities,
		Providers:         activeProviders(r.Providers),
		RoutingPolicy:     defaultRoutingPolicy(r.RoutingPolicy),
		Metadata: map[string]string{
			"exporter":                "api2agent-control-plane-minimum-v0",
			"registry_fingerprint":    fingerprint,
			"snapshot_version_policy": "explicit",
		},
	}, nil
}

func (r Registry) Fingerprint() (string, error) {
	if err := r.Validate(); err != nil {
		return "", err
	}
	data, err := json.Marshal(r)
	if err != nil {
		return "", fmt.Errorf("encode registry fingerprint input: %w", err)
	}
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func (r Registry) Validate() error {
	if r.Snapshot.Version == "" {
		return fmt.Errorf("snapshot.version is required")
	}
	if r.Snapshot.FetchedAt.IsZero() {
		return fmt.Errorf("snapshot.fetched_at is required")
	}
	if r.Snapshot.TTL == "" {
		return fmt.Errorf("snapshot.ttl is required")
	}
	if _, err := time.ParseDuration(r.Snapshot.TTL); err != nil {
		return fmt.Errorf("snapshot.ttl is invalid: %w", err)
	}
	if !oneOf(defaultString(r.Snapshot.Source, "pull"), "push", "pull") {
		return fmt.Errorf("snapshot.source must be push or pull")
	}
	projects := map[string]Project{}
	for _, project := range r.Projects {
		if project.ID == "" {
			return fmt.Errorf("project.id is required")
		}
		if _, exists := projects[project.ID]; exists {
			return fmt.Errorf("project %q is duplicated", project.ID)
		}
		if !oneOf(defaultString(project.Status, "active"), "active", "disabled") {
			return fmt.Errorf("project %q status %q is invalid", project.ID, project.Status)
		}
		if project.DefaultMode != "" && !oneOf(project.DefaultMode, "direct", "proxy", "shadow", "replay") {
			return fmt.Errorf("project %q default_mode %q is invalid", project.ID, project.DefaultMode)
		}
		projects[project.ID] = project
	}
	apiKeys := map[string]APIKey{}
	for _, apiKey := range r.APIKeys {
		if apiKey.ID == "" {
			return fmt.Errorf("api_key.id is required")
		}
		if _, exists := apiKeys[apiKey.ID]; exists {
			return fmt.Errorf("api_key %q is duplicated", apiKey.ID)
		}
		if apiKey.ProjectID == "" {
			return fmt.Errorf("api_key %q project_id is required", apiKey.ID)
		}
		if _, ok := projects[apiKey.ProjectID]; !ok {
			return fmt.Errorf("api_key %q references unknown project %q", apiKey.ID, apiKey.ProjectID)
		}
		if !oneOf(defaultString(apiKey.Status, "active"), "active", "disabled", "revoked") {
			return fmt.Errorf("api_key %q status %q is invalid", apiKey.ID, apiKey.Status)
		}
		apiKeys[apiKey.ID] = apiKey
	}
	if len(r.Capabilities) == 0 {
		return fmt.Errorf("at least one capability is required")
	}
	capabilities := map[string]Capability{}
	for _, capability := range r.Capabilities {
		if capability.ID == "" {
			return fmt.Errorf("capability.id is required")
		}
		if capability.Version == "" {
			return fmt.Errorf("capability %q version is required", capability.ID)
		}
		if _, exists := capabilities[capability.ID]; exists {
			return fmt.Errorf("capability %q is duplicated", capability.ID)
		}
		capabilities[capability.ID] = capability
	}
	if len(r.Providers) == 0 {
		return fmt.Errorf("at least one provider is required")
	}
	providers := map[string]Provider{}
	providerIDs := map[string]bool{}
	toolIDs := map[string]bool{}
	activeProviderCount := 0
	for _, provider := range r.Providers {
		if provider.ID == "" {
			return fmt.Errorf("provider.id is required")
		}
		if _, exists := providers[provider.ID]; exists {
			return fmt.Errorf("provider %q is duplicated", provider.ID)
		}
		if provider.CapabilityID == "" {
			return fmt.Errorf("provider %q capability_id is required", provider.ID)
		}
		capability, ok := capabilities[provider.CapabilityID]
		if !ok {
			return fmt.Errorf("provider %q references unknown capability %q", provider.ID, provider.CapabilityID)
		}
		if provider.CapabilityVersion == "" {
			return fmt.Errorf("provider %q capability_version is required", provider.ID)
		}
		if provider.CapabilityVersion != capability.Version {
			return fmt.Errorf("provider %q capability_version %q does not match capability %q version %q", provider.ID, provider.CapabilityVersion, capability.ID, capability.Version)
		}
		if provider.ProviderID == "" {
			return fmt.Errorf("provider %q provider_id is required", provider.ID)
		}
		if provider.ProviderVersion == "" {
			return fmt.Errorf("provider %q provider_version is required", provider.ID)
		}
		if provider.MappingVersion == "" {
			return fmt.Errorf("provider %q mapping_version is required", provider.ID)
		}
		if provider.ToolID == "" {
			return fmt.Errorf("provider %q tool_id is required", provider.ID)
		}
		if len(provider.Regions) == 0 {
			return fmt.Errorf("provider %q regions are required", provider.ID)
		}
		if provider.GeoAffinity == "" {
			return fmt.Errorf("provider %q geo_affinity is required", provider.ID)
		}
		if !oneOf(defaultString(provider.Status, "active"), "active", "disabled") {
			return fmt.Errorf("provider %q status %q is invalid", provider.ID, provider.Status)
		}
		if defaultString(provider.Status, "active") == "active" {
			activeProviderCount++
			if strings.TrimSpace(provider.Metadata["base_url"]) == "" {
				return fmt.Errorf("active provider %q metadata.base_url is required", provider.ID)
			}
		}
		providers[provider.ID] = provider
		providerIDs[provider.ProviderID] = true
		toolIDs[provider.ToolID] = true
	}
	if activeProviderCount == 0 {
		return fmt.Errorf("at least one active provider is required")
	}
	if err := validateRoutingPolicy(defaultRoutingPolicy(r.RoutingPolicy)); err != nil {
		return err
	}
	credentials := map[string]CredentialMetadata{}
	for _, credential := range r.CredentialMetadata {
		if credential.CredentialID == "" {
			return fmt.Errorf("credential_metadata.credential_id is required")
		}
		if _, exists := credentials[credential.CredentialID]; exists {
			return fmt.Errorf("credential_metadata %q is duplicated", credential.CredentialID)
		}
		if !oneOf(credential.OwnerType, "user", "project", "platform", "provider") {
			return fmt.Errorf("credential_metadata %q owner_type %q is invalid", credential.CredentialID, credential.OwnerType)
		}
		if credential.OwnerID == "" {
			return fmt.Errorf("credential_metadata %q owner_id is required", credential.CredentialID)
		}
		if credential.OwnerType == "project" {
			if _, ok := projects[credential.OwnerID]; !ok {
				return fmt.Errorf("credential_metadata %q references unknown project owner %q", credential.CredentialID, credential.OwnerID)
			}
		}
		if credential.ProviderID == "" {
			return fmt.Errorf("credential_metadata %q provider_id is required", credential.CredentialID)
		}
		if !providerIDs[credential.ProviderID] {
			return fmt.Errorf("credential_metadata %q references unknown provider_id %q", credential.CredentialID, credential.ProviderID)
		}
		if credential.AuthType != "" && !oneOf(credential.AuthType, "api_key", "bearer", "basic", "oauth", "none") {
			return fmt.Errorf("credential_metadata %q auth_type %q is invalid", credential.CredentialID, credential.AuthType)
		}
		if credential.InjectionMode != "" && !oneOf(credential.InjectionMode, "header", "query", "body", "none") {
			return fmt.Errorf("credential_metadata %q injection_mode %q is invalid", credential.CredentialID, credential.InjectionMode)
		}
		if credential.Source != "" && !oneOf(credential.Source, "env", "config", "inline", "vault", "none") {
			return fmt.Errorf("credential_metadata %q source %q is invalid", credential.CredentialID, credential.Source)
		}
		if !oneOf(defaultString(credential.Status, "active"), "active", "disabled", "expired") {
			return fmt.Errorf("credential_metadata %q status %q is invalid", credential.CredentialID, credential.Status)
		}
		if err := validateCredentialScope(credential, capabilities, providerIDs, toolIDs); err != nil {
			return err
		}
		credentials[credential.CredentialID] = credential
	}
	return nil
}

func activeProviders(providers []Provider) []Provider {
	active := make([]Provider, 0, len(providers))
	for _, provider := range providers {
		if provider.Status == "disabled" {
			continue
		}
		active = append(active, provider)
	}
	return active
}

func defaultRoutingPolicy(policy RoutingPolicy) RoutingPolicy {
	if policy.Strategy == "" {
		policy.Strategy = "first"
	}
	if policy.RoutingMode == "" {
		policy.RoutingMode = "deterministic"
	}
	return policy
}

func validateRoutingPolicy(policy RoutingPolicy) error {
	if !oneOf(policy.Strategy, "first", "lowest_cost", "lowest_latency", "region_aware_latency", "highest_success_rate", "balanced") {
		return fmt.Errorf("routing_policy.strategy %q is invalid", policy.Strategy)
	}
	if !oneOf(policy.RoutingMode, "deterministic", "stochastic") {
		return fmt.Errorf("routing_policy.routing_mode %q is invalid", policy.RoutingMode)
	}
	if policy.FailoverPolicy != nil {
		if policy.FailoverPolicy.Enabled && policy.FailoverPolicy.MaxAttempts <= 0 {
			return fmt.Errorf("routing_policy.failover_policy.max_attempts must be positive when enabled")
		}
		if policy.FailoverPolicy.AttemptTimeoutPolicy != "" && !oneOf(policy.FailoverPolicy.AttemptTimeoutPolicy, "fixed", "remaining_budget") {
			return fmt.Errorf("routing_policy.failover_policy.attempt_timeout_policy %q is invalid", policy.FailoverPolicy.AttemptTimeoutPolicy)
		}
		for _, statusCode := range policy.FailoverPolicy.RetryOnStatusCodes {
			if statusCode < 100 || statusCode > 599 {
				return fmt.Errorf("routing_policy.failover_policy retry status code %d is invalid", statusCode)
			}
		}
	}
	return nil
}

func validateCredentialScope(credential CredentialMetadata, capabilities map[string]Capability, providerIDs map[string]bool, toolIDs map[string]bool) error {
	for _, scope := range credential.Scope {
		switch {
		case scope == "*" || scope == "*:*":
			continue
		case strings.HasPrefix(scope, "capability:"):
			capabilityID := strings.TrimPrefix(scope, "capability:")
			if _, ok := capabilities[capabilityID]; !ok {
				return fmt.Errorf("credential_metadata %q scope references unknown capability %q", credential.CredentialID, capabilityID)
			}
		case strings.HasPrefix(scope, "provider:"):
			providerID := strings.TrimPrefix(scope, "provider:")
			if !providerIDs[providerID] {
				return fmt.Errorf("credential_metadata %q scope references unknown provider_id %q", credential.CredentialID, providerID)
			}
		case strings.HasPrefix(scope, "tool:"):
			toolID := strings.TrimPrefix(scope, "tool:")
			if !toolIDs[toolID] {
				return fmt.Errorf("credential_metadata %q scope references unknown tool_id %q", credential.CredentialID, toolID)
			}
		default:
			if _, ok := capabilities[scope]; ok {
				continue
			}
			if toolIDs[scope] {
				continue
			}
			return fmt.Errorf("credential_metadata %q scope %q is not resolvable", credential.CredentialID, scope)
		}
	}
	return nil
}

func defaultString(value string, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}

func oneOf(value string, allowed ...string) bool {
	for _, item := range allowed {
		if value == item {
			return true
		}
	}
	return false
}
