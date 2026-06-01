package registry

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"strings"
	"testing"
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
