package registry

import (
	"encoding/json"
	"fmt"
	"os"
)

func LoadFile(path string) (*Registry, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read registry: %w", err)
	}
	var registry Registry
	if err := json.Unmarshal(data, &registry); err != nil {
		return nil, fmt.Errorf("decode registry: %w", err)
	}
	if err := registry.Validate(); err != nil {
		return nil, err
	}
	return &registry, nil
}

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
			"exporter": "api2agent-control-plane-minimum-v0",
		},
	}, nil
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
		capabilities[capability.ID] = capability
	}
	if len(r.Providers) == 0 {
		return fmt.Errorf("at least one provider is required")
	}
	for _, provider := range r.Providers {
		if provider.ID == "" {
			return fmt.Errorf("provider.id is required")
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
