package registry

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
)

const (
	HostedPermissionPolicyMutationBeginDraftOperation    = "policy_mutation.begin_draft"
	HostedPermissionPolicyMutationApplyChangeOperation   = "policy_mutation.apply_change"
	HostedPermissionPolicyMutationRequestReviewOperation = "policy_mutation.request_review"
	HostedPermissionPolicyMutationPromoteOperation       = "policy_mutation.promote"
	HostedPermissionPolicyMutationRollbackOperation      = "policy_mutation.rollback"
	hostedPermissionPolicyMutationVersion                = "hosted-permission-policy-mutation-v0"
	hostedPermissionPolicyMutationSource                 = "hosted_permission_policy_mutation_private"
)

type HostedPermissionPolicyMutationOptions struct {
	Operation           string
	ProjectID           string
	OrganizationID      string
	ActorID             string
	RequestID           string
	IdempotencyKey      string
	PolicySource        string
	BasePolicyVersion   string
	DraftID             string
	DraftPolicyVersion  string
	TargetPolicyVersion string
	MutationFingerprint string
}

type HostedPermissionPolicyMutationDurableResult struct {
	Operation                 string `json:"operation"`
	ProjectID                 string `json:"project_id"`
	OrganizationID            string `json:"organization_id"`
	ActorID                   string `json:"actor_id"`
	RequestID                 string `json:"request_id"`
	Replayed                  bool   `json:"replayed"`
	PolicySource              string `json:"policy_source"`
	DraftID                   string `json:"draft_id,omitempty"`
	BasePolicyVersion         string `json:"base_policy_version,omitempty"`
	DraftPolicyVersion        string `json:"draft_policy_version,omitempty"`
	PreviousPolicyVersion     string `json:"previous_policy_version,omitempty"`
	TargetPolicyVersion       string `json:"target_policy_version,omitempty"`
	PolicyVersion             string `json:"policy_version,omitempty"`
	PreviousPolicyFingerprint string `json:"previous_policy_fingerprint,omitempty"`
	PolicyFingerprint         string `json:"policy_fingerprint,omitempty"`
	IdempotencyRecordID       int64  `json:"idempotency_record_id,omitempty"`
	AdminAuditEventID         int64  `json:"admin_audit_event_id,omitempty"`
}

type HostedPermissionPolicyDraftChange struct {
	ChangeSeq        int
	ObjectType       string
	Operation        string
	ObjectID         string
	ProjectID        string
	OrganizationID   string
	PatchFingerprint string
	PatchSummary     map[string]string
}

func BeginHostedPermissionPolicyDraft(ctx context.Context, db *sql.DB, opts HostedPermissionPolicyMutationOptions) (HostedPermissionPolicyMutationDurableResult, error) {
	opts = normalizeHostedPermissionPolicyMutationOptions(opts, HostedPermissionPolicyMutationBeginDraftOperation)
	if err := validateHostedPermissionPolicyMutationRequired(opts, true); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	tx, err := beginHostedPermissionPolicyMutationTx(ctx, db)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()
	active, err := loadActiveHostedPolicyVersion(ctx, tx, opts.PolicySource)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if opts.BasePolicyVersion == "" {
		opts.BasePolicyVersion = active.Version
	}
	if opts.BasePolicyVersion != active.Version {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("base policy %q is stale; active policy is %q", opts.BasePolicyVersion, active.Version))
	}
	if opts.DraftPolicyVersion == "" {
		opts.DraftPolicyVersion = opts.BasePolicyVersion + "-draft"
	}
	if opts.DraftID == "" {
		opts.DraftID = opts.PolicySource + ":" + opts.DraftPolicyVersion
	}
	metadata := hostedPermissionPolicyMutationMetadata(opts, nil)
	if err := insertHostedPolicyMutationDraft(ctx, tx, opts, metadata); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	auditID, err := insertHostedPolicyMutationAudit(ctx, tx, opts, opts.DraftID, "success", "", metadata)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := linkHostedPolicyMutationDraftAudit(ctx, tx, opts.DraftID, auditID); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	result := HostedPermissionPolicyMutationDurableResult{
		Operation:          opts.operation(),
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		PolicySource:       opts.PolicySource,
		DraftID:            opts.DraftID,
		BasePolicyVersion:  opts.BasePolicyVersion,
		DraftPolicyVersion: opts.DraftPolicyVersion,
		PolicyVersion:      active.Version,
		PolicyFingerprint:  active.Fingerprint,
		AdminAuditEventID:  auditID,
	}
	if err := tx.Commit(); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy draft: %w", err))
	}
	committed = true
	return result, nil
}

func ApplyHostedPermissionPolicyDraftChange(ctx context.Context, db *sql.DB, opts HostedPermissionPolicyMutationOptions, change HostedPermissionPolicyDraftChange) (HostedPermissionPolicyMutationDurableResult, error) {
	opts = normalizeHostedPermissionPolicyMutationOptions(opts, HostedPermissionPolicyMutationApplyChangeOperation)
	if err := validateHostedPermissionPolicyMutationRequired(opts, false); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	tx, err := beginHostedPermissionPolicyMutationTx(ctx, db)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()
	draft, err := loadHostedPolicyMutationDraft(ctx, tx, opts.DraftID)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if draft.Status != "draft" {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft %q is not writable", opts.DraftID))
	}
	opts = mergeHostedPolicyDraftOptions(opts, draft)
	change = normalizeHostedPermissionPolicyDraftChange(change, opts)
	if err := validateHostedPermissionPolicyDraftChange(change, opts); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if change.ChangeSeq == 0 {
		seq, err := nextHostedPolicyMutationDraftChangeSeq(ctx, tx, opts.DraftID)
		if err != nil {
			return HostedPermissionPolicyMutationDurableResult{}, err
		}
		change.ChangeSeq = seq
	}
	if change.PatchFingerprint == "" {
		fingerprint, err := hashCanonicalJSON(change)
		if err != nil {
			return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_STATE_CONFLICT", "platform", true, fmt.Errorf("fingerprint hosted policy draft change: %w", err))
		}
		change.PatchFingerprint = fingerprint
	}
	fingerprint, err := hashCanonicalJSON(map[string]any{
		"base_policy_version":  opts.BasePolicyVersion,
		"draft_id":             opts.DraftID,
		"draft_policy_version": opts.DraftPolicyVersion,
		"previous_fingerprint": opts.MutationFingerprint,
		"change":               change,
	})
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_STATE_CONFLICT", "platform", true, fmt.Errorf("fingerprint hosted policy draft: %w", err))
	}
	opts.MutationFingerprint = fingerprint
	if err := insertHostedPolicyMutationDraftChange(ctx, tx, opts.DraftID, change); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	metadata := hostedPermissionPolicyMutationMetadata(opts, map[string]string{
		"change_seq":        fmt.Sprint(change.ChangeSeq),
		"object_type":       change.ObjectType,
		"object_id":         change.ObjectID,
		"patch_fingerprint": change.PatchFingerprint,
	})
	if err := updateHostedPolicyMutationDraftFingerprint(ctx, tx, opts.DraftID, fingerprint, metadata); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	auditID, err := insertHostedPolicyMutationAudit(ctx, tx, opts, opts.DraftID, "success", "", metadata)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := linkHostedPolicyMutationDraftAudit(ctx, tx, opts.DraftID, auditID); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	result := HostedPermissionPolicyMutationDurableResult{
		Operation:          opts.operation(),
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		PolicySource:       opts.PolicySource,
		DraftID:            opts.DraftID,
		BasePolicyVersion:  opts.BasePolicyVersion,
		DraftPolicyVersion: opts.DraftPolicyVersion,
		PolicyFingerprint:  fingerprint,
		AdminAuditEventID:  auditID,
	}
	if err := tx.Commit(); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy draft change: %w", err))
	}
	committed = true
	return result, nil
}

func RequestHostedPermissionPolicyReview(ctx context.Context, db *sql.DB, opts HostedPermissionPolicyMutationOptions) (HostedPermissionPolicyMutationDurableResult, error) {
	opts = normalizeHostedPermissionPolicyMutationOptions(opts, HostedPermissionPolicyMutationRequestReviewOperation)
	if err := validateHostedPermissionPolicyMutationRequired(opts, false); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	tx, err := beginHostedPermissionPolicyMutationTx(ctx, db)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()
	draft, err := loadHostedPolicyMutationDraft(ctx, tx, opts.DraftID)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if draft.Status != "draft" {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft %q is not open for review", opts.DraftID))
	}
	opts = mergeHostedPolicyDraftOptions(opts, draft)
	metadata := hostedPermissionPolicyMutationMetadata(opts, map[string]string{"draft_status": "review_requested"})
	if err := updateHostedPolicyMutationDraftReview(ctx, tx, opts, metadata); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	auditID, err := insertHostedPolicyMutationAudit(ctx, tx, opts, opts.DraftID, "success", "", metadata)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := linkHostedPolicyMutationDraftAudit(ctx, tx, opts.DraftID, auditID); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	result := HostedPermissionPolicyMutationDurableResult{
		Operation:          opts.operation(),
		ProjectID:          opts.ProjectID,
		OrganizationID:     opts.OrganizationID,
		ActorID:            opts.ActorID,
		RequestID:          opts.RequestID,
		PolicySource:       opts.PolicySource,
		DraftID:            opts.DraftID,
		BasePolicyVersion:  opts.BasePolicyVersion,
		DraftPolicyVersion: opts.DraftPolicyVersion,
		PolicyFingerprint:  opts.MutationFingerprint,
		AdminAuditEventID:  auditID,
	}
	if err := tx.Commit(); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy review: %w", err))
	}
	committed = true
	return result, nil
}

func PromoteHostedPermissionPolicyDraft(ctx context.Context, db *sql.DB, opts HostedPermissionPolicyMutationOptions) (HostedPermissionPolicyMutationDurableResult, error) {
	opts = normalizeHostedPermissionPolicyMutationOptions(opts, HostedPermissionPolicyMutationPromoteOperation)
	if err := validateHostedPermissionPolicyMutationRequired(opts, false); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	tx, err := beginHostedPermissionPolicyMutationTx(ctx, db)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()
	draft, err := loadHostedPolicyMutationDraft(ctx, tx, opts.DraftID)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	opts = mergeHostedPolicyDraftOptions(opts, draft)
	if opts.MutationFingerprint == "" {
		opts.MutationFingerprint = draft.DraftPolicyFingerprint
	}
	idempotency, err := newHostedPolicyMutationIdempotencyRequest(opts)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	record, replay, err := reserveHostedPolicyMutationIdempotency(ctx, tx, idempotency)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if replay {
		if err := tx.Commit(); err != nil {
			return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy replay: %w", err))
		}
		committed = true
		return record.Result, nil
	}
	if draft.Status != "review_requested" {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft %q is not promotable", opts.DraftID))
	}
	active, err := loadActiveHostedPolicyVersion(ctx, tx, opts.PolicySource)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if opts.BasePolicyVersion != active.Version {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("base policy %q is stale; active policy is %q", opts.BasePolicyVersion, active.Version))
	}
	promotedVersion := opts.DraftPolicyVersion
	metadata := hostedPermissionPolicyMutationMetadata(opts, map[string]string{
		"previous_policy_version":     active.Version,
		"previous_policy_fingerprint": active.Fingerprint,
		"policy_version":              promotedVersion,
		"policy_fingerprint":          opts.MutationFingerprint,
	})
	if err := supersedeHostedPolicyVersion(ctx, tx, opts.PolicySource, active.Version); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := insertActiveHostedPolicyVersion(ctx, tx, opts.PolicySource, promotedVersion, opts.MutationFingerprint, metadata); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := markHostedPolicyMutationDraftPromoted(ctx, tx, opts.DraftID, promotedVersion); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	auditID, err := insertHostedPolicyMutationAudit(ctx, tx, opts, opts.DraftID, "success", "", metadata)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	result := HostedPermissionPolicyMutationDurableResult{
		Operation:                 opts.operation(),
		ProjectID:                 opts.ProjectID,
		OrganizationID:            opts.OrganizationID,
		ActorID:                   opts.ActorID,
		RequestID:                 opts.RequestID,
		PolicySource:              opts.PolicySource,
		DraftID:                   opts.DraftID,
		BasePolicyVersion:         opts.BasePolicyVersion,
		DraftPolicyVersion:        opts.DraftPolicyVersion,
		PreviousPolicyVersion:     active.Version,
		PolicyVersion:             promotedVersion,
		PreviousPolicyFingerprint: active.Fingerprint,
		PolicyFingerprint:         opts.MutationFingerprint,
		IdempotencyRecordID:       record.ID,
		AdminAuditEventID:         auditID,
	}
	if err := completeHostedPolicyMutationIdempotency(ctx, tx, record, result, auditID); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := tx.Commit(); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy promotion: %w", err))
	}
	committed = true
	return result, nil
}

func RollbackHostedPermissionPolicy(ctx context.Context, db *sql.DB, opts HostedPermissionPolicyMutationOptions) (HostedPermissionPolicyMutationDurableResult, error) {
	opts = normalizeHostedPermissionPolicyMutationOptions(opts, HostedPermissionPolicyMutationRollbackOperation)
	if err := validateHostedPermissionPolicyMutationRequired(opts, false); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if strings.TrimSpace(opts.TargetPolicyVersion) == "" {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("target policy version is required"))
	}
	tx, err := beginHostedPermissionPolicyMutationTx(ctx, db)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()
	idempotency, err := newHostedPolicyMutationIdempotencyRequest(opts)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	record, replay, err := reserveHostedPolicyMutationIdempotency(ctx, tx, idempotency)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if replay {
		if err := tx.Commit(); err != nil {
			return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy rollback replay: %w", err))
		}
		committed = true
		return record.Result, nil
	}
	active, err := loadActiveHostedPolicyVersion(ctx, tx, opts.PolicySource)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	target, err := loadHostedPolicyVersion(ctx, tx, opts.PolicySource, opts.TargetPolicyVersion)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	rollbackVersion := opts.DraftPolicyVersion
	if rollbackVersion == "" {
		rollbackVersion = opts.TargetPolicyVersion + "-rollback"
	}
	if opts.MutationFingerprint == "" {
		opts.MutationFingerprint = target.Fingerprint
	}
	metadata := hostedPermissionPolicyMutationMetadata(opts, map[string]string{
		"previous_policy_version":     active.Version,
		"previous_policy_fingerprint": active.Fingerprint,
		"target_policy_version":       target.Version,
		"policy_version":              rollbackVersion,
		"policy_fingerprint":          opts.MutationFingerprint,
	})
	if err := supersedeHostedPolicyVersion(ctx, tx, opts.PolicySource, active.Version); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := insertActiveHostedPolicyVersion(ctx, tx, opts.PolicySource, rollbackVersion, opts.MutationFingerprint, metadata); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	auditID, err := insertHostedPolicyMutationAudit(ctx, tx, opts, rollbackVersion, "success", "", metadata)
	if err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	result := HostedPermissionPolicyMutationDurableResult{
		Operation:                 opts.operation(),
		ProjectID:                 opts.ProjectID,
		OrganizationID:            opts.OrganizationID,
		ActorID:                   opts.ActorID,
		RequestID:                 opts.RequestID,
		PolicySource:              opts.PolicySource,
		BasePolicyVersion:         active.Version,
		TargetPolicyVersion:       target.Version,
		PreviousPolicyVersion:     active.Version,
		PolicyVersion:             rollbackVersion,
		PreviousPolicyFingerprint: active.Fingerprint,
		PolicyFingerprint:         opts.MutationFingerprint,
		IdempotencyRecordID:       record.ID,
		AdminAuditEventID:         auditID,
	}
	if err := completeHostedPolicyMutationIdempotency(ctx, tx, record, result, auditID); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, err
	}
	if err := tx.Commit(); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit hosted policy rollback: %w", err))
	}
	committed = true
	return result, nil
}

type hostedPolicyVersionRow struct {
	Version     string
	Fingerprint string
	Status      string
}

type hostedPolicyMutationDraftRow struct {
	ID                     string
	ProjectID              string
	OrganizationID         string
	PolicySource           string
	BasePolicyVersion      string
	DraftPolicyVersion     string
	DraftPolicyFingerprint string
	Status                 string
	ActorID                string
}

type hostedPolicyMutationIdempotencyRequest struct {
	Enabled            bool
	ProjectID          string
	ActorID            string
	Operation          string
	KeyHash            string
	KeyPrefix          string
	RequestFingerprint string
	RequestSummary     map[string]string
	FirstRequestID     string
}

type hostedPolicyMutationIdempotencyRecord struct {
	ID     int64
	Result HostedPermissionPolicyMutationDurableResult
}

func beginHostedPermissionPolicyMutationTx(ctx context.Context, db *sql.DB) (*sql.Tx, error) {
	if db == nil {
		return nil, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("postgres registry db is required"))
	}
	tx, err := db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable, ReadOnly: false})
	if err != nil {
		return nil, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("begin hosted policy mutation transaction: %w", err))
	}
	return tx, nil
}

func normalizeHostedPermissionPolicyMutationOptions(opts HostedPermissionPolicyMutationOptions, operation string) HostedPermissionPolicyMutationOptions {
	opts.ProjectID = strings.TrimSpace(opts.ProjectID)
	opts.OrganizationID = strings.TrimSpace(opts.OrganizationID)
	opts.ActorID = strings.TrimSpace(opts.ActorID)
	opts.RequestID = strings.TrimSpace(opts.RequestID)
	opts.IdempotencyKey = strings.TrimSpace(opts.IdempotencyKey)
	opts.PolicySource = strings.TrimSpace(opts.PolicySource)
	opts.BasePolicyVersion = strings.TrimSpace(opts.BasePolicyVersion)
	opts.DraftID = strings.TrimSpace(opts.DraftID)
	opts.DraftPolicyVersion = strings.TrimSpace(opts.DraftPolicyVersion)
	opts.TargetPolicyVersion = strings.TrimSpace(opts.TargetPolicyVersion)
	opts.MutationFingerprint = strings.TrimSpace(opts.MutationFingerprint)
	if opts.PolicySource == "" {
		opts.PolicySource = "hosted_permission_store"
	}
	opts.Operation = operation
	return opts
}

func (opts HostedPermissionPolicyMutationOptions) operation() string {
	return opts.Operation
}

func validateHostedPermissionPolicyMutationRequired(opts HostedPermissionPolicyMutationOptions, allowMissingDraft bool) error {
	if opts.ProjectID == "" {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("project id is required"))
	}
	if opts.OrganizationID == "" {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("organization id is required"))
	}
	if opts.ActorID == "" {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("actor id is required"))
	}
	if opts.PolicySource == "" {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("policy source is required"))
	}
	if !allowMissingDraft && opts.DraftID == "" && opts.operation() != HostedPermissionPolicyMutationRollbackOperation {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft id is required"))
	}
	return nil
}

func loadActiveHostedPolicyVersion(ctx context.Context, tx *sql.Tx, policySource string) (hostedPolicyVersionRow, error) {
	var row hostedPolicyVersionRow
	if err := tx.QueryRowContext(ctx, `
SELECT policy_version, policy_fingerprint, status
FROM hosted_policy_versions
WHERE policy_source = $1 AND status = 'active'
FOR UPDATE`, policySource).Scan(&row.Version, &row.Fingerprint, &row.Status); err != nil {
		return hostedPolicyVersionRow{}, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("load active hosted policy version: %w", err))
	}
	return row, nil
}

func loadHostedPolicyVersion(ctx context.Context, tx *sql.Tx, policySource string, policyVersion string) (hostedPolicyVersionRow, error) {
	var row hostedPolicyVersionRow
	if err := tx.QueryRowContext(ctx, `
SELECT policy_version, policy_fingerprint, status
FROM hosted_policy_versions
WHERE policy_source = $1 AND policy_version = $2
FOR UPDATE`, policySource, policyVersion).Scan(&row.Version, &row.Fingerprint, &row.Status); err != nil {
		return hostedPolicyVersionRow{}, mutationError("POLICY_VERSION_CONFLICT", "caller", false, fmt.Errorf("load hosted policy version: %w", err))
	}
	return row, nil
}

func loadHostedPolicyMutationDraft(ctx context.Context, tx *sql.Tx, draftID string) (hostedPolicyMutationDraftRow, error) {
	var row hostedPolicyMutationDraftRow
	if err := tx.QueryRowContext(ctx, `
SELECT id, project_id, organization_id, policy_source, base_policy_version, draft_policy_version, draft_policy_fingerprint, status, actor_id
FROM hosted_policy_mutation_drafts
WHERE id = $1
FOR UPDATE`, draftID).Scan(&row.ID, &row.ProjectID, &row.OrganizationID, &row.PolicySource, &row.BasePolicyVersion, &row.DraftPolicyVersion, &row.DraftPolicyFingerprint, &row.Status, &row.ActorID); err != nil {
		return hostedPolicyMutationDraftRow{}, mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("load hosted policy mutation draft: %w", err))
	}
	return row, nil
}

func mergeHostedPolicyDraftOptions(opts HostedPermissionPolicyMutationOptions, draft hostedPolicyMutationDraftRow) HostedPermissionPolicyMutationOptions {
	opts.DraftID = draft.ID
	opts.ProjectID = defaultString(opts.ProjectID, draft.ProjectID)
	opts.OrganizationID = defaultString(opts.OrganizationID, draft.OrganizationID)
	opts.PolicySource = defaultString(opts.PolicySource, draft.PolicySource)
	opts.BasePolicyVersion = defaultString(opts.BasePolicyVersion, draft.BasePolicyVersion)
	opts.DraftPolicyVersion = defaultString(opts.DraftPolicyVersion, draft.DraftPolicyVersion)
	opts.MutationFingerprint = defaultString(opts.MutationFingerprint, draft.DraftPolicyFingerprint)
	return opts
}

func normalizeHostedPermissionPolicyDraftChange(change HostedPermissionPolicyDraftChange, opts HostedPermissionPolicyMutationOptions) HostedPermissionPolicyDraftChange {
	change.ObjectType = strings.TrimSpace(change.ObjectType)
	change.Operation = strings.TrimSpace(change.Operation)
	change.ObjectID = strings.TrimSpace(change.ObjectID)
	change.ProjectID = defaultString(strings.TrimSpace(change.ProjectID), opts.ProjectID)
	change.OrganizationID = defaultString(strings.TrimSpace(change.OrganizationID), opts.OrganizationID)
	change.PatchFingerprint = strings.TrimSpace(change.PatchFingerprint)
	if change.PatchSummary == nil {
		change.PatchSummary = map[string]string{}
	}
	return change
}

func validateHostedPermissionPolicyDraftChange(change HostedPermissionPolicyDraftChange, opts HostedPermissionPolicyMutationOptions) error {
	if change.ProjectID != opts.ProjectID || change.OrganizationID != opts.OrganizationID {
		return mutationError("POLICY_SCOPE_VIOLATION", "caller", false, fmt.Errorf("draft change scope does not match policy draft"))
	}
	if change.ObjectID == "" {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft change object id is required"))
	}
	if !oneOf(change.ObjectType, "subject", "membership", "role", "role_binding", "permission_grant") {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("unsupported draft change object type %q", change.ObjectType))
	}
	if !oneOf(change.Operation, "upsert", "revoke", "disable") {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("unsupported draft change operation %q", change.Operation))
	}
	if change.PatchFingerprint != "" && !strings.HasPrefix(change.PatchFingerprint, "sha256:") {
		return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft change patch fingerprint must use sha256"))
	}
	for key, value := range change.PatchSummary {
		if containsHostedPolicyMutationSecretMarker(key) || containsHostedPolicyMutationSecretMarker(value) {
			return mutationError("POLICY_STATE_CONFLICT", "caller", false, fmt.Errorf("draft change patch summary must be secret-safe"))
		}
	}
	return nil
}

func nextHostedPolicyMutationDraftChangeSeq(ctx context.Context, tx *sql.Tx, draftID string) (int, error) {
	var current int
	if err := tx.QueryRowContext(ctx, `
SELECT COALESCE(MAX(change_seq), 0)
FROM hosted_policy_mutation_draft_changes
WHERE draft_id = $1`, draftID).Scan(&current); err != nil {
		return 0, mutationError("PERSISTENT_STORE_READ_FAILED", "platform", true, fmt.Errorf("load hosted policy draft change sequence: %w", err))
	}
	return current + 1, nil
}

func insertHostedPolicyMutationDraft(ctx context.Context, tx *sql.Tx, opts HostedPermissionPolicyMutationOptions, metadata map[string]string) error {
	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy draft metadata: %w", err))
	}
	if _, err := tx.ExecContext(ctx, `
INSERT INTO hosted_policy_mutation_drafts (
  id,
  project_id,
  organization_id,
  policy_source,
  base_policy_version,
  draft_policy_version,
  draft_policy_fingerprint,
  status,
  actor_id,
  metadata
)
VALUES ($1, $2, $3, $4, $5, $6, $7, 'draft', $8, $9::jsonb)`, opts.DraftID, opts.ProjectID, opts.OrganizationID, opts.PolicySource, opts.BasePolicyVersion, opts.DraftPolicyVersion, opts.MutationFingerprint, opts.ActorID, metadataJSON); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("insert hosted policy mutation draft: %w", err))
	}
	return nil
}

func insertHostedPolicyMutationDraftChange(ctx context.Context, tx *sql.Tx, draftID string, change HostedPermissionPolicyDraftChange) error {
	summaryJSON, err := json.Marshal(change.PatchSummary)
	if err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy draft change summary: %w", err))
	}
	if _, err := tx.ExecContext(ctx, `
INSERT INTO hosted_policy_mutation_draft_changes (
  draft_id,
  change_seq,
  object_type,
  operation,
  object_id,
  project_id,
  organization_id,
  patch_fingerprint,
  patch_summary
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)`, draftID, change.ChangeSeq, change.ObjectType, change.Operation, change.ObjectID, change.ProjectID, change.OrganizationID, change.PatchFingerprint, summaryJSON); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("insert hosted policy draft change: %w", err))
	}
	return nil
}

func updateHostedPolicyMutationDraftFingerprint(ctx context.Context, tx *sql.Tx, draftID string, fingerprint string, metadata map[string]string) error {
	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy draft metadata: %w", err))
	}
	if _, err := tx.ExecContext(ctx, `
UPDATE hosted_policy_mutation_drafts
SET draft_policy_fingerprint = $1,
    metadata = $2::jsonb,
    updated_at = now()
WHERE id = $3`, fingerprint, metadataJSON, draftID); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("update hosted policy draft fingerprint: %w", err))
	}
	return nil
}

func updateHostedPolicyMutationDraftReview(ctx context.Context, tx *sql.Tx, opts HostedPermissionPolicyMutationOptions, metadata map[string]string) error {
	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy review metadata: %w", err))
	}
	if _, err := tx.ExecContext(ctx, `
UPDATE hosted_policy_mutation_drafts
SET status = 'review_requested',
    review_requested_by = $1,
    review_requested_at = now(),
    draft_policy_fingerprint = $2,
    metadata = $3::jsonb,
    updated_at = now()
WHERE id = $4`, opts.ActorID, opts.MutationFingerprint, metadataJSON, opts.DraftID); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("request hosted policy review: %w", err))
	}
	return nil
}

func linkHostedPolicyMutationDraftAudit(ctx context.Context, tx *sql.Tx, draftID string, auditID int64) error {
	if _, err := tx.ExecContext(ctx, `
UPDATE hosted_policy_mutation_drafts
SET admin_audit_event_id = $1,
    updated_at = now()
WHERE id = $2`, auditID, draftID); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("link hosted policy draft audit: %w", err))
	}
	return nil
}

func supersedeHostedPolicyVersion(ctx context.Context, tx *sql.Tx, policySource string, policyVersion string) error {
	if _, err := tx.ExecContext(ctx, `
UPDATE hosted_policy_versions
SET status = 'superseded',
    metadata = metadata || jsonb_build_object('superseded_at', now()::text)
WHERE policy_source = $1 AND policy_version = $2 AND status = 'active'`, policySource, policyVersion); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("supersede hosted policy version: %w", err))
	}
	return nil
}

func insertActiveHostedPolicyVersion(ctx context.Context, tx *sql.Tx, policySource string, policyVersion string, fingerprint string, metadata map[string]string) error {
	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy version metadata: %w", err))
	}
	if _, err := tx.ExecContext(ctx, `
INSERT INTO hosted_policy_versions (
  policy_source,
  policy_version,
  policy_fingerprint,
  status,
  activated_at,
  metadata
)
VALUES ($1, $2, $3, 'active', now(), $4::jsonb)`, policySource, policyVersion, fingerprint, metadataJSON); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("insert active hosted policy version: %w", err))
	}
	return nil
}

func markHostedPolicyMutationDraftPromoted(ctx context.Context, tx *sql.Tx, draftID string, promotedVersion string) error {
	if _, err := tx.ExecContext(ctx, `
UPDATE hosted_policy_mutation_drafts
SET status = 'promoted',
    promoted_policy_version = $1,
    promoted_at = now(),
    updated_at = now()
WHERE id = $2`, promotedVersion, draftID); err != nil {
		return mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("mark hosted policy draft promoted: %w", err))
	}
	return nil
}

func insertHostedPolicyMutationAudit(ctx context.Context, tx *sql.Tx, opts HostedPermissionPolicyMutationOptions, resourceID string, outcome string, errorType string, metadata map[string]string) (int64, error) {
	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return 0, mutationError("AUDIT_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy mutation audit metadata: %w", err))
	}
	var id int64
	if err := tx.QueryRowContext(ctx, `
INSERT INTO admin_audit_events (actor_id, action, resource_type, resource_id, request_id, outcome, error_type, metadata)
VALUES ($1, $2, 'hosted_permission_policy', $3, $4, $5, $6, $7::jsonb)
RETURNING id`, opts.ActorID, opts.operation(), resourceID, opts.RequestID, outcome, errorType, metadataJSON).Scan(&id); err != nil {
		return 0, mutationError("AUDIT_WRITE_FAILED", "platform", true, fmt.Errorf("record hosted policy mutation audit: %w", err))
	}
	return id, nil
}

func hostedPermissionPolicyMutationMetadata(opts HostedPermissionPolicyMutationOptions, extra map[string]string) map[string]string {
	metadata := map[string]string{
		"version":             hostedPermissionPolicyMutationVersion,
		"source":              hostedPermissionPolicyMutationSource,
		"operation":           opts.operation(),
		"project_id":          opts.ProjectID,
		"organization_id":     opts.OrganizationID,
		"actor_id":            opts.ActorID,
		"request_id":          opts.RequestID,
		"policy_source":       opts.PolicySource,
		"base_policy_version": opts.BasePolicyVersion,
	}
	if opts.DraftID != "" {
		metadata["draft_id"] = opts.DraftID
	}
	if opts.DraftPolicyVersion != "" {
		metadata["draft_policy_version"] = opts.DraftPolicyVersion
	}
	if opts.TargetPolicyVersion != "" {
		metadata["target_policy_version"] = opts.TargetPolicyVersion
	}
	if opts.MutationFingerprint != "" {
		metadata["mutation_fingerprint"] = opts.MutationFingerprint
	}
	if opts.IdempotencyKey != "" {
		scope := hostedPolicyMutationIdempotencyScope(opts)
		metadata["idempotency_key_hash"] = scope.KeyHash
		metadata["idempotency_key_prefix"] = scope.KeyPrefix
	}
	for key, value := range extra {
		if value != "" {
			metadata[key] = value
		}
	}
	return metadata
}

func newHostedPolicyMutationIdempotencyRequest(opts HostedPermissionPolicyMutationOptions) (hostedPolicyMutationIdempotencyRequest, error) {
	if opts.IdempotencyKey == "" {
		return hostedPolicyMutationIdempotencyRequest{}, nil
	}
	scope := hostedPolicyMutationIdempotencyScope(opts)
	summary := hostedPermissionPolicyMutationMetadata(opts, nil)
	delete(summary, "request_id")
	fingerprint, err := hashCanonicalJSON(summary)
	if err != nil {
		return hostedPolicyMutationIdempotencyRequest{}, err
	}
	return hostedPolicyMutationIdempotencyRequest{
		Enabled:            true,
		ProjectID:          scope.ProjectID,
		ActorID:            scope.ActorID,
		Operation:          scope.Operation,
		KeyHash:            scope.KeyHash,
		KeyPrefix:          scope.KeyPrefix,
		RequestFingerprint: fingerprint,
		RequestSummary:     summary,
		FirstRequestID:     opts.RequestID,
	}, nil
}

func hostedPolicyMutationIdempotencyScope(opts HostedPermissionPolicyMutationOptions) idempotencyScopeRecord {
	keyHash := hashString(opts.IdempotencyKey)
	keyPrefix := keyHash
	if len(keyPrefix) > len("sha256:")+12 {
		keyPrefix = keyPrefix[:len("sha256:")+12]
	}
	return idempotencyScopeRecord{
		ProjectID: opts.ProjectID,
		ActorID:   opts.ActorID,
		Operation: opts.operation(),
		KeyHash:   keyHash,
		KeyPrefix: keyPrefix,
	}
}

func reserveHostedPolicyMutationIdempotency(ctx context.Context, tx *sql.Tx, req hostedPolicyMutationIdempotencyRequest) (hostedPolicyMutationIdempotencyRecord, bool, error) {
	if !req.Enabled {
		return hostedPolicyMutationIdempotencyRecord{}, false, nil
	}
	record, replay, err := reserveIdempotency(ctx, tx, importReplaceIdempotencyRequest{
		Enabled:            true,
		ProjectID:          req.ProjectID,
		ActorID:            req.ActorID,
		Operation:          req.Operation,
		KeyHash:            req.KeyHash,
		KeyPrefix:          req.KeyPrefix,
		RequestFingerprint: req.RequestFingerprint,
		RequestSummary:     req.RequestSummary,
		FirstRequestID:     req.FirstRequestID,
	})
	if err != nil || !replay {
		return hostedPolicyMutationIdempotencyRecord{ID: record.ID}, replay, err
	}
	result, err := hostedPolicyMutationResultFromCachedResponse(record.ResponseBody)
	if err != nil {
		return hostedPolicyMutationIdempotencyRecord{}, false, mutationError("IDEMPOTENCY_RESPONSE_REPLAY_FAILED", "platform", true, err)
	}
	result.Replayed = true
	result.IdempotencyRecordID = record.ID
	return hostedPolicyMutationIdempotencyRecord{ID: record.ID, Result: result}, true, nil
}

func completeHostedPolicyMutationIdempotency(ctx context.Context, tx *sql.Tx, record hostedPolicyMutationIdempotencyRecord, result HostedPermissionPolicyMutationDurableResult, adminAuditEventID int64) error {
	if record.ID == 0 {
		return nil
	}
	body, err := json.Marshal(result)
	if err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode hosted policy mutation idempotency response: %w", err))
	}
	responseFingerprint, err := hashCanonicalJSON(result)
	if err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("fingerprint hosted policy mutation idempotency response: %w", err))
	}
	if _, err := tx.ExecContext(ctx, `
UPDATE admin_mutation_idempotency_records
SET status = 'succeeded',
    response_status_code = 200,
    response_body = $1::jsonb,
    response_fingerprint = $2,
    registry_fingerprint = $3,
    previous_registry_fingerprint = $4,
    snapshot_version = $5,
    noop = false,
    registry_revision_id = NULL,
    admin_audit_event_id = $6,
    completed_at = now(),
    expires_at = now() + interval '30 days',
    updated_at = now()
WHERE id = $7`, body, responseFingerprint, result.PolicyFingerprint, result.PreviousPolicyFingerprint, result.PolicyVersion, adminAuditEventID, record.ID); err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("complete hosted policy mutation idempotency record: %w", err))
	}
	return nil
}

func hostedPolicyMutationResultFromCachedResponse(data []byte) (HostedPermissionPolicyMutationDurableResult, error) {
	if len(data) == 0 || string(data) == "null" {
		return HostedPermissionPolicyMutationDurableResult{}, fmt.Errorf("cached hosted policy mutation response is empty")
	}
	var result HostedPermissionPolicyMutationDurableResult
	if err := json.Unmarshal(data, &result); err != nil {
		return HostedPermissionPolicyMutationDurableResult{}, fmt.Errorf("decode cached hosted policy mutation response: %w", err)
	}
	return result, nil
}

func containsHostedPolicyMutationSecretMarker(value string) bool {
	lower := strings.ToLower(value)
	for _, marker := range []string{"raw_token", "access_token", "refresh_token", "session_token", "gateway_secret", "plaintext", "api_key", "idempotency_key"} {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	return false
}
