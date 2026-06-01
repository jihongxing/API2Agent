package registry

import (
	"fmt"
	"slices"
	"strings"
	"testing"
	"time"
)

const (
	policyMutationTestProjectID      = "policy-mutation-project"
	policyMutationTestOrganizationID = "policy-mutation-org"
	policyMutationTestSource         = "hosted-permission-policy-store-fixture"
	policyMutationTestBaseVersion    = "hosted-permission-policy-v1"
	policyMutationTestExternalRef    = "dogfood/idp/admin"
	policyMutationTestSubjectID      = "subject-policy-admin"
	policyMutationTestActorID        = "actor-policy-admin"
	policyMutationPermissionValidate = "control_plane.permission_policy.validate"
	policyMutationPermissionPromote  = "control_plane.permission_policy.promote"
	policyMutationPermissionRollback = "control_plane.permission_policy.rollback"
)

func TestHostedPermissionPolicyMutationPromoteUpdatesReadModelEvidence(t *testing.T) {
	h := newPolicyMutationHarness()
	before := h.ResolvePermission(policyMutationTestExternalRef, policyMutationPermissionPromote, policyMutationTime())
	if before.Allowed {
		t.Fatalf("expected promote permission denied before policy promotion: %#v", before)
	}

	draft := mustBeginPolicyMutationDraft(t, h, policyMutationTestBaseVersion, "hosted-permission-policy-v2")
	draft.UpsertGrant(HostedPermissionPolicyGrant{
		RoleID:     "policy-admin",
		Permission: policyMutationPermissionPromote,
		ScopeType:  "project",
		Status:     "active",
	})
	validation, err := h.ValidateDraft(draft.ID)
	if err != nil {
		t.Fatalf("validate draft: %v", err)
	}
	if !validation.Allowed || !strings.HasPrefix(validation.PolicyFingerprint, "sha256:") {
		t.Fatalf("unexpected validation: %#v", validation)
	}
	if err := h.RequestReview(draft.ID); err != nil {
		t.Fatalf("request review: %v", err)
	}

	result, err := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          policyMutationTestProjectID,
		OrganizationID:     policyMutationTestOrganizationID,
		ActorID:            policyMutationTestActorID,
		RequestID:          "policy-promote-1",
		IdempotencyKey:     "raw-idempotency-key-promote",
		BasePolicyVersion:  policyMutationTestBaseVersion,
		DraftPolicyVersion: "hosted-permission-policy-v2",
	})
	if err != nil {
		t.Fatalf("promote draft: %v", err)
	}
	if !result.Allowed || result.PolicyVersion != "hosted-permission-policy-v2" || result.PreviousPolicyVersion != policyMutationTestBaseVersion {
		t.Fatalf("unexpected promotion result: %#v", result)
	}
	if result.IdempotencyKeyHash == "raw-idempotency-key-promote" || result.IdempotencyKeyPrefix == "raw-idempotency-key-promote" {
		t.Fatalf("raw idempotency key leaked into result: %#v", result)
	}
	if h.Versions[policyMutationTestBaseVersion].Status != "superseded" || h.Versions["hosted-permission-policy-v2"].Status != "active" {
		t.Fatalf("unexpected policy version states: %#v", h.Versions)
	}

	after := h.ResolvePermission(policyMutationTestExternalRef, policyMutationPermissionPromote, policyMutationTime())
	if !after.Allowed || after.PolicyVersion != "hosted-permission-policy-v2" || after.PolicyFingerprint != result.PolicyFingerprint {
		t.Fatalf("expected promoted permission evidence, got %#v", after)
	}
	if !slices.Contains(after.Permissions, policyMutationPermissionPromote) {
		t.Fatalf("expected promoted permission in read-model evidence: %#v", after.Permissions)
	}
	assertPolicyMutationAuditSecretSafe(t, h.Audits, "raw-idempotency-key-promote")
}

func TestHostedPermissionPolicyMutationIdempotencyReplayAndConflict(t *testing.T) {
	h := newPolicyMutationHarness()
	draft := mustBeginPolicyMutationDraft(t, h, policyMutationTestBaseVersion, "hosted-permission-policy-v2")
	draft.UpsertGrant(HostedPermissionPolicyGrant{RoleID: "policy-admin", Permission: policyMutationPermissionPromote, ScopeType: "project", Status: "active"})
	if err := h.RequestReview(draft.ID); err != nil {
		t.Fatalf("request review: %v", err)
	}
	first, err := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          policyMutationTestProjectID,
		OrganizationID:     policyMutationTestOrganizationID,
		ActorID:            policyMutationTestActorID,
		RequestID:          "policy-promote-first",
		IdempotencyKey:     "same-policy-key",
		BasePolicyVersion:  policyMutationTestBaseVersion,
		DraftPolicyVersion: "hosted-permission-policy-v2",
	})
	if err != nil {
		t.Fatalf("first promote: %v", err)
	}
	auditCount := len(h.Audits)
	replayed, err := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          policyMutationTestProjectID,
		OrganizationID:     policyMutationTestOrganizationID,
		ActorID:            policyMutationTestActorID,
		RequestID:          "policy-promote-replay",
		IdempotencyKey:     "same-policy-key",
		BasePolicyVersion:  policyMutationTestBaseVersion,
		DraftPolicyVersion: "hosted-permission-policy-v2",
	})
	if err != nil {
		t.Fatalf("replay promote: %v", err)
	}
	if !replayed.Replayed || replayed.PolicyFingerprint != first.PolicyFingerprint || replayed.PolicyVersion != first.PolicyVersion {
		t.Fatalf("unexpected replay result: first=%#v replay=%#v", first, replayed)
	}
	if len(h.Audits) != auditCount {
		t.Fatalf("idempotency replay must not create a new audit event: %#v", h.Audits)
	}
	record := h.Idempotency[hostedPermissionPolicyMutationScope(HostedPermissionPolicyMutationRequest{
		Operation:      "policy_mutation.promote",
		ProjectID:      policyMutationTestProjectID,
		ActorID:        policyMutationTestActorID,
		IdempotencyKey: "same-policy-key",
	})]
	if record == nil || record.ReplayCount != 1 || record.LastReplayRequestID != "policy-promote-replay" {
		t.Fatalf("expected replay metadata, got %#v", record)
	}

	conflictDraft := mustBeginPolicyMutationDraft(t, h, "hosted-permission-policy-v2", "hosted-permission-policy-v3")
	conflictDraft.UpsertGrant(HostedPermissionPolicyGrant{RoleID: "policy-admin", Permission: policyMutationPermissionRollback, ScopeType: "project", Status: "active"})
	if err := h.RequestReview(conflictDraft.ID); err != nil {
		t.Fatalf("request conflict review: %v", err)
	}
	_, err = h.PromoteDraft(conflictDraft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          policyMutationTestProjectID,
		OrganizationID:     policyMutationTestOrganizationID,
		ActorID:            policyMutationTestActorID,
		RequestID:          "policy-promote-conflict",
		IdempotencyKey:     "same-policy-key",
		BasePolicyVersion:  "hosted-permission-policy-v2",
		DraftPolicyVersion: "hosted-permission-policy-v3",
	})
	assertPolicyMutationError(t, err, "IDEMPOTENCY_KEY_CONFLICT")
	if h.ActiveVersion != "hosted-permission-policy-v2" {
		t.Fatalf("idempotency conflict must not mutate active policy: %q", h.ActiveVersion)
	}
}

func TestHostedPermissionPolicyMutationRejectsScopeAndDuplicateViolations(t *testing.T) {
	h := newPolicyMutationHarness()
	draft := mustBeginPolicyMutationDraft(t, h, policyMutationTestBaseVersion, "hosted-permission-policy-v2")
	draft.Snapshot.PermissionGrants = append(draft.Snapshot.PermissionGrants,
		HostedPermissionPolicyGrant{RoleID: "policy-admin", Permission: policyMutationPermissionPromote, ScopeType: "platform", Status: "active"},
	)

	validation, err := h.ValidateDraft(draft.ID)
	assertPolicyMutationError(t, err, "POLICY_SCOPE_VIOLATION")
	if validation.Allowed {
		t.Fatalf("expected scope violation to fail validation: %#v", validation)
	}

	duplicate := mustBeginPolicyMutationDraft(t, h, policyMutationTestBaseVersion, "hosted-permission-policy-v3")
	duplicate.Snapshot.PermissionGrants = append(duplicate.Snapshot.PermissionGrants,
		HostedPermissionPolicyGrant{RoleID: "policy-admin", Permission: policyMutationPermissionValidate, ScopeType: "project", Status: "active"},
	)
	_, err = h.ValidateDraft(duplicate.ID)
	assertPolicyMutationError(t, err, "POLICY_GRANT_CONFLICT")
}

func TestHostedPermissionPolicyMutationRejectsStaleBaseAndRollsBackAsNewVersion(t *testing.T) {
	h := newPolicyMutationHarness()
	draft := mustBeginPolicyMutationDraft(t, h, policyMutationTestBaseVersion, "hosted-permission-policy-v2")
	draft.UpsertGrant(HostedPermissionPolicyGrant{RoleID: "policy-admin", Permission: policyMutationPermissionPromote, ScopeType: "project", Status: "active"})
	if err := h.RequestReview(draft.ID); err != nil {
		t.Fatalf("request review: %v", err)
	}
	if _, err := h.PromoteDraft(draft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          policyMutationTestProjectID,
		OrganizationID:     policyMutationTestOrganizationID,
		ActorID:            policyMutationTestActorID,
		RequestID:          "policy-promote-1",
		IdempotencyKey:     "policy-key-1",
		BasePolicyVersion:  policyMutationTestBaseVersion,
		DraftPolicyVersion: "hosted-permission-policy-v2",
	}); err != nil {
		t.Fatalf("promote draft: %v", err)
	}

	staleDraft, err := h.BeginStaleDraftForContract(policyMutationTestBaseVersion, "hosted-permission-policy-v3")
	if err != nil {
		t.Fatalf("begin stale contract draft: %v", err)
	}
	_, err = h.PromoteDraft(staleDraft.ID, HostedPermissionPolicyMutationRequest{
		ProjectID:          policyMutationTestProjectID,
		OrganizationID:     policyMutationTestOrganizationID,
		ActorID:            policyMutationTestActorID,
		RequestID:          "policy-stale",
		IdempotencyKey:     "policy-key-stale",
		BasePolicyVersion:  policyMutationTestBaseVersion,
		DraftPolicyVersion: "hosted-permission-policy-v3",
	})
	assertPolicyMutationError(t, err, "POLICY_VERSION_CONFLICT")
	if h.ActiveVersion != "hosted-permission-policy-v2" {
		t.Fatalf("stale base conflict must not mutate active version: %q", h.ActiveVersion)
	}

	rollback, err := h.RollbackPolicy(policyMutationTestBaseVersion, HostedPermissionPolicyMutationRequest{
		ProjectID:           policyMutationTestProjectID,
		OrganizationID:      policyMutationTestOrganizationID,
		ActorID:             policyMutationTestActorID,
		RequestID:           "policy-rollback",
		IdempotencyKey:      "policy-key-rollback",
		BasePolicyVersion:   "hosted-permission-policy-v2",
		TargetPolicyVersion: policyMutationTestBaseVersion,
	})
	if err != nil {
		t.Fatalf("rollback policy: %v", err)
	}
	if rollback.PolicyVersion == policyMutationTestBaseVersion || !strings.Contains(rollback.PolicyVersion, "rollback") {
		t.Fatalf("rollback must create a new active version: %#v", rollback)
	}
	afterRollback := h.ResolvePermission(policyMutationTestExternalRef, policyMutationPermissionPromote, policyMutationTime())
	if afterRollback.Allowed {
		t.Fatalf("expected rollback to remove promoted grant: %#v", afterRollback)
	}
	if h.Versions["hosted-permission-policy-v2"].Status != "superseded" || h.Versions[h.ActiveVersion].Status != "active" {
		t.Fatalf("unexpected version states after rollback: %#v", h.Versions)
	}
}

func TestHostedPermissionPolicyMutationDogfoodReportPasses(t *testing.T) {
	report := RunHostedPermissionPolicyMutationBoundaryDogfood()
	if report.Status != "passed" {
		t.Fatalf("expected dogfood report passed, got %#v", report)
	}
	if report.DraftValidationStatus != "passed" || report.PromotionStatus != "passed" || report.RollbackStatus != "passed" {
		t.Fatalf("unexpected dogfood status fields: %#v", report)
	}
	if report.GatewayDecisionBeforePromotion != "denied" || report.GatewayDecisionAfterPromotion != "allowed" || report.GatewayDecisionAfterRollback != "denied" {
		t.Fatalf("unexpected gateway decision proof: %#v", report)
	}
	if report.IdempotencyReplayCount != 1 || report.IdempotencyConflictStatus != "IDEMPOTENCY_KEY_CONFLICT" || report.StaleBaseConflictStatus != "POLICY_VERSION_CONFLICT" || report.ScopeViolationStatus != "POLICY_SCOPE_VIOLATION" {
		t.Fatalf("unexpected mutation conflict proof: %#v", report)
	}
	if report.AuditContainsRawIdempotencyKey || report.AuditContainsRawToken || report.AuditContainsGatewaySecret {
		t.Fatalf("dogfood report found secret leakage: %#v", report)
	}
}

func newPolicyMutationHarness() *HostedPermissionPolicyMutationHarness {
	return NewHostedPermissionPolicyMutationHarness(
		policyMutationTestProjectID,
		policyMutationTestOrganizationID,
		policyMutationTestSource,
		policyMutationTestBaseVersion,
		HostedPermissionPolicySnapshot{
			Subjects: []HostedPermissionPolicySubject{
				{ID: policyMutationTestSubjectID, ExternalSubjectRef: policyMutationTestExternalRef, Status: "active"},
			},
			Memberships: []HostedPermissionPolicyMembership{
				{SubjectID: policyMutationTestSubjectID, ActorID: policyMutationTestActorID, ProjectID: policyMutationTestProjectID, OrganizationID: policyMutationTestOrganizationID, Status: "active"},
			},
			Roles: []HostedPermissionPolicyRole{
				{ID: "policy-admin", Status: "active"},
			},
			RoleBindings: []HostedPermissionPolicyRoleBinding{
				{SubjectID: policyMutationTestSubjectID, ProjectID: policyMutationTestProjectID, OrganizationID: policyMutationTestOrganizationID, RoleID: "policy-admin", Status: "active"},
			},
			PermissionGrants: []HostedPermissionPolicyGrant{
				{RoleID: "policy-admin", Permission: policyMutationPermissionValidate, ScopeType: "project", Status: "active"},
			},
		},
	)
}

func mustBeginPolicyMutationDraft(t *testing.T, h *HostedPermissionPolicyMutationHarness, baseVersion string, draftVersion string) *HostedPermissionPolicyDraft {
	t.Helper()
	draft, err := h.BeginDraft(baseVersion, draftVersion)
	if err != nil {
		t.Fatalf("begin draft: %v", err)
	}
	return draft
}

func policyMutationTime() time.Time {
	return time.Date(2026, 6, 2, 0, 0, 0, 0, time.UTC)
}

func assertPolicyMutationError(t *testing.T, err error, wantType string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected %s error", wantType)
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != wantType || mutationErr.Retryable {
		t.Fatalf("unexpected mutation error: %#v", mutationErr)
	}
}

func assertPolicyMutationAuditSecretSafe(t *testing.T, audits []HostedPermissionPolicyMutationAuditEvent, forbidden ...string) {
	t.Helper()
	rendered := fmt.Sprintf("%#v", audits)
	defaultForbidden := []string{
		"raw_token",
		"public_token",
		"access_token",
		"refresh_token",
		"gateway_secret",
		"plaintext",
	}
	forbidden = append(forbidden, defaultForbidden...)
	for _, item := range forbidden {
		if strings.Contains(strings.ToLower(rendered), strings.ToLower(item)) {
			t.Fatalf("audit evidence leaked %q in %#v", item, audits)
		}
	}
}
