package routing

import (
	"fmt"
	"time"

	"api2agent/services/data-plane/internal/protocol"
	"api2agent/services/data-plane/internal/snapshots"
)

type DecisionInput struct {
	RequestID         string
	Identity          protocol.IdentityRef
	CapabilityID      string
	ClientRegion      *string
	Snapshot          *snapshots.Snapshot
	ExecutionBudgetMS int
}

type DecisionResult struct {
	Decision protocol.RoutingDecision
	Provider snapshots.ProviderCandidate
}

func Decide(input DecisionInput) (DecisionResult, error) {
	if input.Snapshot == nil {
		return DecisionResult{}, fmt.Errorf("snapshot is required")
	}
	var candidates []snapshots.ProviderCandidate
	for _, provider := range input.Snapshot.Providers {
		if provider.CapabilityID == input.CapabilityID {
			candidates = append(candidates, provider)
		}
	}
	if len(candidates) == 0 {
		return DecisionResult{}, fmt.Errorf("no provider for capability %q", input.CapabilityID)
	}

	selected := candidates[0]
	selectedRegion := selectProviderRegion(input.ClientRegion, selected)
	candidateIDs := make([]string, 0, len(candidates))
	for _, candidate := range candidates {
		candidateIDs = append(candidateIDs, candidate.ID)
	}
	now := time.Now().UTC()
	decisionID := NewID("route")
	strategy := input.Snapshot.RoutingPolicy.Strategy
	if strategy == "" {
		strategy = "first"
	}
	routingMode := input.Snapshot.RoutingPolicy.RoutingMode
	if routingMode == "" {
		routingMode = "deterministic"
	}
	decision := protocol.RoutingDecision{
		ID:                     decisionID,
		SchemaVersion:          protocol.SchemaVersion,
		RequestID:              input.RequestID,
		Identity:               input.Identity,
		CapabilityID:           input.CapabilityID,
		Strategy:               strategy,
		Topology:               protocol.NetworkTopology{ClientRegion: input.ClientRegion, SelectedProviderRegion: selectedRegion},
		CandidateProviderIDs:   candidateIDs,
		RankedProviderIDs:      candidateIDs,
		SelectedProviderID:     &selected.ID,
		SelectedProviderRegion: selectedRegion,
		SnapshotVersion:        input.Snapshot.SnapshotVersion,
		RoutingMode:            routingMode,
		RoutingSeed:            input.Snapshot.RoutingPolicy.RoutingSeed,
		FailoverPolicy: &protocol.FailoverPolicy{
			Enabled:              false,
			MaxAttempts:          1,
			AttemptTimeoutPolicy: "fixed",
		},
		CreatedAt: now,
	}
	return DecisionResult{Decision: decision, Provider: selected}, nil
}

func selectProviderRegion(clientRegion *string, provider snapshots.ProviderCandidate) *string {
	if clientRegion != nil {
		for _, region := range provider.Regions {
			if region == *clientRegion {
				value := region
				return &value
			}
		}
	}
	for _, region := range provider.Regions {
		if region == "global" {
			value := region
			return &value
		}
	}
	if provider.GeoAffinity == "global" {
		value := "global"
		return &value
	}
	if len(provider.Regions) > 0 {
		value := provider.Regions[0]
		return &value
	}
	return nil
}
