package registry

import (
	"fmt"
	"slices"
	"strings"
	"time"
)

type HostedPermissionPolicySubject struct {
	ID                 string `json:"id"`
	ExternalSubjectRef string `json:"external_subject_ref"`
	Status             string `json:"status"`
}

type HostedPermissionPolicyMembership struct {
	SubjectID      string `json:"subject_id"`
	ActorID        string `json:"actor_id"`
	ProjectID      string `json:"project_id"`
	OrganizationID string `json:"organization_id"`
	Status         string `json:"status"`
}

type HostedPermissionPolicyRole struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

type HostedPermissionPolicyRoleBinding struct {
	SubjectID      string `json:"subject_id"`
	ProjectID      string `json:"project_id"`
	OrganizationID string `json:"organization_id"`
	RoleID         string `json:"role_id"`
	Status         string `json:"status"`
}

type HostedPermissionPolicyGrant struct {
	RoleID     string `json:"role_id"`
	Permission string `json:"permission"`
	ScopeType  string `json:"scope_type"`
	Status     string `json:"status"`
}

type HostedPermissionPolicySnapshot struct {
	Subjects         []HostedPermissionPolicySubject     `json:"subjects"`
	Memberships      []HostedPermissionPolicyMembership  `json:"memberships"`
	Roles            []HostedPermissionPolicyRole        `json:"roles"`
	RoleBindings     []HostedPermissionPolicyRoleBinding `json:"role_bindings"`
	PermissionGrants []HostedPermissionPolicyGrant       `json:"permission_grants"`
}

type HostedPermissionPolicyVersion struct {
	Source      string `json:"source"`
	Version     string `json:"version"`
	Fingerprint string `json:"fingerprint"`
	Status      string `json:"status"`
}

type HostedPermissionPolicyMutationViolation struct {
	ObjectType string `json:"object_type"`
	ObjectID   string `json:"object_id"`
	Reason     string `json:"reason"`
}

type HostedPermissionPolicyValidation struct {
	Allowed           bool                                      `json:"allowed"`
	PolicyFingerprint string                                    `json:"policy_fingerprint"`
	Violations        []HostedPermissionPolicyMutationViolation `json:"violations,omitempty"`
}

type HostedPermissionPolicyDraft struct {
	ID          string
	BaseVersion string
	Version     string
	Status      string
	Snapshot    HostedPermissionPolicySnapshot
	ReviewedAt  time.Time
	CreatedAt   time.Time
}

type HostedPermissionPolicyMutationRequest struct {
	Operation           string
	ProjectID           string
	OrganizationID      string
	ActorID             string
	RequestID           string
	IdempotencyKey      string
	BasePolicyVersion   string
	DraftPolicyVersion  string
	TargetPolicyVersion string
}

type HostedPermissionPolicyMutationResult struct {
	Operation                 string    `json:"operation"`
	ProjectID                 string    `json:"project_id"`
	OrganizationID            string    `json:"organization_id"`
	ActorID                   string    `json:"actor_id"`
	RequestID                 string    `json:"request_id"`
	Replayed                  bool      `json:"replayed"`
	Allowed                   bool      `json:"allowed"`
	PolicySource              string    `json:"policy_source"`
	BasePolicyVersion         string    `json:"base_policy_version,omitempty"`
	DraftPolicyVersion        string    `json:"draft_policy_version,omitempty"`
	PreviousPolicyVersion     string    `json:"previous_policy_version,omitempty"`
	TargetPolicyVersion       string    `json:"target_policy_version,omitempty"`
	PolicyVersion             string    `json:"policy_version,omitempty"`
	PreviousPolicyFingerprint string    `json:"previous_policy_fingerprint,omitempty"`
	PolicyFingerprint         string    `json:"policy_fingerprint,omitempty"`
	IdempotencyKeyHash        string    `json:"idempotency_key_hash,omitempty"`
	IdempotencyKeyPrefix      string    `json:"idempotency_key_prefix,omitempty"`
	AuditEventID              int64     `json:"audit_event_id,omitempty"`
	ResolvedAt                time.Time `json:"resolved_at,omitempty"`
}

type HostedPermissionPolicyMutationAuditEvent struct {
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

type HostedPermissionPolicyMutationIdempotencyRecord struct {
	ID                  int64
	RequestFingerprint  string
	Status              string
	Result              HostedPermissionPolicyMutationResult
	ReplayCount         int64
	LastReplayRequestID string
}

type HostedPermissionPolicyMutationHarness struct {
	ProjectID         string
	OrganizationID    string
	PolicySource      string
	ActiveVersion     string
	ActiveFingerprint string
	ActiveSnapshot    HostedPermissionPolicySnapshot
	History           map[string]HostedPermissionPolicySnapshot
	Versions          map[string]HostedPermissionPolicyVersion
	Drafts            map[string]*HostedPermissionPolicyDraft
	Audits            []HostedPermissionPolicyMutationAuditEvent
	Idempotency       map[string]*HostedPermissionPolicyMutationIdempotencyRecord
	nextDraftSeq      int
	nextAuditID       int64
	nextVersionSeq    int
}

func NewHostedPermissionPolicyMutationHarness(projectID, organizationID, policySource string, activeVersion string, snapshot HostedPermissionPolicySnapshot) *HostedPermissionPolicyMutationHarness {
	canonical := canonicalHostedPermissionPolicySnapshot(snapshot)
	fingerprint, _ := hashCanonicalJSON(canonical)
	h := &HostedPermissionPolicyMutationHarness{
		ProjectID:         strings.TrimSpace(projectID),
		OrganizationID:    strings.TrimSpace(organizationID),
		PolicySource:      strings.TrimSpace(policySource),
		ActiveVersion:     strings.TrimSpace(activeVersion),
		ActiveFingerprint: fingerprint,
		ActiveSnapshot:    cloneHostedPermissionPolicySnapshot(canonical),
		History:           map[string]HostedPermissionPolicySnapshot{},
		Versions:          map[string]HostedPermissionPolicyVersion{},
		Drafts:            map[string]*HostedPermissionPolicyDraft{},
		Idempotency:       map[string]*HostedPermissionPolicyMutationIdempotencyRecord{},
	}
	if h.ActiveVersion != "" {
		h.History[h.ActiveVersion] = cloneHostedPermissionPolicySnapshot(canonical)
		h.Versions[h.ActiveVersion] = HostedPermissionPolicyVersion{
			Source:      h.PolicySource,
			Version:     h.ActiveVersion,
			Fingerprint: fingerprint,
			Status:      "active",
		}
	}
	return h
}

func (h *HostedPermissionPolicyMutationHarness) BeginDraft(baseVersion string, draftVersion string) (*HostedPermissionPolicyDraft, error) {
	if strings.TrimSpace(baseVersion) != h.ActiveVersion {
		return nil, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("draft base policy %q does not match active policy %q", baseVersion, h.ActiveVersion))
	}
	return h.beginDraftFromSnapshot(baseVersion, draftVersion, h.ActiveSnapshot), nil
}

func (h *HostedPermissionPolicyMutationHarness) BeginStaleDraftForContract(baseVersion string, draftVersion string) (*HostedPermissionPolicyDraft, error) {
	baseVersion = strings.TrimSpace(baseVersion)
	snapshot, ok := h.History[baseVersion]
	if !ok {
		return nil, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("stale draft base policy %q is unknown", baseVersion))
	}
	return h.beginDraftFromSnapshot(baseVersion, draftVersion, snapshot), nil
}

func (h *HostedPermissionPolicyMutationHarness) beginDraftFromSnapshot(baseVersion string, draftVersion string, snapshot HostedPermissionPolicySnapshot) *HostedPermissionPolicyDraft {
	baseVersion = strings.TrimSpace(baseVersion)
	draftVersion = strings.TrimSpace(draftVersion)
	if draftVersion == "" {
		draftVersion = fmt.Sprintf("%s-draft-%d", baseVersion, h.nextDraftSeq+1)
	}
	h.nextDraftSeq++
	draft := &HostedPermissionPolicyDraft{
		ID:          fmt.Sprintf("draft-%s-%d", h.PolicySource, h.nextDraftSeq),
		BaseVersion: baseVersion,
		Version:     draftVersion,
		Status:      "draft",
		Snapshot:    cloneHostedPermissionPolicySnapshot(snapshot),
		CreatedAt:   time.Now().UTC(),
	}
	h.Drafts[draft.ID] = draft
	h.audit("policy_mutation.begin_draft", "success", "", draft.ID, nil, map[string]string{
		"project_id":           h.ProjectID,
		"organization_id":      h.OrganizationID,
		"policy_source":        h.PolicySource,
		"base_policy_version":  draft.BaseVersion,
		"draft_policy_version": draft.Version,
	})
	return draft
}

func (h *HostedPermissionPolicyMutationHarness) RequestReview(draftID string) error {
	draft, err := h.draft(draftID)
	if err != nil {
		return err
	}
	if draft.Status != "draft" {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft %q is not open for review", draftID))
	}
	draft.Status = "review_requested"
	draft.ReviewedAt = time.Now().UTC()
	h.audit("policy_mutation.request_review", "success", "", draft.ID, nil, map[string]string{
		"project_id":           h.ProjectID,
		"organization_id":      h.OrganizationID,
		"policy_source":        h.PolicySource,
		"base_policy_version":  draft.BaseVersion,
		"draft_policy_version": draft.Version,
	})
	return nil
}

func (h *HostedPermissionPolicyMutationHarness) ValidateDraft(draftID string) (HostedPermissionPolicyValidation, error) {
	draft, err := h.draft(draftID)
	if err != nil {
		return HostedPermissionPolicyValidation{}, err
	}
	validation := validateHostedPermissionPolicySnapshot(draft.Snapshot, h.ProjectID, h.OrganizationID)
	if !validation.Allowed {
		return validation, hostedPermissionPolicyValidationError(validation)
	}
	return validation, nil
}

func (h *HostedPermissionPolicyMutationHarness) PromoteDraft(draftID string, req HostedPermissionPolicyMutationRequest) (HostedPermissionPolicyMutationResult, error) {
	draft, err := h.draft(draftID)
	if err != nil {
		return HostedPermissionPolicyMutationResult{}, err
	}
	if draft.Status != "review_requested" && draft.Status != "draft" {
		return HostedPermissionPolicyMutationResult{}, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft %q is not promotable", draftID))
	}
	req.Operation = "policy_mutation.promote"
	req.ProjectID = strings.TrimSpace(req.ProjectID)
	req.OrganizationID = strings.TrimSpace(req.OrganizationID)
	req.ActorID = strings.TrimSpace(req.ActorID)
	req.DraftPolicyVersion = draft.Version
	if strings.TrimSpace(req.BasePolicyVersion) == "" {
		req.BasePolicyVersion = draft.BaseVersion
	}
	mutationFingerprint, err := hashCanonicalJSON(canonicalHostedPermissionPolicySnapshot(draft.Snapshot))
	if err != nil {
		return HostedPermissionPolicyMutationResult{}, mutationError("POLICY_STATE_CONFLICT", "platform", true, fmt.Errorf("fingerprint draft snapshot: %w", err))
	}
	requestFingerprint, summary := hostedPermissionPolicyMutationRequestFingerprint(req, mutationFingerprint)
	record, replay, err := h.reserveMutation(req, requestFingerprint, summary)
	if err != nil || replay {
		if replay {
			replayed := record.Result
			replayed.Replayed = true
			replayed.RequestID = req.RequestID
			h.recordReplay(record, req.RequestID)
			return replayed, nil
		}
		return HostedPermissionPolicyMutationResult{}, err
	}
	if req.BasePolicyVersion != h.ActiveVersion {
		return HostedPermissionPolicyMutationResult{}, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("base policy %q is stale; active policy is %q", req.BasePolicyVersion, h.ActiveVersion))
	}
	validation := validateHostedPermissionPolicySnapshot(draft.Snapshot, h.ProjectID, h.OrganizationID)
	if !validation.Allowed {
		return HostedPermissionPolicyMutationResult{}, hostedPermissionPolicyValidationError(validation)
	}
	beforeVersion := h.ActiveVersion
	beforeFingerprint := h.ActiveFingerprint
	h.ActiveVersion = draft.Version
	h.ActiveFingerprint = validation.PolicyFingerprint
	h.ActiveSnapshot = cloneHostedPermissionPolicySnapshot(draft.Snapshot)
	h.History[h.ActiveVersion] = cloneHostedPermissionPolicySnapshot(h.ActiveSnapshot)
	h.Versions[beforeVersion] = HostedPermissionPolicyVersion{
		Source:      h.PolicySource,
		Version:     beforeVersion,
		Fingerprint: beforeFingerprint,
		Status:      "superseded",
	}
	h.Versions[h.ActiveVersion] = HostedPermissionPolicyVersion{
		Source:      h.PolicySource,
		Version:     h.ActiveVersion,
		Fingerprint: h.ActiveFingerprint,
		Status:      "active",
	}
	result := HostedPermissionPolicyMutationResult{
		Operation:                 req.Operation,
		ProjectID:                 h.ProjectID,
		OrganizationID:            h.OrganizationID,
		ActorID:                   req.ActorID,
		RequestID:                 req.RequestID,
		Allowed:                   true,
		PolicySource:              h.PolicySource,
		BasePolicyVersion:         beforeVersion,
		DraftPolicyVersion:        draft.Version,
		PreviousPolicyVersion:     beforeVersion,
		PolicyVersion:             h.ActiveVersion,
		PreviousPolicyFingerprint: beforeFingerprint,
		PolicyFingerprint:         h.ActiveFingerprint,
		IdempotencyKeyHash:        mutationIdempotencyKeyHash(req.IdempotencyKey),
		IdempotencyKeyPrefix:      mutationIdempotencyKeyPrefix(req.IdempotencyKey),
		ResolvedAt:                time.Now().UTC(),
	}
	auditID := h.audit("policy_mutation.promote", "success", "", draft.ID, nil, map[string]string{
		"actor_id":                    req.ActorID,
		"request_id":                  req.RequestID,
		"project_id":                  h.ProjectID,
		"organization_id":             h.OrganizationID,
		"policy_source":               h.PolicySource,
		"base_policy_version":         beforeVersion,
		"draft_policy_version":        draft.Version,
		"previous_policy_version":     beforeVersion,
		"policy_version":              h.ActiveVersion,
		"previous_policy_fingerprint": beforeFingerprint,
		"policy_fingerprint":          h.ActiveFingerprint,
		"mutation_fingerprint":        mutationFingerprint,
		"idempotency_key_hash":        result.IdempotencyKeyHash,
		"idempotency_key_prefix":      result.IdempotencyKeyPrefix,
	})
	result.AuditEventID = auditID
	if err := h.completeMutation(record, result); err != nil {
		return HostedPermissionPolicyMutationResult{}, err
	}
	return result, nil
}

func (h *HostedPermissionPolicyMutationHarness) RollbackPolicy(targetVersion string, req HostedPermissionPolicyMutationRequest) (HostedPermissionPolicyMutationResult, error) {
	targetVersion = strings.TrimSpace(targetVersion)
	baseSnapshot, ok := h.History[targetVersion]
	if !ok {
		return HostedPermissionPolicyMutationResult{}, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("rollback target policy %q is unknown", targetVersion))
	}
	req.Operation = "policy_mutation.rollback"
	req.ProjectID = strings.TrimSpace(req.ProjectID)
	req.OrganizationID = strings.TrimSpace(req.OrganizationID)
	req.ActorID = strings.TrimSpace(req.ActorID)
	req.TargetPolicyVersion = targetVersion
	mutationFingerprint, err := hashCanonicalJSON(canonicalHostedPermissionPolicySnapshot(baseSnapshot))
	if err != nil {
		return HostedPermissionPolicyMutationResult{}, mutationError("POLICY_STATE_CONFLICT", "platform", true, fmt.Errorf("fingerprint rollback snapshot: %w", err))
	}
	requestFingerprint, summary := hostedPermissionPolicyMutationRequestFingerprint(req, mutationFingerprint)
	record, replay, err := h.reserveMutation(req, requestFingerprint, summary)
	if err != nil || replay {
		if replay {
			replayed := record.Result
			replayed.Replayed = true
			replayed.RequestID = req.RequestID
			h.recordReplay(record, req.RequestID)
			return replayed, nil
		}
		return HostedPermissionPolicyMutationResult{}, err
	}
	newVersion := h.nextRollbackVersion(targetVersion)
	beforeVersion := h.ActiveVersion
	beforeFingerprint := h.ActiveFingerprint
	h.ActiveVersion = newVersion
	h.ActiveFingerprint = mutationFingerprint
	h.ActiveSnapshot = cloneHostedPermissionPolicySnapshot(baseSnapshot)
	h.History[h.ActiveVersion] = cloneHostedPermissionPolicySnapshot(h.ActiveSnapshot)
	h.Versions[beforeVersion] = HostedPermissionPolicyVersion{
		Source:      h.PolicySource,
		Version:     beforeVersion,
		Fingerprint: beforeFingerprint,
		Status:      "superseded",
	}
	h.Versions[h.ActiveVersion] = HostedPermissionPolicyVersion{
		Source:      h.PolicySource,
		Version:     h.ActiveVersion,
		Fingerprint: h.ActiveFingerprint,
		Status:      "active",
	}
	result := HostedPermissionPolicyMutationResult{
		Operation:                 req.Operation,
		ProjectID:                 h.ProjectID,
		OrganizationID:            h.OrganizationID,
		ActorID:                   req.ActorID,
		RequestID:                 req.RequestID,
		Allowed:                   true,
		PolicySource:              h.PolicySource,
		BasePolicyVersion:         beforeVersion,
		TargetPolicyVersion:       targetVersion,
		PreviousPolicyVersion:     beforeVersion,
		PolicyVersion:             h.ActiveVersion,
		PreviousPolicyFingerprint: beforeFingerprint,
		PolicyFingerprint:         h.ActiveFingerprint,
		IdempotencyKeyHash:        mutationIdempotencyKeyHash(req.IdempotencyKey),
		IdempotencyKeyPrefix:      mutationIdempotencyKeyPrefix(req.IdempotencyKey),
		ResolvedAt:                time.Now().UTC(),
	}
	auditID := h.audit("policy_mutation.rollback", "success", "", h.ActiveVersion, nil, map[string]string{
		"actor_id":                    req.ActorID,
		"request_id":                  req.RequestID,
		"project_id":                  h.ProjectID,
		"organization_id":             h.OrganizationID,
		"policy_source":               h.PolicySource,
		"base_policy_version":         beforeVersion,
		"target_policy_version":       targetVersion,
		"policy_version":              h.ActiveVersion,
		"policy_fingerprint":          h.ActiveFingerprint,
		"previous_policy_version":     beforeVersion,
		"previous_policy_fingerprint": beforeFingerprint,
		"mutation_fingerprint":        mutationFingerprint,
		"idempotency_key_hash":        result.IdempotencyKeyHash,
		"idempotency_key_prefix":      result.IdempotencyKeyPrefix,
	})
	result.AuditEventID = auditID
	if err := h.completeMutation(record, result); err != nil {
		return HostedPermissionPolicyMutationResult{}, err
	}
	return result, nil
}

func (h *HostedPermissionPolicyMutationHarness) ResolvePermission(externalSubjectRef, requiredPermission string, resolvedAt time.Time) HostedPermissionDecision {
	resolvedAt = resolvedAt.UTC()
	if resolvedAt.IsZero() {
		resolvedAt = time.Now().UTC()
	}
	policy := hostedPermissionPolicyVersion{
		Source:      h.PolicySource,
		Version:     h.ActiveVersion,
		Fingerprint: h.ActiveFingerprint,
	}
	subject, ok := h.findSubjectByExternalRef(externalSubjectRef)
	if !ok || subject.Status != "active" {
		decision := hostedDeniedDecision(HostedPermissionLookupRequest{
			PublicPrincipalID:  externalSubjectRef,
			ExternalSubjectRef: externalSubjectRef,
			ProjectID:          h.ProjectID,
			RequiredPermission: requiredPermission,
			ResolvedAt:         resolvedAt,
		}, policy, HostedPermissionDecisionDenied, HostedPermissionErrorPublicAuthzDenied, HostedPermissionDenySubjectInactive)
		if ok {
			decision.SubjectID = subject.ID
			decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
		}
		return decision
	}
	membership, ok := h.findActiveMembership(subject.ID)
	if !ok {
		decision := hostedDeniedDecision(HostedPermissionLookupRequest{
			PublicPrincipalID:  externalSubjectRef,
			ExternalSubjectRef: externalSubjectRef,
			ProjectID:          h.ProjectID,
			RequiredPermission: requiredPermission,
			ResolvedAt:         resolvedAt,
		}, policy, HostedPermissionDecisionDenied, HostedPermissionErrorPublicAuthzDenied, HostedPermissionDenyMissingMembership)
		decision.SubjectID = subject.ID
		decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
		return decision
	}
	if membership.Status != "active" {
		decision := hostedDeniedDecision(HostedPermissionLookupRequest{
			PublicPrincipalID:  externalSubjectRef,
			ExternalSubjectRef: externalSubjectRef,
			ProjectID:          h.ProjectID,
			RequiredPermission: requiredPermission,
			ResolvedAt:         resolvedAt,
		}, policy, HostedPermissionDecisionDenied, HostedPermissionErrorPublicAuthzDenied, HostedPermissionDenyMembershipInactive)
		decision.SubjectID = subject.ID
		decision.ActorID = membership.ActorID
		decision.ProjectID = membership.ProjectID
		decision.OrganizationID = membership.OrganizationID
		decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
		return decision
	}
	roles := h.activeRoleIDs(subject.ID, membership.ProjectID, membership.OrganizationID)
	permissions := h.activePermissions(subject.ID, membership.ProjectID, membership.OrganizationID)
	decision := HostedPermissionDecision{
		Allowed:            slices.Contains(permissions, requiredPermission),
		Status:             HostedPermissionDecisionAllowed,
		SubjectID:          subject.ID,
		ActorID:            membership.ActorID,
		ProjectID:          membership.ProjectID,
		OrganizationID:     membership.OrganizationID,
		Roles:              roles,
		Permissions:        permissions,
		RequiredPermission: requiredPermission,
		PolicySource:       policy.Source,
		PolicyVersion:      policy.Version,
		PolicyFingerprint:  policy.Fingerprint,
		PermissionSource:   policy.Source,
		ResolvedAt:         resolvedAt,
	}
	if !decision.Allowed {
		decision.Status = HostedPermissionDecisionDenied
		decision.ErrorType = HostedPermissionErrorPublicAuthzDenied
		decision.DenyReason = HostedPermissionDenyMissingEndpointPermission
	}
	decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
	return decision
}

func (h *HostedPermissionPolicyMutationHarness) audit(action string, outcome string, errorType string, resourceID string, result *HostedPermissionPolicyMutationResult, metadata map[string]string) int64 {
	h.nextAuditID++
	event := HostedPermissionPolicyMutationAuditEvent{
		ID:           h.nextAuditID,
		ActorID:      metadata["actor_id"],
		Action:       action,
		ResourceType: "hosted_permission_policy",
		ResourceID:   resourceID,
		RequestID:    metadata["request_id"],
		Outcome:      outcome,
		ErrorType:    errorType,
		Metadata:     map[string]string{},
	}
	for key, value := range metadata {
		if value != "" {
			event.Metadata[key] = value
		}
	}
	if result != nil {
		result.AuditEventID = event.ID
	}
	h.Audits = append(h.Audits, event)
	return event.ID
}

func (h *HostedPermissionPolicyMutationHarness) draft(draftID string) (*HostedPermissionPolicyDraft, error) {
	draft, ok := h.Drafts[draftID]
	if !ok {
		return nil, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft %q does not exist", draftID))
	}
	return draft, nil
}

func (h *HostedPermissionPolicyMutationHarness) reserveMutation(req HostedPermissionPolicyMutationRequest, requestFingerprint string, summary map[string]string) (*HostedPermissionPolicyMutationIdempotencyRecord, bool, error) {
	key := hostedPermissionPolicyMutationScope(req)
	if key == "" {
		return nil, false, nil
	}
	if record, ok := h.Idempotency[key]; ok {
		if record.RequestFingerprint != requestFingerprint {
			return nil, false, mutationError("IDEMPOTENCY_KEY_CONFLICT", "caller", false, fmt.Errorf("idempotency key was already used for a different request"))
		}
		if record.Status != "succeeded" {
			return nil, false, mutationError("IDEMPOTENCY_REQUEST_IN_PROGRESS", "platform", true, fmt.Errorf("idempotency request is still in progress"))
		}
		return record, true, nil
	}
	record := &HostedPermissionPolicyMutationIdempotencyRecord{
		ID:                 int64(len(h.Idempotency) + 1),
		RequestFingerprint: requestFingerprint,
		Status:             "processing",
	}
	h.Idempotency[key] = record
	if summary != nil {
		record.Result.ProjectID = summary["project_id"]
		record.Result.OrganizationID = summary["organization_id"]
		record.Result.ActorID = summary["actor_id"]
		record.Result.RequestID = summary["request_id"]
		record.Result.PolicySource = summary["policy_source"]
		record.Result.BasePolicyVersion = summary["base_policy_version"]
		record.Result.DraftPolicyVersion = summary["draft_policy_version"]
		record.Result.PreviousPolicyVersion = summary["previous_policy_version"]
		record.Result.PolicyVersion = summary["policy_version"]
	}
	return record, false, nil
}

func (h *HostedPermissionPolicyMutationHarness) recordReplay(record *HostedPermissionPolicyMutationIdempotencyRecord, requestID string) {
	if record == nil {
		return
	}
	record.ReplayCount++
	record.LastReplayRequestID = requestID
}

func (h *HostedPermissionPolicyMutationHarness) completeMutation(record *HostedPermissionPolicyMutationIdempotencyRecord, result HostedPermissionPolicyMutationResult) error {
	if record == nil {
		return nil
	}
	record.Status = "succeeded"
	record.Result = result
	return nil
}

func (h *HostedPermissionPolicyMutationHarness) nextRollbackVersion(targetVersion string) string {
	h.nextVersionSeq++
	return fmt.Sprintf("%s-rollback-%d", targetVersion, h.nextVersionSeq)
}

func (h *HostedPermissionPolicyMutationHarness) findSubjectByExternalRef(externalRef string) (HostedPermissionPolicySubject, bool) {
	for _, subject := range h.ActiveSnapshot.Subjects {
		if subject.ExternalSubjectRef == externalRef {
			return subject, true
		}
	}
	return HostedPermissionPolicySubject{}, false
}

func (h *HostedPermissionPolicyMutationHarness) findActiveMembership(subjectID string) (HostedPermissionPolicyMembership, bool) {
	for _, membership := range h.ActiveSnapshot.Memberships {
		if membership.SubjectID == subjectID && membership.ProjectID == h.ProjectID && membership.OrganizationID == h.OrganizationID && membership.Status == "active" {
			return membership, true
		}
	}
	return HostedPermissionPolicyMembership{}, false
}

func (h *HostedPermissionPolicyMutationHarness) activeRoleIDs(subjectID, projectID, organizationID string) []string {
	roleStatus := map[string]string{}
	for _, role := range h.ActiveSnapshot.Roles {
		roleStatus[role.ID] = role.Status
	}
	var out []string
	for _, binding := range h.ActiveSnapshot.RoleBindings {
		if binding.SubjectID == subjectID && binding.ProjectID == projectID && binding.OrganizationID == organizationID && binding.Status == "active" && roleStatus[binding.RoleID] == "active" {
			out = append(out, binding.RoleID)
		}
	}
	slices.Sort(out)
	return out
}

func (h *HostedPermissionPolicyMutationHarness) activePermissions(subjectID, projectID, organizationID string) []string {
	activeRoles := map[string]bool{}
	for _, roleID := range h.activeRoleIDs(subjectID, projectID, organizationID) {
		activeRoles[roleID] = true
	}
	permissions := map[string]bool{}
	for _, grant := range h.ActiveSnapshot.PermissionGrants {
		if grant.Status == "active" && activeRoles[grant.RoleID] {
			permissions[grant.Permission] = true
		}
	}
	out := make([]string, 0, len(permissions))
	for permission := range permissions {
		out = append(out, permission)
	}
	slices.Sort(out)
	return out
}

type HostedPermissionPolicyMutationDogfoodReport struct {
	Status                          string `json:"status"`
	PolicySource                    string `json:"policy_source"`
	ProjectID                       string `json:"project_id"`
	OrganizationID                  string `json:"organization_id"`
	ActiveVersionBefore             string `json:"active_version_before"`
	ActiveFingerprintBefore         string `json:"active_fingerprint_before"`
	DraftValidationStatus           string `json:"draft_validation_status"`
	PromotionStatus                 string `json:"promotion_status"`
	PromotionReplayed               bool   `json:"promotion_replayed"`
	ActiveVersionAfterPromotion     string `json:"active_version_after_promotion"`
	ActiveFingerprintAfterPromotion string `json:"active_fingerprint_after_promotion"`
	IdempotencyReplayCount          int    `json:"idempotency_replay_count"`
	IdempotencyConflictStatus       string `json:"idempotency_conflict_status"`
	ScopeViolationStatus            string `json:"scope_violation_status"`
	StaleBaseConflictStatus         string `json:"stale_base_conflict_status"`
	RollbackStatus                  string `json:"rollback_status"`
	ActiveVersionAfterRollback      string `json:"active_version_after_rollback"`
	ActiveFingerprintAfterRollback  string `json:"active_fingerprint_after_rollback"`
	GatewayDecisionBeforePromotion  string `json:"gateway_decision_before_promotion"`
	GatewayDecisionAfterPromotion   string `json:"gateway_decision_after_promotion"`
	GatewayDecisionAfterRollback    string `json:"gateway_decision_after_rollback"`
	AuditRows                       int    `json:"audit_rows"`
	AuditContainsRawIdempotencyKey  bool   `json:"audit_contains_raw_idempotency_key"`
	AuditContainsRawToken           bool   `json:"audit_contains_raw_token"`
	AuditContainsGatewaySecret      bool   `json:"audit_contains_gateway_secret"`
}

func RunHostedPermissionPolicyMutationBoundaryDogfood() HostedPermissionPolicyMutationDogfoodReport {
	const (
		projectID      = "policy-mutation-project"
		organizationID = "policy-mutation-org"
		policySource   = "hosted-permission-policy-store-fixture"
		baseVersion    = "hosted-permission-policy-v1"
		draftVersion   = "hosted-permission-policy-v2"
	)
	base := HostedPermissionPolicySnapshot{
		Subjects: []HostedPermissionPolicySubject{
			{ID: "subject-policy-admin", ExternalSubjectRef: "dogfood/idp/admin", Status: "active"},
		},
		Memberships: []HostedPermissionPolicyMembership{
			{SubjectID: "subject-policy-admin", ActorID: "actor-policy-admin", ProjectID: projectID, OrganizationID: organizationID, Status: "active"},
		},
		Roles: []HostedPermissionPolicyRole{
			{ID: "policy-admin", Status: "active"},
		},
		RoleBindings: []HostedPermissionPolicyRoleBinding{
			{SubjectID: "subject-policy-admin", ProjectID: projectID, OrganizationID: organizationID, RoleID: "policy-admin", Status: "active"},
		},
		PermissionGrants: []HostedPermissionPolicyGrant{
			{RoleID: "policy-admin", Permission: "control_plane.permission_policy.validate", ScopeType: "project", Status: "active"},
		},
	}
	h := NewHostedPermissionPolicyMutationHarness(projectID, organizationID, policySource, baseVersion, base)
	before := h.ResolvePermission("dogfood/idp/admin", "control_plane.permission_policy.promote", time.Date(2026, 6, 2, 0, 0, 0, 0, time.UTC))
	draft, _ := h.BeginDraft(baseVersion, draftVersion)
	draft.UpsertGrant(HostedPermissionPolicyGrant{
		RoleID:     "policy-admin",
		Permission: "control_plane.permission_policy.promote",
		ScopeType:  "project",
		Status:     "active",
	})
	validation, validationErr := h.ValidateDraft(draft.ID)
	report := HostedPermissionPolicyMutationDogfoodReport{
		Status:                         "failed",
		PolicySource:                   policySource,
		ProjectID:                      projectID,
		OrganizationID:                 organizationID,
		ActiveVersionBefore:            h.ActiveVersion,
		ActiveFingerprintBefore:        h.ActiveFingerprint,
		DraftValidationStatus:          "failed",
		GatewayDecisionBeforePromotion: hostedDecisionStatus(before),
	}
	if validationErr == nil && validation.Allowed {
		report.DraftValidationStatus = "passed"
	}
	_ = h.RequestReview(draft.ID)
	promoteResult, promoteErr := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          projectID,
		OrganizationID:     organizationID,
		ActorID:            "actor-policy-admin",
		RequestID:          "policy-promote-1",
		IdempotencyKey:     "policy-promote-key",
		BasePolicyVersion:  baseVersion,
		DraftPolicyVersion: draftVersion,
	})
	if promoteErr == nil {
		report.PromotionStatus = "passed"
		report.PromotionReplayed = promoteResult.Replayed
		report.ActiveVersionAfterPromotion = h.ActiveVersion
		report.ActiveFingerprintAfterPromotion = h.ActiveFingerprint
	}
	replayed, replayErr := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          projectID,
		OrganizationID:     organizationID,
		ActorID:            "actor-policy-admin",
		RequestID:          "policy-promote-2",
		IdempotencyKey:     "policy-promote-key",
		BasePolicyVersion:  baseVersion,
		DraftPolicyVersion: draftVersion,
	})
	if replayErr == nil && replayed.Replayed {
		report.IdempotencyReplayCount = 1
	}
	_, conflictErr := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:           projectID,
		OrganizationID:      organizationID,
		ActorID:             "actor-policy-admin",
		RequestID:           "policy-promote-3",
		IdempotencyKey:      "policy-promote-key",
		BasePolicyVersion:   baseVersion,
		TargetPolicyVersion: "different-target",
	})
	report.IdempotencyConflictStatus = mutationErrorType(conflictErr)
	report.StaleBaseConflictStatus = mutationErrorType(func() error {
		staleDraft, _ := h.BeginStaleDraftForContract(baseVersion, "hosted-permission-policy-v3")
		_, err := h.PromoteDraft(staleDraft.ID, HostedPermissionPolicyMutationRequest{
			ProjectID:          projectID,
			OrganizationID:     organizationID,
			ActorID:            "actor-policy-admin",
			RequestID:          "policy-promote-stale",
			IdempotencyKey:     "policy-promote-stale",
			BasePolicyVersion:  baseVersion,
			DraftPolicyVersion: "hosted-permission-policy-v3",
		})
		return err
	}())
	afterPromote := h.ResolvePermission("dogfood/idp/admin", "control_plane.permission_policy.promote", time.Date(2026, 6, 2, 0, 0, 0, 0, time.UTC))
	report.GatewayDecisionAfterPromotion = hostedDecisionStatus(afterPromote)
	rollbackResult, rollbackErr := h.RollbackPolicy(baseVersion, HostedPermissionPolicyMutationRequest{
		ProjectID:           projectID,
		OrganizationID:      organizationID,
		ActorID:             "actor-policy-admin",
		RequestID:           "policy-rollback-1",
		IdempotencyKey:      "policy-rollback-key",
		BasePolicyVersion:   h.ActiveVersion,
		TargetPolicyVersion: baseVersion,
	})
	if rollbackErr == nil {
		report.RollbackStatus = "passed"
		report.ActiveVersionAfterRollback = h.ActiveVersion
		report.ActiveFingerprintAfterRollback = h.ActiveFingerprint
		_ = rollbackResult
	}
	afterRollback := h.ResolvePermission("dogfood/idp/admin", "control_plane.permission_policy.promote", time.Date(2026, 6, 2, 0, 0, 0, 0, time.UTC))
	report.GatewayDecisionAfterRollback = hostedDecisionStatus(afterRollback)
	scopeDraft, _ := h.BeginDraft(h.ActiveVersion, "hosted-permission-policy-v4")
	scopeDraft.UpsertGrant(HostedPermissionPolicyGrant{
		RoleID:     "policy-admin",
		Permission: "control_plane.permission_policy.rollback",
		ScopeType:  "platform",
		Status:     "active",
	})
	scopeValidation, scopeValidationErr := h.ValidateDraft(scopeDraft.ID)
	if scopeValidationErr != nil || !scopeValidation.Allowed {
		report.ScopeViolationStatus = mutationErrorType(scopeValidationErr)
		if report.ScopeViolationStatus == "" && len(scopeValidation.Violations) > 0 {
			report.ScopeViolationStatus = scopeValidation.Violations[0].Reason
		}
	}
	report.AuditRows = len(h.Audits)
	for _, audit := range h.Audits {
		if containsSecretLikeValue(audit.Metadata, "raw-idempotency-key") {
			report.AuditContainsRawIdempotencyKey = true
		}
		if containsSecretLikeValue(audit.Metadata, "raw-token") {
			report.AuditContainsRawToken = true
		}
		if containsSecretLikeValue(audit.Metadata, "gateway-secret") {
			report.AuditContainsGatewaySecret = true
		}
	}
	report.Status = "passed"
	if report.DraftValidationStatus != "passed" || report.PromotionStatus != "passed" || report.RollbackStatus != "passed" || report.GatewayDecisionAfterPromotion != "allowed" || report.GatewayDecisionAfterRollback != "denied" {
		report.Status = "failed"
	}
	return report
}

func hostedDecisionStatus(decision HostedPermissionDecision) string {
	if decision.Allowed {
		return "allowed"
	}
	if decision.Status == HostedPermissionDecisionSourceUnavailable {
		return "source_unavailable"
	}
	return "denied"
}

func hostedPermissionPolicyMutationRequestFingerprint(req HostedPermissionPolicyMutationRequest, mutationFingerprint string) (string, map[string]string) {
	summary := map[string]string{
		"version":               "hosted-permission-policy-mutation-v0",
		"operation":             req.Operation,
		"policy_source":         "hosted_permission_store",
		"project_id":            strings.TrimSpace(req.ProjectID),
		"organization_id":       strings.TrimSpace(req.OrganizationID),
		"actor_id":              strings.TrimSpace(req.ActorID),
		"base_policy_version":   strings.TrimSpace(req.BasePolicyVersion),
		"draft_policy_version":  strings.TrimSpace(req.DraftPolicyVersion),
		"target_policy_version": strings.TrimSpace(req.TargetPolicyVersion),
		"mutation_fingerprint":  mutationFingerprint,
		"source":                "hosted_permission_policy_mutation_contract_harness",
		"dry_run":               "false",
	}
	fingerprint, _ := hashCanonicalJSON(summary)
	return fingerprint, summary
}

func hostedPermissionPolicyMutationScope(req HostedPermissionPolicyMutationRequest) string {
	projectID := strings.TrimSpace(req.ProjectID)
	actorID := strings.TrimSpace(req.ActorID)
	keyHash := mutationIdempotencyKeyHash(req.IdempotencyKey)
	if keyHash == "" {
		return ""
	}
	return strings.Join([]string{projectID, actorID, req.Operation, keyHash}, "|")
}

func mutationIdempotencyKeyHash(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return ""
	}
	return hashString(value)
}

func mutationIdempotencyKeyPrefix(value string) string {
	keyHash := mutationIdempotencyKeyHash(value)
	if keyHash == "" {
		return ""
	}
	if len(keyHash) > len("sha256:")+12 {
		return keyHash[:len("sha256:")+12]
	}
	return keyHash
}

func mutationErrorType(err error) string {
	if err == nil {
		return ""
	}
	if mutationErr, ok := err.(RegistryMutationError); ok {
		return mutationErr.ErrorType
	}
	return ""
}

func containsSecretLikeValue(metadata map[string]string, needle string) bool {
	for _, value := range metadata {
		if strings.Contains(strings.ToLower(value), strings.ToLower(needle)) {
			return true
		}
	}
	return false
}

func validateHostedPermissionPolicySnapshot(snapshot HostedPermissionPolicySnapshot, projectID string, organizationID string) HostedPermissionPolicyValidation {
	canonical := canonicalHostedPermissionPolicySnapshot(snapshot)
	fingerprint, _ := hashCanonicalJSON(canonical)
	validation := HostedPermissionPolicyValidation{
		Allowed:           true,
		PolicyFingerprint: fingerprint,
	}
	seenSubject := map[string]bool{}
	seenMembership := map[string]bool{}
	seenRole := map[string]bool{}
	seenBinding := map[string]bool{}
	seenGrant := map[string]bool{}
	for _, subject := range canonical.Subjects {
		if subject.ID == "" {
			validation.addViolation("subject", "", "invalid_status_transition")
			continue
		}
		if seenSubject[subject.ID] {
			validation.addViolation("subject", subject.ID, "duplicate_active_subject")
			continue
		}
		seenSubject[subject.ID] = true
		if !isValidHostedPermissionSubjectStatus(subject.Status) {
			validation.addViolation("subject", subject.ID, "invalid_status_transition")
		}
	}
	for _, membership := range canonical.Memberships {
		key := strings.Join([]string{membership.SubjectID, membership.ProjectID, membership.OrganizationID}, "|")
		if seenMembership[key] && membership.Status == "active" {
			validation.addViolation("membership", key, "duplicate_active_membership")
			continue
		}
		if membership.ProjectID != projectID || membership.OrganizationID != organizationID {
			validation.addViolation("membership", key, "scope_escape")
		}
		if !isValidHostedPermissionMembershipStatus(membership.Status) {
			validation.addViolation("membership", key, "invalid_status_transition")
		}
		if membership.Status == "active" {
			seenMembership[key] = true
		}
	}
	for _, role := range canonical.Roles {
		if seenRole[role.ID] {
			validation.addViolation("role", role.ID, "duplicate_active_role")
			continue
		}
		seenRole[role.ID] = true
		if !isValidHostedPermissionRoleStatus(role.Status) {
			validation.addViolation("role", role.ID, "invalid_status_transition")
		}
	}
	for _, binding := range canonical.RoleBindings {
		key := strings.Join([]string{binding.SubjectID, binding.ProjectID, binding.OrganizationID, binding.RoleID}, "|")
		if binding.ProjectID != projectID || binding.OrganizationID != organizationID {
			validation.addViolation("role_binding", key, "scope_escape")
		}
		if !isValidHostedPermissionBindingStatus(binding.Status) {
			validation.addViolation("role_binding", key, "invalid_status_transition")
		}
		if binding.Status == "active" {
			if seenBinding[key] {
				validation.addViolation("role_binding", key, "duplicate_active_role_binding")
				continue
			}
			seenBinding[key] = true
		}
	}
	for _, grant := range canonical.PermissionGrants {
		key := strings.Join([]string{grant.RoleID, grant.Permission, grant.ScopeType}, "|")
		if grant.ScopeType == "platform" {
			validation.addViolation("permission_grant", key, "scope_escape")
		}
		if !isValidHostedPermissionGrantStatus(grant.Status) {
			validation.addViolation("permission_grant", key, "invalid_status_transition")
		}
		if grant.Status == "active" {
			if seenGrant[key] {
				validation.addViolation("permission_grant", key, "duplicate_active_permission_grant")
				continue
			}
			seenGrant[key] = true
		}
	}
	return validation
}

func (v *HostedPermissionPolicyValidation) addViolation(objectType, objectID, reason string) {
	v.Allowed = false
	v.Violations = append(v.Violations, HostedPermissionPolicyMutationViolation{
		ObjectType: objectType,
		ObjectID:   objectID,
		Reason:     reason,
	})
}

func hostedPermissionPolicyValidationError(validation HostedPermissionPolicyValidation) error {
	for _, violation := range validation.Violations {
		switch violation.Reason {
		case "scope_escape":
			return mutationError("POLICY_SCOPE_VIOLATION", "caller", false, fmt.Errorf("%s %s escapes policy scope", violation.ObjectType, violation.ObjectID))
		case "duplicate_active_role_binding":
			return mutationError("POLICY_BINDING_CONFLICT", "caller", false, fmt.Errorf("duplicate active role binding %s", violation.ObjectID))
		case "duplicate_active_permission_grant":
			return mutationError("POLICY_GRANT_CONFLICT", "caller", false, fmt.Errorf("duplicate active permission grant %s", violation.ObjectID))
		case "invalid_status_transition":
			return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("invalid status transition for %s %s", violation.ObjectType, violation.ObjectID))
		}
	}
	return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("policy validation failed"))
}

func canonicalHostedPermissionPolicySnapshot(snapshot HostedPermissionPolicySnapshot) HostedPermissionPolicySnapshot {
	canonical := cloneHostedPermissionPolicySnapshot(snapshot)
	slices.SortFunc(canonical.Subjects, func(left, right HostedPermissionPolicySubject) int {
		if left.ID != right.ID {
			return strings.Compare(left.ID, right.ID)
		}
		return strings.Compare(left.ExternalSubjectRef, right.ExternalSubjectRef)
	})
	slices.SortFunc(canonical.Memberships, func(left, right HostedPermissionPolicyMembership) int {
		if left.SubjectID != right.SubjectID {
			return strings.Compare(left.SubjectID, right.SubjectID)
		}
		if left.ProjectID != right.ProjectID {
			return strings.Compare(left.ProjectID, right.ProjectID)
		}
		if left.OrganizationID != right.OrganizationID {
			return strings.Compare(left.OrganizationID, right.OrganizationID)
		}
		return strings.Compare(left.ActorID, right.ActorID)
	})
	slices.SortFunc(canonical.Roles, func(left, right HostedPermissionPolicyRole) int {
		return strings.Compare(left.ID, right.ID)
	})
	slices.SortFunc(canonical.RoleBindings, func(left, right HostedPermissionPolicyRoleBinding) int {
		if left.SubjectID != right.SubjectID {
			return strings.Compare(left.SubjectID, right.SubjectID)
		}
		if left.ProjectID != right.ProjectID {
			return strings.Compare(left.ProjectID, right.ProjectID)
		}
		if left.OrganizationID != right.OrganizationID {
			return strings.Compare(left.OrganizationID, right.OrganizationID)
		}
		return strings.Compare(left.RoleID, right.RoleID)
	})
	slices.SortFunc(canonical.PermissionGrants, func(left, right HostedPermissionPolicyGrant) int {
		if left.RoleID != right.RoleID {
			return strings.Compare(left.RoleID, right.RoleID)
		}
		if left.ScopeType != right.ScopeType {
			return strings.Compare(left.ScopeType, right.ScopeType)
		}
		return strings.Compare(left.Permission, right.Permission)
	})
	return canonical
}

func cloneHostedPermissionPolicySnapshot(snapshot HostedPermissionPolicySnapshot) HostedPermissionPolicySnapshot {
	cloned := HostedPermissionPolicySnapshot{
		Subjects:         append([]HostedPermissionPolicySubject(nil), snapshot.Subjects...),
		Memberships:      append([]HostedPermissionPolicyMembership(nil), snapshot.Memberships...),
		Roles:            append([]HostedPermissionPolicyRole(nil), snapshot.Roles...),
		RoleBindings:     append([]HostedPermissionPolicyRoleBinding(nil), snapshot.RoleBindings...),
		PermissionGrants: append([]HostedPermissionPolicyGrant(nil), snapshot.PermissionGrants...),
	}
	return cloned
}

func isValidHostedPermissionSubjectStatus(status string) bool {
	switch status {
	case "", "active", "suspended", "disabled":
		return true
	default:
		return false
	}
}

func isValidHostedPermissionMembershipStatus(status string) bool {
	switch status {
	case "", "active", "suspended", "revoked":
		return true
	default:
		return false
	}
}

func isValidHostedPermissionRoleStatus(status string) bool {
	switch status {
	case "", "active", "disabled":
		return true
	default:
		return false
	}
}

func isValidHostedPermissionBindingStatus(status string) bool {
	switch status {
	case "", "active", "revoked":
		return true
	default:
		return false
	}
}

func isValidHostedPermissionGrantStatus(status string) bool {
	switch status {
	case "", "active", "revoked":
		return true
	default:
		return false
	}
}

func (d *HostedPermissionPolicyDraft) UpsertSubject(subject HostedPermissionPolicySubject) {
	d.Snapshot.Subjects = upsertHostedPermissionPolicySubject(d.Snapshot.Subjects, subject)
}

func (d *HostedPermissionPolicyDraft) UpsertMembership(membership HostedPermissionPolicyMembership) {
	d.Snapshot.Memberships = upsertHostedPermissionPolicyMembership(d.Snapshot.Memberships, membership)
}

func (d *HostedPermissionPolicyDraft) UpsertRole(role HostedPermissionPolicyRole) {
	d.Snapshot.Roles = upsertHostedPermissionPolicyRole(d.Snapshot.Roles, role)
}

func (d *HostedPermissionPolicyDraft) UpsertRoleBinding(binding HostedPermissionPolicyRoleBinding) {
	d.Snapshot.RoleBindings = upsertHostedPermissionPolicyRoleBinding(d.Snapshot.RoleBindings, binding)
}

func (d *HostedPermissionPolicyDraft) UpsertGrant(grant HostedPermissionPolicyGrant) {
	d.Snapshot.PermissionGrants = upsertHostedPermissionPolicyGrant(d.Snapshot.PermissionGrants, grant)
}

func upsertHostedPermissionPolicySubject(items []HostedPermissionPolicySubject, item HostedPermissionPolicySubject) []HostedPermissionPolicySubject {
	for i := range items {
		if items[i].ID == item.ID {
			items[i] = item
			return items
		}
	}
	return append(items, item)
}

func upsertHostedPermissionPolicyMembership(items []HostedPermissionPolicyMembership, item HostedPermissionPolicyMembership) []HostedPermissionPolicyMembership {
	for i := range items {
		if items[i].SubjectID == item.SubjectID && items[i].ProjectID == item.ProjectID && items[i].OrganizationID == item.OrganizationID {
			items[i] = item
			return items
		}
	}
	return append(items, item)
}

func upsertHostedPermissionPolicyRole(items []HostedPermissionPolicyRole, item HostedPermissionPolicyRole) []HostedPermissionPolicyRole {
	for i := range items {
		if items[i].ID == item.ID {
			items[i] = item
			return items
		}
	}
	return append(items, item)
}

func upsertHostedPermissionPolicyRoleBinding(items []HostedPermissionPolicyRoleBinding, item HostedPermissionPolicyRoleBinding) []HostedPermissionPolicyRoleBinding {
	for i := range items {
		if items[i].SubjectID == item.SubjectID && items[i].ProjectID == item.ProjectID && items[i].OrganizationID == item.OrganizationID && items[i].RoleID == item.RoleID {
			items[i] = item
			return items
		}
	}
	return append(items, item)
}

func upsertHostedPermissionPolicyGrant(items []HostedPermissionPolicyGrant, item HostedPermissionPolicyGrant) []HostedPermissionPolicyGrant {
	for i := range items {
		if items[i].RoleID == item.RoleID && items[i].Permission == item.Permission && items[i].ScopeType == item.ScopeType {
			items[i] = item
			return items
		}
	}
	return append(items, item)
}
