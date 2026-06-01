package registry

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"slices"
	"strings"
	"testing"
	"time"
)

func TestPostgresHostedPermissionPolicyMutationWritesDraftChangeReviewAndAudit(t *testing.T) {
	rows := hostedPolicyMutationRows()
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	begin, err := BeginHostedPermissionPolicyDraft(context.Background(), db, hostedPolicyMutationOptions("req-begin", "raw-begin-key"))
	if err != nil {
		t.Fatalf("begin hosted policy draft: %v", err)
	}
	if script.beginOptions.Isolation != driver.IsolationLevel(sql.LevelSerializable) || script.beginOptions.ReadOnly {
		t.Fatalf("expected serializable write transaction, got %#v", script.beginOptions)
	}
	if len(script.rows.PolicyMutationDrafts) != 1 {
		t.Fatalf("expected draft row, got %#v", script.rows.PolicyMutationDrafts)
	}
	if script.rows.PolicyMutationDrafts[0].ID != begin.DraftID || script.rows.PolicyMutationDrafts[0].BasePolicyVersion != "policy-v1" {
		t.Fatalf("unexpected draft row: %#v result=%#v", script.rows.PolicyMutationDrafts[0], begin)
	}

	apply, err := ApplyHostedPermissionPolicyDraftChange(context.Background(), db, HostedPermissionPolicyMutationOptions{
		ProjectID:      "project-a",
		OrganizationID: "org-a",
		ActorID:        "admin-a",
		RequestID:      "req-change",
		PolicySource:   "hosted_permission_store",
		DraftID:        begin.DraftID,
	}, HostedPermissionPolicyDraftChange{
		ObjectType: "permission_grant",
		Operation:  "upsert",
		ObjectID:   "grant-read",
		PatchSummary: map[string]string{
			"permission": "control_plane.permission_policy.promote",
		},
	})
	if err != nil {
		t.Fatalf("apply hosted policy draft change: %v", err)
	}
	if len(script.rows.PolicyDraftChanges) != 1 {
		t.Fatalf("expected one patch evidence row, got %#v", script.rows.PolicyDraftChanges)
	}
	change := script.rows.PolicyDraftChanges[0]
	if change.ChangeSeq != 1 || change.ProjectID != "project-a" || !strings.HasPrefix(change.PatchFingerprint, "sha256:") {
		t.Fatalf("unexpected change row: %#v", change)
	}
	if !strings.HasPrefix(apply.PolicyFingerprint, "sha256:") || script.rows.PolicyMutationDrafts[0].DraftPolicyFingerprint != apply.PolicyFingerprint {
		t.Fatalf("draft fingerprint was not persisted: result=%#v draft=%#v", apply, script.rows.PolicyMutationDrafts[0])
	}

	review, err := RequestHostedPermissionPolicyReview(context.Background(), db, HostedPermissionPolicyMutationOptions{
		ProjectID:      "project-a",
		OrganizationID: "org-a",
		ActorID:        "admin-a",
		RequestID:      "req-review",
		PolicySource:   "hosted_permission_store",
		DraftID:        begin.DraftID,
	})
	if err != nil {
		t.Fatalf("request hosted policy review: %v", err)
	}
	if review.PolicyFingerprint != apply.PolicyFingerprint || script.rows.PolicyMutationDrafts[0].Status != "review_requested" {
		t.Fatalf("review did not preserve draft fingerprint/status: review=%#v draft=%#v", review, script.rows.PolicyMutationDrafts[0])
	}
	if len(script.rows.AdminAuditEvents) != 3 {
		t.Fatalf("expected begin/apply/review audit events, got %#v", script.rows.AdminAuditEvents)
	}
}

func TestPostgresHostedPermissionPolicyMutationPromoteReplaysAndRejectsConflicts(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.PolicyMutationDrafts = append(rows.PolicyMutationDrafts, PersistentPolicyMutationDraftRow{
		ID:                     "draft-policy-v2",
		ProjectID:              "project-a",
		OrganizationID:         "org-a",
		PolicySource:           "hosted_permission_store",
		BasePolicyVersion:      "policy-v1",
		DraftPolicyVersion:     "policy-v2",
		DraftPolicyFingerprint: "sha256:policy-v2",
		Status:                 "review_requested",
		ActorID:                "admin-a",
	})
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	opts := hostedPolicyMutationOptions("req-promote-first", "raw-idempotency-key-promote")
	opts.DraftID = "draft-policy-v2"
	first, err := PromoteHostedPermissionPolicyDraft(context.Background(), db, opts)
	if err != nil {
		t.Fatalf("promote hosted policy draft: %v", err)
	}
	if first.PolicyVersion != "policy-v2" || first.PreviousPolicyVersion != "policy-v1" {
		t.Fatalf("unexpected promotion result: %#v", first)
	}
	if len(script.rows.HostedPolicyVersions) != 2 || script.rows.HostedPolicyVersions[0].Status != "superseded" || script.rows.HostedPolicyVersions[1].Status != "active" {
		t.Fatalf("expected append-style policy version promotion, got %#v", script.rows.HostedPolicyVersions)
	}
	if len(script.rows.IdempotencyRecords) != 1 {
		t.Fatalf("expected idempotency record, got %#v", script.rows.IdempotencyRecords)
	}
	record := script.rows.IdempotencyRecords[0]
	if record.IdempotencyKeyHash == "raw-idempotency-key-promote" || record.IdempotencyKeyPrefix == "raw-idempotency-key-promote" {
		t.Fatalf("raw idempotency key leaked into record: %#v", record)
	}

	replayOpts := opts
	replayOpts.RequestID = "req-promote-replay"
	replayed, err := PromoteHostedPermissionPolicyDraft(context.Background(), db, replayOpts)
	if err != nil {
		t.Fatalf("replay hosted policy promotion: %v", err)
	}
	if !replayed.Replayed || replayed.PolicyVersion != first.PolicyVersion {
		t.Fatalf("unexpected replay result: first=%#v replay=%#v", first, replayed)
	}
	if len(script.rows.HostedPolicyVersions) != 2 || script.rows.IdempotencyRecords[0].ReplayCount != 1 {
		t.Fatalf("replay should not create another version and should update replay metadata: versions=%#v idem=%#v", script.rows.HostedPolicyVersions, script.rows.IdempotencyRecords[0])
	}

	conflictOpts := opts
	conflictOpts.RequestID = "req-promote-conflict"
	conflictOpts.DraftPolicyVersion = "policy-v2-conflict"
	_, err = PromoteHostedPermissionPolicyDraft(context.Background(), db, conflictOpts)
	if err == nil {
		t.Fatalf("expected idempotency conflict")
	}
	if mutationErrorType(err) != "IDEMPOTENCY_KEY_CONFLICT" {
		t.Fatalf("unexpected conflict error: %T %v", err, err)
	}
}

func TestPostgresHostedPermissionPolicyMutationPromoteAppliesGraphChanges(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.PolicyMutationDrafts = append(rows.PolicyMutationDrafts, PersistentPolicyMutationDraftRow{
		ID:                     "draft-graph",
		ProjectID:              "project-a",
		OrganizationID:         "org-a",
		PolicySource:           "hosted_permission_store",
		BasePolicyVersion:      "policy-v1",
		DraftPolicyVersion:     "policy-v2",
		DraftPolicyFingerprint: "sha256:policy-v2",
		Status:                 "review_requested",
		ActorID:                "admin-a",
	})
	rows.PolicyDraftChanges = append(rows.PolicyDraftChanges,
		hostedPolicyDraftChange("draft-graph", 1, "subject", "upsert", "subject-a", map[string]string{
			"subject_id":           "subject-a",
			"external_subject_ref": "dogfood/idp/admin",
			"display_name":         "Dogfood Admin",
			"status":               "active",
		}),
		hostedPolicyDraftChange("draft-graph", 2, "membership", "upsert", "subject-a:project-a", map[string]string{
			"subject_id": "subject-a",
			"actor_id":   "actor-a",
			"status":     "active",
		}),
		hostedPolicyDraftChange("draft-graph", 3, "role", "upsert", "policy-admin", map[string]string{
			"role_id":           "policy-admin",
			"name":              "Policy Admin",
			"scope_type":        "project",
			"public_assignable": "false",
			"status":            "active",
		}),
		hostedPolicyDraftChange("draft-graph", 4, "role_binding", "upsert", "subject-a:policy-admin", map[string]string{
			"subject_id": "subject-a",
			"role_id":    "policy-admin",
			"source":     "operator",
			"status":     "active",
		}),
		hostedPolicyDraftChange("draft-graph", 5, "permission_grant", "upsert", "policy-admin:promote", map[string]string{
			"role_id":    "policy-admin",
			"permission": "control_plane.permission_policy.promote",
			"scope_type": "project",
			"status":     "active",
		}),
	)
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	opts := hostedPolicyMutationOptions("req-graph", "raw-idempotency-key-graph")
	opts.DraftID = "draft-graph"
	if _, err := PromoteHostedPermissionPolicyDraft(context.Background(), db, opts); err != nil {
		t.Fatalf("promote graph draft: %v", err)
	}

	if len(script.rows.HostedSubjects) != 1 || script.rows.HostedSubjects[0].ExternalSubjectRef != "dogfood/idp/admin" || script.rows.HostedSubjects[0].Metadata["policy_version"] != "policy-v2" {
		t.Fatalf("subject graph change was not applied: %#v", script.rows.HostedSubjects)
	}
	if len(script.rows.HostedMemberships) != 1 || script.rows.HostedMemberships[0].ActorID != "actor-a" || script.rows.HostedMemberships[0].ProjectID != "project-a" {
		t.Fatalf("membership graph change was not applied: %#v", script.rows.HostedMemberships)
	}
	if len(script.rows.HostedRoles) != 1 || script.rows.HostedRoles[0].ID != "policy-admin" || script.rows.HostedRoles[0].Name != "Policy Admin" {
		t.Fatalf("role graph change was not applied: %#v", script.rows.HostedRoles)
	}
	if len(script.rows.HostedRoleBindings) != 1 || script.rows.HostedRoleBindings[0].SubjectID != "subject-a" || script.rows.HostedRoleBindings[0].RoleID != "policy-admin" {
		t.Fatalf("role binding graph change was not applied: %#v", script.rows.HostedRoleBindings)
	}
	if len(script.rows.HostedGrants) != 1 || script.rows.HostedGrants[0].Permission != "control_plane.permission_policy.promote" || script.rows.HostedGrants[0].Metadata["policy_version"] != "policy-v2" {
		t.Fatalf("permission grant graph change was not applied: %#v", script.rows.HostedGrants)
	}
	if got := script.rows.HostedPolicyVersions[1].Metadata["draft_change_count"]; got != "5" {
		t.Fatalf("expected policy version metadata to record graph apply count, got %#v", script.rows.HostedPolicyVersions[1].Metadata)
	}
}

func TestPostgresHostedPermissionPolicyMutationReadModelConsistencyDogfood(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.PolicyMutationDrafts = append(rows.PolicyMutationDrafts, PersistentPolicyMutationDraftRow{
		ID:                     "draft-consistency",
		ProjectID:              "project-a",
		OrganizationID:         "org-a",
		PolicySource:           "hosted_permission_store",
		BasePolicyVersion:      "policy-v1",
		DraftPolicyVersion:     "policy-v2",
		DraftPolicyFingerprint: "sha256:policy-v2",
		Status:                 "review_requested",
		ActorID:                "admin-a",
	})
	rows.PolicyDraftChanges = append(rows.PolicyDraftChanges,
		hostedPolicyDraftChange("draft-consistency", 1, "subject", "upsert", "subject-a", map[string]string{
			"subject_id":           "subject-a",
			"external_subject_ref": "dogfood/idp/admin",
			"display_name":         "Dogfood Admin",
		}),
		hostedPolicyDraftChange("draft-consistency", 2, "membership", "upsert", "subject-a:project-a", map[string]string{
			"subject_id": "subject-a",
			"actor_id":   "actor-a",
		}),
		hostedPolicyDraftChange("draft-consistency", 3, "role", "upsert", "policy-admin", map[string]string{
			"role_id":    "policy-admin",
			"name":       "Policy Admin",
			"scope_type": "project",
		}),
		hostedPolicyDraftChange("draft-consistency", 4, "role_binding", "upsert", "subject-a:policy-admin", map[string]string{
			"subject_id": "subject-a",
			"role_id":    "policy-admin",
		}),
		hostedPolicyDraftChange("draft-consistency", 5, "permission_grant", "upsert", "policy-admin:promote", map[string]string{
			"role_id":    "policy-admin",
			"permission": PermissionHostedPermissionPolicyPromote,
			"scope_type": "project",
		}),
	)
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	promoteOpts := hostedPolicyMutationOptions("req-consistency-promote", "raw-idempotency-key-consistency-promote")
	promoteOpts.DraftID = "draft-consistency"
	if _, err := PromoteHostedPermissionPolicyDraft(context.Background(), db, promoteOpts); err != nil {
		t.Fatalf("promote consistency draft: %v", err)
	}

	resolvedAt := time.Date(2026, 6, 2, 1, 0, 0, 0, time.UTC)
	afterPromote, err := NewHostedPermissionReadModel(db).Resolve(context.Background(), HostedPermissionLookupRequest{
		PublicPrincipalID:  "public-admin",
		ExternalSubjectRef: "dogfood/idp/admin",
		ProjectID:          "project-a",
		TokenID:            "gateway-token-admin",
		RequiredPermission: PermissionHostedPermissionPolicyPromote,
		ResolvedAt:         resolvedAt,
	})
	if err != nil {
		t.Fatalf("resolve after promotion: %v", err)
	}
	if !afterPromote.Allowed || afterPromote.PolicyVersion != "policy-v2" || afterPromote.PolicyFingerprint != "sha256:policy-v2" {
		t.Fatalf("expected read model to allow promoted graph permission with policy-v2 evidence, got %#v", afterPromote)
	}
	if !slices.Contains(afterPromote.Roles, "policy-admin") || !slices.Contains(afterPromote.Permissions, PermissionHostedPermissionPolicyPromote) {
		t.Fatalf("read model did not consume promoted graph rows: %#v", afterPromote)
	}

	rollbackOpts := hostedPolicyMutationOptions("req-consistency-rollback", "raw-idempotency-key-consistency-rollback")
	rollbackOpts.TargetPolicyVersion = "policy-v1"
	rollbackOpts.DraftPolicyVersion = "policy-v1-rollback-1"
	rollbackOpts.MutationFingerprint = ""
	if _, err := RollbackHostedPermissionPolicy(context.Background(), db, rollbackOpts); err != nil {
		t.Fatalf("rollback consistency policy: %v", err)
	}
	afterRollback, err := NewHostedPermissionReadModel(db).Resolve(context.Background(), HostedPermissionLookupRequest{
		PublicPrincipalID:  "public-admin",
		ExternalSubjectRef: "dogfood/idp/admin",
		ProjectID:          "project-a",
		TokenID:            "gateway-token-admin",
		RequiredPermission: PermissionHostedPermissionPolicyPromote,
		ResolvedAt:         resolvedAt.Add(time.Minute),
	})
	if err != nil {
		t.Fatalf("resolve after rollback: %v", err)
	}
	if !afterRollback.Allowed || afterRollback.PolicyVersion != "policy-v1-rollback-1" || afterRollback.PolicyFingerprint != "sha256:policy-v1" {
		t.Fatalf("expected rollback to change policy evidence without silently rewinding graph permission, got %#v", afterRollback)
	}
	if !slices.Contains(afterRollback.Permissions, PermissionHostedPermissionPolicyPromote) {
		t.Fatalf("rollback should not claim graph rewind in read model dogfood: %#v", afterRollback)
	}
	rollbackMetadata := script.rows.HostedPolicyVersions[len(script.rows.HostedPolicyVersions)-1].Metadata
	if rollbackMetadata["graph_rollback_status"] != "not_applied" {
		t.Fatalf("rollback metadata should explain read-model consistency boundary: %#v", rollbackMetadata)
	}
}

func TestPostgresHostedPermissionPolicyMutationPromoteAppliesGraphStatusChanges(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.HostedSubjects = append(rows.HostedSubjects, PersistentHostedSubjectRow{ID: "subject-a", ExternalSubjectRef: "dogfood/idp/admin", Status: "active"})
	rows.HostedMemberships = append(rows.HostedMemberships, PersistentHostedMembershipRow{SubjectID: "subject-a", ActorID: "actor-a", ProjectID: "project-a", OrganizationID: "org-a", Status: "active"})
	rows.HostedRoles = append(rows.HostedRoles, PersistentHostedRoleRow{ID: "policy-admin", Name: "Policy Admin", ScopeType: "project", Status: "active"})
	rows.HostedRoleBindings = append(rows.HostedRoleBindings, PersistentHostedRoleBindingRow{SubjectID: "subject-a", ProjectID: "project-a", OrganizationID: "org-a", RoleID: "policy-admin", Status: "active", Source: "operator"})
	rows.HostedGrants = append(rows.HostedGrants, PersistentHostedGrantRow{RoleID: "policy-admin", Permission: "control_plane.permission_policy.promote", ScopeType: "project", Status: "active"})
	rows.PolicyMutationDrafts = append(rows.PolicyMutationDrafts, PersistentPolicyMutationDraftRow{
		ID:                     "draft-revoke",
		ProjectID:              "project-a",
		OrganizationID:         "org-a",
		PolicySource:           "hosted_permission_store",
		BasePolicyVersion:      "policy-v1",
		DraftPolicyVersion:     "policy-v2",
		DraftPolicyFingerprint: "sha256:policy-v2",
		Status:                 "review_requested",
		ActorID:                "admin-a",
	})
	rows.PolicyDraftChanges = append(rows.PolicyDraftChanges,
		hostedPolicyDraftChange("draft-revoke", 1, "permission_grant", "revoke", "policy-admin:promote", map[string]string{
			"role_id":    "policy-admin",
			"permission": "control_plane.permission_policy.promote",
			"scope_type": "project",
		}),
		hostedPolicyDraftChangeWithOperation("draft-revoke", 2, "role_binding", "revoke", "subject-a:policy-admin", map[string]string{
			"subject_id": "subject-a",
			"role_id":    "policy-admin",
		}),
	)
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	opts := hostedPolicyMutationOptions("req-revoke", "raw-idempotency-key-revoke")
	opts.DraftID = "draft-revoke"
	if _, err := PromoteHostedPermissionPolicyDraft(context.Background(), db, opts); err != nil {
		t.Fatalf("promote revoke draft: %v", err)
	}
	if script.rows.HostedGrants[0].Status != "revoked" {
		t.Fatalf("expected grant revoked, got %#v", script.rows.HostedGrants)
	}
	if script.rows.HostedRoleBindings[0].Status != "revoked" {
		t.Fatalf("expected role binding revoked, got %#v", script.rows.HostedRoleBindings)
	}
}

func TestPostgresHostedPermissionPolicyMutationRejectsStaleBase(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.HostedPolicyVersions[0].PolicyVersion = "policy-v2"
	rows.HostedPolicyVersions[0].PolicyFingerprint = "sha256:policy-v2"
	rows.PolicyMutationDrafts = append(rows.PolicyMutationDrafts, PersistentPolicyMutationDraftRow{
		ID:                     "draft-stale",
		ProjectID:              "project-a",
		OrganizationID:         "org-a",
		PolicySource:           "hosted_permission_store",
		BasePolicyVersion:      "policy-v1",
		DraftPolicyVersion:     "policy-v3",
		DraftPolicyFingerprint: "sha256:policy-v3",
		Status:                 "review_requested",
		ActorID:                "admin-a",
	})
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	opts := hostedPolicyMutationOptions("req-stale", "raw-idempotency-key-stale")
	opts.DraftID = "draft-stale"
	_, err := PromoteHostedPermissionPolicyDraft(context.Background(), db, opts)
	if err == nil {
		t.Fatalf("expected stale base conflict")
	}
	if mutationErrorType(err) != "POLICY_VERSION_CONFLICT" {
		t.Fatalf("unexpected stale base error: %T %v", err, err)
	}
	if len(script.rows.HostedPolicyVersions) != 1 || len(script.rows.AdminAuditEvents) != 0 {
		t.Fatalf("stale base should not promote or audit success: versions=%#v audits=%#v", script.rows.HostedPolicyVersions, script.rows.AdminAuditEvents)
	}
}

func hostedPolicyDraftChange(draftID string, seq int, objectType string, operation string, objectID string, summary map[string]string) PersistentPolicyDraftChangeRow {
	return hostedPolicyDraftChangeWithOperation(draftID, seq, objectType, operation, objectID, summary)
}

func hostedPolicyDraftChangeWithOperation(draftID string, seq int, objectType string, operation string, objectID string, summary map[string]string) PersistentPolicyDraftChangeRow {
	return PersistentPolicyDraftChangeRow{
		DraftID:          draftID,
		ChangeSeq:        seq,
		ObjectType:       objectType,
		Operation:        operation,
		ObjectID:         objectID,
		ProjectID:        "project-a",
		OrganizationID:   "org-a",
		PatchFingerprint: "sha256:patch",
		PatchSummary:     summary,
	}
}

func TestPostgresHostedPermissionPolicyMutationRollbackAppendsActiveVersion(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.HostedPolicyVersions[0].Status = "superseded"
	rows.HostedPolicyVersions = append(rows.HostedPolicyVersions,
		PersistentHostedPolicyVersionRow{
			PolicySource:      "hosted_permission_store",
			PolicyVersion:     "policy-v2",
			PolicyFingerprint: "sha256:policy-v2",
			Status:            "active",
		},
	)
	rows.HostedSubjects = append(rows.HostedSubjects, PersistentHostedSubjectRow{ID: "subject-a", ExternalSubjectRef: "dogfood/idp/admin", Status: "active", Metadata: map[string]string{"policy_version": "policy-v2"}})
	rows.HostedMemberships = append(rows.HostedMemberships, PersistentHostedMembershipRow{SubjectID: "subject-a", ActorID: "actor-a", ProjectID: "project-a", OrganizationID: "org-a", Status: "active", Metadata: map[string]string{"policy_version": "policy-v2"}})
	rows.HostedRoles = append(rows.HostedRoles, PersistentHostedRoleRow{ID: "policy-admin", Name: "Policy Admin", ScopeType: "project", Status: "active", Metadata: map[string]string{"policy_version": "policy-v2"}})
	rows.HostedRoleBindings = append(rows.HostedRoleBindings, PersistentHostedRoleBindingRow{SubjectID: "subject-a", ProjectID: "project-a", OrganizationID: "org-a", RoleID: "policy-admin", Status: "active", Source: "operator", Metadata: map[string]string{"policy_version": "policy-v2"}})
	rows.HostedGrants = append(rows.HostedGrants, PersistentHostedGrantRow{RoleID: "policy-admin", Permission: "control_plane.permission_policy.promote", ScopeType: "project", Status: "active", Metadata: map[string]string{"policy_version": "policy-v2"}})
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	opts := hostedPolicyMutationOptions("req-rollback", "raw-idempotency-key-rollback")
	opts.TargetPolicyVersion = "policy-v1"
	opts.DraftPolicyVersion = "policy-v1-rollback-1"
	result, err := RollbackHostedPermissionPolicy(context.Background(), db, opts)
	if err != nil {
		t.Fatalf("rollback hosted policy: %v", err)
	}
	if result.PolicyVersion != "policy-v1-rollback-1" || result.TargetPolicyVersion != "policy-v1" || result.PreviousPolicyVersion != "policy-v2" {
		t.Fatalf("unexpected rollback result: %#v", result)
	}
	if len(script.rows.HostedPolicyVersions) != 3 || script.rows.HostedPolicyVersions[1].Status != "superseded" || script.rows.HostedPolicyVersions[2].Status != "active" {
		t.Fatalf("rollback should append a new active version: %#v", script.rows.HostedPolicyVersions)
	}
	metadata := script.rows.HostedPolicyVersions[2].Metadata
	if metadata["graph_apply_mode"] != "policy_version_only" || metadata["graph_rollback_status"] != "not_applied" || metadata["graph_rollback_reason"] != "hosted_graph_rows_not_versioned" {
		t.Fatalf("rollback metadata must state graph rows were not rewound: %#v", metadata)
	}
	if script.rows.HostedSubjects[0].Metadata["policy_version"] != "policy-v2" ||
		script.rows.HostedMemberships[0].Metadata["policy_version"] != "policy-v2" ||
		script.rows.HostedRoles[0].Metadata["policy_version"] != "policy-v2" ||
		script.rows.HostedRoleBindings[0].Metadata["policy_version"] != "policy-v2" ||
		script.rows.HostedGrants[0].Metadata["policy_version"] != "policy-v2" {
		t.Fatalf("rollback should not silently rewrite hosted graph rows: subjects=%#v memberships=%#v roles=%#v bindings=%#v grants=%#v", script.rows.HostedSubjects, script.rows.HostedMemberships, script.rows.HostedRoles, script.rows.HostedRoleBindings, script.rows.HostedGrants)
	}
}

func TestPostgresHostedPermissionPolicyMutationRejectsSecretUnsafePatchSummary(t *testing.T) {
	rows := hostedPolicyMutationRows()
	rows.PolicyMutationDrafts = append(rows.PolicyMutationDrafts, PersistentPolicyMutationDraftRow{
		ID:                     "draft-secret",
		ProjectID:              "project-a",
		OrganizationID:         "org-a",
		PolicySource:           "hosted_permission_store",
		BasePolicyVersion:      "policy-v1",
		DraftPolicyVersion:     "policy-v2",
		DraftPolicyFingerprint: "",
		Status:                 "draft",
		ActorID:                "admin-a",
	})
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	_, err := ApplyHostedPermissionPolicyDraftChange(context.Background(), db, HostedPermissionPolicyMutationOptions{
		ProjectID:      "project-a",
		OrganizationID: "org-a",
		ActorID:        "admin-a",
		RequestID:      "req-secret",
		PolicySource:   "hosted_permission_store",
		DraftID:        "draft-secret",
	}, HostedPermissionPolicyDraftChange{
		ObjectType: "subject",
		Operation:  "upsert",
		ObjectID:   "subject-a",
		PatchSummary: map[string]string{
			"raw_token": "should-not-persist",
		},
	})
	if err == nil {
		t.Fatalf("expected secret unsafe patch summary to be rejected")
	}
	if mutationErrorType(err) != "POLICY_STATE_CONFLICT" {
		t.Fatalf("unexpected secret summary error: %T %v", err, err)
	}
	if len(script.rows.PolicyDraftChanges) != 0 || len(script.rows.AdminAuditEvents) != 0 {
		t.Fatalf("unsafe patch should not persist change/audit rows: changes=%#v audits=%#v", script.rows.PolicyDraftChanges, script.rows.AdminAuditEvents)
	}
}

func hostedPolicyMutationRows() PersistentRegistryRows {
	return PersistentRegistryRows{
		Projects: []PersistentProjectRow{{
			ID:          "project-a",
			Name:        "Project A",
			Status:      "active",
			DefaultMode: "proxy",
		}},
		HostedPolicyVersions: []PersistentHostedPolicyVersionRow{{
			PolicySource:      "hosted_permission_store",
			PolicyVersion:     "policy-v1",
			PolicyFingerprint: "sha256:policy-v1",
			Status:            "active",
		}},
	}
}

func hostedPolicyMutationOptions(requestID string, idempotencyKey string) HostedPermissionPolicyMutationOptions {
	return HostedPermissionPolicyMutationOptions{
		ProjectID:           "project-a",
		OrganizationID:      "org-a",
		ActorID:             "admin-a",
		RequestID:           requestID,
		IdempotencyKey:      idempotencyKey,
		PolicySource:        "hosted_permission_store",
		BasePolicyVersion:   "policy-v1",
		DraftPolicyVersion:  "policy-v2",
		MutationFingerprint: "sha256:policy-v2",
	}
}
