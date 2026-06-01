package registry

import (
	"fmt"
	"reflect"
	"sort"
	"strings"
)

const (
	ProjectPartitionReplaceOperation = "registry.project_partition_replace"

	providerOwnerProjectMetadataKey = "owner_project_id"
)

type ProjectPartitionMutationCounts struct {
	ProjectsChanged           int `json:"projects_changed"`
	APIKeysChanged            int `json:"api_keys_changed"`
	CredentialMetadataChanged int `json:"credential_metadata_changed"`
	ProvidersChanged          int `json:"providers_changed"`
}

type ProjectPartitionMutationViolation struct {
	ObjectType string `json:"object_type"`
	ObjectID   string `json:"object_id"`
	Reason     string `json:"reason"`
}

type ProjectPartitionMutationDecision struct {
	PartitionProjectID      string                              `json:"partition_project_id"`
	Operation               string                              `json:"operation"`
	Allowed                 bool                                `json:"allowed"`
	DiffFingerprint         string                              `json:"partition_diff_fingerprint"`
	Counts                  ProjectPartitionMutationCounts      `json:"counts"`
	RejectedCounts          map[string]int                      `json:"rejected_counts,omitempty"`
	Violations              []ProjectPartitionMutationViolation `json:"violations,omitempty"`
	ProposedFingerprint     string                              `json:"proposed_registry_fingerprint,omitempty"`
	PreviousFingerprint     string                              `json:"previous_registry_fingerprint,omitempty"`
	SnapshotBoundaryChanged bool                                `json:"snapshot_boundary_changed"`
}

func ValidateProjectPartitionMutation(current Registry, proposed Registry, projectID string) (ProjectPartitionMutationDecision, error) {
	projectID = strings.TrimSpace(projectID)
	decision := ProjectPartitionMutationDecision{
		PartitionProjectID: projectID,
		Operation:          ProjectPartitionReplaceOperation,
		Allowed:            true,
		RejectedCounts:     map[string]int{},
	}
	if projectID == "" {
		decision.Allowed = false
		decision.addViolation("principal", "", "project_scope_required")
		decision.finalize()
		return decision, mutationError("AUTHZ_DENIED", "caller", false, fmt.Errorf("project partition mutation requires a project-scoped principal"))
	}

	current = CanonicalRegistry(current)
	if err := current.Validate(); err != nil {
		decision.Allowed = false
		decision.addViolation("registry", "current", "current_registry_invalid")
		decision.finalize()
		return decision, mutationError("REGISTRY_MUTATION_INVALID", "caller", false, fmt.Errorf("current registry is invalid: %w", err))
	}
	proposed = CanonicalRegistry(proposed)
	if err := proposed.Validate(); err != nil {
		decision.Allowed = false
		decision.addViolation("registry", "proposed", "proposed_registry_invalid")
		decision.finalize()
		return decision, mutationError("REGISTRY_MUTATION_INVALID", "caller", false, fmt.Errorf("proposed registry is invalid: %w", err))
	}
	if fingerprint, err := current.Fingerprint(); err == nil {
		decision.PreviousFingerprint = fingerprint
	}
	if fingerprint, err := proposed.Fingerprint(); err == nil {
		decision.ProposedFingerprint = fingerprint
	}

	validateProjectPartitionProjects(&decision, current.Projects, proposed.Projects, projectID)
	validateProjectPartitionAPIKeys(&decision, current.APIKeys, proposed.APIKeys, projectID)
	validateProjectPartitionCredentials(&decision, current.CredentialMetadata, proposed.CredentialMetadata, projectID)
	validateProjectPartitionProviders(&decision, current.Providers, proposed.Providers, projectID)
	validateProjectPartitionCapabilities(&decision, current.Capabilities, proposed.Capabilities)
	validateProjectPartitionGlobalObjects(&decision, current, proposed)

	decision.finalize()
	if !decision.Allowed {
		return decision, mutationError("REGISTRY_PARTITION_VIOLATION", "caller", false, fmt.Errorf("registry mutation changes objects outside project partition %q", projectID))
	}
	return decision, nil
}

func validateProjectPartitionProjects(decision *ProjectPartitionMutationDecision, current []Project, proposed []Project, projectID string) {
	currentByID := map[string]Project{}
	proposedByID := map[string]Project{}
	for _, item := range current {
		currentByID[item.ID] = item
	}
	for _, item := range proposed {
		proposedByID[item.ID] = item
	}
	for _, id := range unionKeys(currentByID, proposedByID) {
		before, beforeOK := currentByID[id]
		after, afterOK := proposedByID[id]
		if beforeOK && afterOK && reflect.DeepEqual(before, after) {
			continue
		}
		if id != projectID {
			decision.addViolation("project", id, "cross_project_change")
			continue
		}
		if !beforeOK {
			decision.addViolation("project", id, "project_create_not_allowed")
			continue
		}
		if !afterOK {
			decision.addViolation("project", id, "project_delete_not_allowed")
			continue
		}
		decision.Counts.ProjectsChanged++
	}
}

func validateProjectPartitionAPIKeys(decision *ProjectPartitionMutationDecision, current []APIKey, proposed []APIKey, projectID string) {
	currentByID := map[string]APIKey{}
	proposedByID := map[string]APIKey{}
	for _, item := range current {
		currentByID[item.ID] = item
	}
	for _, item := range proposed {
		proposedByID[item.ID] = item
	}
	for _, id := range unionKeys(currentByID, proposedByID) {
		before, beforeOK := currentByID[id]
		after, afterOK := proposedByID[id]
		if beforeOK && afterOK && reflect.DeepEqual(before, after) {
			continue
		}
		if beforeOK && before.ProjectID != projectID {
			decision.addViolation("api_key", id, "cross_project_change")
			continue
		}
		if afterOK && after.ProjectID != projectID {
			reason := "cross_project_change"
			if beforeOK && before.ProjectID == projectID {
				reason = "ownership_transfer"
			}
			decision.addViolation("api_key", id, reason)
			continue
		}
		decision.Counts.APIKeysChanged++
	}
}

func validateProjectPartitionCredentials(decision *ProjectPartitionMutationDecision, current []CredentialMetadata, proposed []CredentialMetadata, projectID string) {
	currentByID := map[string]CredentialMetadata{}
	proposedByID := map[string]CredentialMetadata{}
	for _, item := range current {
		currentByID[item.CredentialID] = item
	}
	for _, item := range proposed {
		proposedByID[item.CredentialID] = item
	}
	for _, id := range unionKeys(currentByID, proposedByID) {
		before, beforeOK := currentByID[id]
		after, afterOK := proposedByID[id]
		if beforeOK && afterOK && reflect.DeepEqual(before, after) {
			continue
		}
		beforeOwned := beforeOK && credentialOwnedByProject(before, projectID)
		afterOwned := afterOK && credentialOwnedByProject(after, projectID)
		if beforeOK && afterOK && (before.OwnerType != after.OwnerType || before.OwnerID != after.OwnerID) {
			decision.addViolation("credential_metadata", id, "ownership_transfer")
			continue
		}
		if beforeOK && !beforeOwned {
			decision.addViolation("credential_metadata", id, "cross_project_or_platform_change")
			continue
		}
		if afterOK && !afterOwned {
			decision.addViolation("credential_metadata", id, "cross_project_or_platform_change")
			continue
		}
		decision.Counts.CredentialMetadataChanged++
	}
}

func validateProjectPartitionProviders(decision *ProjectPartitionMutationDecision, current []Provider, proposed []Provider, projectID string) {
	currentByID := map[string]Provider{}
	proposedByID := map[string]Provider{}
	for _, item := range current {
		currentByID[item.ID] = item
	}
	for _, item := range proposed {
		proposedByID[item.ID] = item
	}
	for _, id := range unionKeys(currentByID, proposedByID) {
		before, beforeOK := currentByID[id]
		after, afterOK := proposedByID[id]
		if beforeOK && afterOK && reflect.DeepEqual(before, after) {
			continue
		}
		beforeOwner := providerOwnerProjectID(before)
		afterOwner := providerOwnerProjectID(after)
		if beforeOK && afterOK && beforeOwner != afterOwner {
			decision.addViolation("provider", id, "ownership_transfer")
			continue
		}
		if beforeOK && beforeOwner == "" {
			decision.addViolation("provider", id, "platform_provider_change")
			continue
		}
		if afterOK && afterOwner == "" {
			decision.addViolation("provider", id, "platform_provider_change")
			continue
		}
		if beforeOK && beforeOwner != projectID {
			decision.addViolation("provider", id, "cross_project_change")
			continue
		}
		if afterOK && afterOwner != projectID {
			decision.addViolation("provider", id, "cross_project_change")
			continue
		}
		if beforeOK && afterOK && (before.CapabilityID != after.CapabilityID || before.CapabilityVersion != after.CapabilityVersion) {
			decision.addViolation("provider", id, "capability_reference_change")
			continue
		}
		decision.Counts.ProvidersChanged++
	}
}

func validateProjectPartitionCapabilities(decision *ProjectPartitionMutationDecision, current []Capability, proposed []Capability) {
	currentByID := map[string]Capability{}
	proposedByID := map[string]Capability{}
	for _, item := range current {
		currentByID[capabilityKey(item)] = item
	}
	for _, item := range proposed {
		proposedByID[capabilityKey(item)] = item
	}
	for _, id := range unionKeys(currentByID, proposedByID) {
		before, beforeOK := currentByID[id]
		after, afterOK := proposedByID[id]
		if beforeOK && afterOK && reflect.DeepEqual(before, after) {
			continue
		}
		decision.addViolation("capability", id, "global_capability_change")
	}
}

func validateProjectPartitionGlobalObjects(decision *ProjectPartitionMutationDecision, current Registry, proposed Registry) {
	if !reflect.DeepEqual(current.RoutingPolicy, proposed.RoutingPolicy) {
		decision.addViolation("routing_policy", "global", "global_routing_policy_change")
	}
	if !reflect.DeepEqual(current.Snapshot, proposed.Snapshot) {
		decision.SnapshotBoundaryChanged = true
		decision.addViolation("snapshot_config", "active", "global_snapshot_config_change")
	}
}

func credentialOwnedByProject(item CredentialMetadata, projectID string) bool {
	return item.OwnerType == "project" && item.OwnerID == projectID
}

func providerOwnerProjectID(item Provider) string {
	if item.Metadata == nil {
		return ""
	}
	return strings.TrimSpace(item.Metadata[providerOwnerProjectMetadataKey])
}

func capabilityKey(item Capability) string {
	return item.ID + "@" + item.Version
}

func unionKeys[T any](left map[string]T, right map[string]T) []string {
	keys := make([]string, 0, len(left)+len(right))
	seen := map[string]bool{}
	for key := range left {
		keys = append(keys, key)
		seen[key] = true
	}
	for key := range right {
		if !seen[key] {
			keys = append(keys, key)
		}
	}
	sort.Strings(keys)
	return keys
}

func (d *ProjectPartitionMutationDecision) addViolation(objectType string, objectID string, reason string) {
	d.Allowed = false
	d.Violations = append(d.Violations, ProjectPartitionMutationViolation{
		ObjectType: objectType,
		ObjectID:   objectID,
		Reason:     reason,
	})
	if d.RejectedCounts == nil {
		d.RejectedCounts = map[string]int{}
	}
	d.RejectedCounts[objectType]++
}

func (d *ProjectPartitionMutationDecision) finalize() {
	sort.Slice(d.Violations, func(i, j int) bool {
		if d.Violations[i].ObjectType == d.Violations[j].ObjectType {
			if d.Violations[i].ObjectID == d.Violations[j].ObjectID {
				return d.Violations[i].Reason < d.Violations[j].Reason
			}
			return d.Violations[i].ObjectID < d.Violations[j].ObjectID
		}
		return d.Violations[i].ObjectType < d.Violations[j].ObjectType
	})
	fingerprint, err := hashCanonicalJSON(map[string]any{
		"operation":                     d.Operation,
		"partition_project_id":          d.PartitionProjectID,
		"counts":                        d.Counts,
		"rejected_counts":               d.RejectedCounts,
		"violations":                    d.Violations,
		"proposed_registry_fingerprint": d.ProposedFingerprint,
		"previous_registry_fingerprint": d.PreviousFingerprint,
	})
	if err == nil {
		d.DiffFingerprint = fingerprint
	}
	if len(d.RejectedCounts) == 0 {
		d.RejectedCounts = nil
	}
}
