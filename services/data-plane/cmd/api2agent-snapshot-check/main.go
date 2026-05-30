package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"api2agent/services/data-plane/internal/snapshots"
)

type Report struct {
	SnapshotPath          string `json:"snapshot_path"`
	SnapshotVersion       string `json:"snapshot_version,omitempty"`
	SnapshotSource        string `json:"snapshot_source,omitempty"`
	SnapshotTTL           string `json:"snapshot_ttl,omitempty"`
	CapabilityCount       int    `json:"capability_count"`
	ProviderCount         int    `json:"provider_count"`
	RoutingStrategy       string `json:"routing_strategy,omitempty"`
	RoutingMode           string `json:"routing_mode,omitempty"`
	Exporter              string `json:"exporter,omitempty"`
	RegistryFingerprint   string `json:"registry_fingerprint,omitempty"`
	SnapshotVersionPolicy string `json:"snapshot_version_policy,omitempty"`
	Passed                bool   `json:"passed"`
	Error                 string `json:"error,omitempty"`
}

func main() {
	snapshotPath := flag.String("snapshot", "", "path to routing snapshot json")
	flag.Parse()

	report, err := run(*snapshotPath)
	if err != nil {
		report.Passed = false
		report.Error = err.Error()
		_ = json.NewEncoder(os.Stdout).Encode(report)
		os.Exit(1)
	}
	report.Passed = true
	_ = json.NewEncoder(os.Stdout).Encode(report)
}

func run(snapshotPath string) (Report, error) {
	report := Report{SnapshotPath: snapshotPath}
	if snapshotPath == "" {
		return report, fmt.Errorf("--snapshot is required")
	}
	snapshot, err := snapshots.LoadFile(snapshotPath)
	if err != nil {
		return report, err
	}
	report.SnapshotVersion = snapshot.SnapshotVersion
	report.SnapshotSource = snapshot.SnapshotSource
	report.SnapshotTTL = snapshot.SnapshotTTL
	report.CapabilityCount = len(snapshot.Capabilities)
	report.ProviderCount = len(snapshot.Providers)
	report.RoutingStrategy = snapshot.RoutingPolicy.Strategy
	report.RoutingMode = snapshot.RoutingPolicy.RoutingMode
	report.Exporter = snapshot.Metadata["exporter"]
	report.RegistryFingerprint = snapshot.Metadata["registry_fingerprint"]
	report.SnapshotVersionPolicy = snapshot.Metadata["snapshot_version_policy"]

	if _, err := snapshot.TTLDuration(); err != nil {
		return report, err
	}
	if len(snapshot.Capabilities) == 0 {
		return report, fmt.Errorf("snapshot has no capabilities")
	}
	if len(snapshot.Providers) == 0 {
		return report, fmt.Errorf("snapshot has no providers")
	}
	if snapshot.RoutingPolicy.Strategy == "" {
		return report, fmt.Errorf("snapshot routing strategy is required")
	}
	if snapshot.RoutingPolicy.RoutingMode == "" {
		return report, fmt.Errorf("snapshot routing mode is required")
	}
	for _, provider := range snapshot.Providers {
		if provider.ID == "" {
			return report, fmt.Errorf("provider.id is required")
		}
		if provider.CapabilityID == "" {
			return report, fmt.Errorf("provider %q capability_id is required", provider.ID)
		}
		if provider.ProviderID == "" {
			return report, fmt.Errorf("provider %q provider_id is required", provider.ID)
		}
		if provider.ProviderVersion == "" {
			return report, fmt.Errorf("provider %q provider_version is required", provider.ID)
		}
		if provider.MappingVersion == "" {
			return report, fmt.Errorf("provider %q mapping_version is required", provider.ID)
		}
	}
	return report, nil
}
