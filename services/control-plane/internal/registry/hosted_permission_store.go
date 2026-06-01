package registry

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"errors"
	"fmt"
	"slices"
	"time"
)

const (
	HostedPermissionDecisionAllowed               = 200
	HostedPermissionDecisionDenied                = 403
	HostedPermissionDecisionSourceUnavailable     = 503
	HostedPermissionErrorPublicAuthzDenied        = "PUBLIC_AUTHZ_DENIED"
	HostedPermissionErrorSourceUnavailable        = "PERMISSION_SOURCE_UNAVAILABLE"
	HostedPermissionDenySubjectInactive           = "public principal subject is not active"
	HostedPermissionDenyMissingMembership         = "public principal is missing project membership"
	HostedPermissionDenyMembershipInactive        = "public principal project membership is inactive"
	HostedPermissionDenyMissingEndpointPermission = "public principal lacks endpoint permission"
	HostedPermissionDenyPolicyUnavailable         = "hosted permission policy view is stale or ambiguous"
)

type HostedPermissionReadModel struct {
	DB *sql.DB
}

func NewHostedPermissionReadModel(db *sql.DB) HostedPermissionReadModel {
	return HostedPermissionReadModel{DB: db}
}

type HostedPermissionLookupRequest struct {
	PublicPrincipalID  string
	ExternalSubjectRef string
	ProjectID          string
	TokenID            string
	RequiredPermission string
	ResolvedAt         time.Time
}

type HostedPermissionDecision struct {
	Allowed            bool
	Status             int
	ErrorType          string
	DenyReason         string
	SubjectID          string
	ActorID            string
	ProjectID          string
	OrganizationID     string
	TokenID            string
	Roles              []string
	Permissions        []string
	RequiredPermission string
	PolicySource       string
	PolicyVersion      string
	PolicyFingerprint  string
	DecisionID         string
	PermissionSource   string
	ResolvedAt         time.Time
}

type hostedPermissionPolicyVersion struct {
	Source      string
	Version     string
	Fingerprint string
}

type hostedPermissionSubject struct {
	ID     string
	Status string
}

type hostedPermissionMembership struct {
	ActorID        string
	ProjectID      string
	OrganizationID string
	Status         string
}

type hostedPermissionRowQueryer interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
}

func (m HostedPermissionReadModel) Resolve(ctx context.Context, req HostedPermissionLookupRequest) (HostedPermissionDecision, error) {
	if m.DB == nil {
		return HostedPermissionDecision{}, fmt.Errorf("hosted permission db is required")
	}
	resolvedAt := req.ResolvedAt.UTC()
	if resolvedAt.IsZero() {
		resolvedAt = time.Now().UTC()
	}
	req.ResolvedAt = resolvedAt

	tx, err := m.DB.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelRepeatableRead,
		ReadOnly:  true,
	})
	if err != nil {
		return HostedPermissionDecision{}, fmt.Errorf("begin hosted permission read transaction: %w", err)
	}
	defer tx.Rollback()

	policy, ok, err := loadHostedActivePolicyVersion(ctx, tx)
	if err != nil {
		return HostedPermissionDecision{}, err
	}
	if !ok {
		decision := hostedDeniedDecision(req, policy, HostedPermissionDecisionSourceUnavailable, HostedPermissionErrorSourceUnavailable, HostedPermissionDenyPolicyUnavailable)
		if err := tx.Commit(); err != nil {
			return HostedPermissionDecision{}, fmt.Errorf("commit hosted permission read transaction: %w", err)
		}
		return decision, nil
	}

	subjectRef := req.ExternalSubjectRef
	if subjectRef == "" {
		subjectRef = req.PublicPrincipalID
	}
	subject, ok, err := loadHostedSubject(ctx, tx, subjectRef)
	if err != nil {
		return HostedPermissionDecision{}, err
	}
	if !ok || subject.Status != "active" {
		decision := hostedDeniedDecision(req, policy, HostedPermissionDecisionDenied, HostedPermissionErrorPublicAuthzDenied, HostedPermissionDenySubjectInactive)
		if ok {
			decision.SubjectID = subject.ID
			decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
		}
		if err := tx.Commit(); err != nil {
			return HostedPermissionDecision{}, fmt.Errorf("commit hosted permission read transaction: %w", err)
		}
		return decision, nil
	}

	membership, ok, err := loadHostedMembership(ctx, tx, subject.ID, req.ProjectID)
	if err != nil {
		return HostedPermissionDecision{}, err
	}
	if !ok {
		decision := hostedDeniedDecision(req, policy, HostedPermissionDecisionDenied, HostedPermissionErrorPublicAuthzDenied, HostedPermissionDenyMissingMembership)
		decision.SubjectID = subject.ID
		decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
		if err := tx.Commit(); err != nil {
			return HostedPermissionDecision{}, fmt.Errorf("commit hosted permission read transaction: %w", err)
		}
		return decision, nil
	}

	if membership.Status != "active" {
		decision := hostedDeniedDecision(req, policy, HostedPermissionDecisionDenied, HostedPermissionErrorPublicAuthzDenied, HostedPermissionDenyMembershipInactive)
		decision.SubjectID = subject.ID
		decision.ActorID = membership.ActorID
		decision.ProjectID = membership.ProjectID
		decision.OrganizationID = membership.OrganizationID
		decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
		if err := tx.Commit(); err != nil {
			return HostedPermissionDecision{}, fmt.Errorf("commit hosted permission read transaction: %w", err)
		}
		return decision, nil
	}

	roles, err := loadHostedRoles(ctx, tx, subject.ID, membership.ProjectID, membership.OrganizationID)
	if err != nil {
		return HostedPermissionDecision{}, err
	}
	permissions, err := loadHostedPermissions(ctx, tx, subject.ID, membership.ProjectID, membership.OrganizationID)
	if err != nil {
		return HostedPermissionDecision{}, err
	}

	decision := HostedPermissionDecision{
		Allowed:            slices.Contains(permissions, req.RequiredPermission),
		Status:             HostedPermissionDecisionAllowed,
		SubjectID:          subject.ID,
		ActorID:            membership.ActorID,
		ProjectID:          membership.ProjectID,
		OrganizationID:     membership.OrganizationID,
		TokenID:            req.TokenID,
		Roles:              roles,
		Permissions:        permissions,
		RequiredPermission: req.RequiredPermission,
		PolicySource:       policy.Source,
		PolicyVersion:      policy.Version,
		PolicyFingerprint:  policy.Fingerprint,
		PermissionSource:   policy.Source,
		ResolvedAt:         req.ResolvedAt,
	}
	if !decision.Allowed {
		decision.Status = HostedPermissionDecisionDenied
		decision.ErrorType = HostedPermissionErrorPublicAuthzDenied
		decision.DenyReason = HostedPermissionDenyMissingEndpointPermission
	}
	decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)

	if err := tx.Commit(); err != nil {
		return HostedPermissionDecision{}, fmt.Errorf("commit hosted permission read transaction: %w", err)
	}
	return decision, nil
}

func loadHostedActivePolicyVersion(ctx context.Context, q sqlQueryer) (hostedPermissionPolicyVersion, bool, error) {
	rows, err := q.QueryContext(ctx, `
SELECT policy_source, policy_version, policy_fingerprint
FROM hosted_policy_versions
WHERE status = 'active'
ORDER BY policy_source, policy_version`)
	if err != nil {
		return hostedPermissionPolicyVersion{}, false, fmt.Errorf("query hosted active policy versions: %w", err)
	}
	defer rows.Close()

	var policies []hostedPermissionPolicyVersion
	for rows.Next() {
		var policy hostedPermissionPolicyVersion
		if err := rows.Scan(&policy.Source, &policy.Version, &policy.Fingerprint); err != nil {
			return hostedPermissionPolicyVersion{}, false, fmt.Errorf("scan hosted active policy version: %w", err)
		}
		policies = append(policies, policy)
	}
	if err := rows.Err(); err != nil {
		return hostedPermissionPolicyVersion{}, false, fmt.Errorf("iterate hosted active policy versions: %w", err)
	}
	if len(policies) != 1 {
		return hostedPermissionPolicyVersion{}, false, nil
	}
	return policies[0], true, nil
}

func loadHostedSubject(ctx context.Context, q hostedPermissionRowQueryer, externalSubjectRef string) (hostedPermissionSubject, bool, error) {
	if externalSubjectRef == "" {
		return hostedPermissionSubject{}, false, nil
	}
	row := q.QueryRowContext(ctx, `
SELECT id, status
FROM hosted_subjects
WHERE external_subject_ref = $1
ORDER BY id`, externalSubjectRef)
	var subject hostedPermissionSubject
	if err := row.Scan(&subject.ID, &subject.Status); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return hostedPermissionSubject{}, false, nil
		}
		return hostedPermissionSubject{}, false, fmt.Errorf("query hosted subject: %w", err)
	}
	return subject, true, nil
}

func loadHostedMembership(ctx context.Context, q hostedPermissionRowQueryer, subjectID string, projectID string) (hostedPermissionMembership, bool, error) {
	row := q.QueryRowContext(ctx, `
SELECT actor_id, project_id, organization_id, status
FROM hosted_project_memberships
WHERE subject_id = $1 AND project_id = $2`, subjectID, projectID)
	var membership hostedPermissionMembership
	if err := row.Scan(&membership.ActorID, &membership.ProjectID, &membership.OrganizationID, &membership.Status); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return hostedPermissionMembership{}, false, nil
		}
		return hostedPermissionMembership{}, false, fmt.Errorf("query hosted project membership: %w", err)
	}
	return membership, true, nil
}

func loadHostedRoles(ctx context.Context, q sqlQueryer, subjectID string, projectID string, organizationID string) ([]string, error) {
	rows, err := q.QueryContext(ctx, `
SELECT r.id
FROM hosted_role_bindings b
JOIN hosted_roles r ON r.id = b.role_id
WHERE b.subject_id = $1
  AND b.project_id = $2
  AND b.organization_id = $3
  AND b.status = 'active'
  AND r.status = 'active'
ORDER BY r.id`, subjectID, projectID, organizationID)
	if err != nil {
		return nil, fmt.Errorf("query hosted roles: %w", err)
	}
	defer rows.Close()
	return scanHostedStrings(rows, "hosted role")
}

func loadHostedPermissions(ctx context.Context, q sqlQueryer, subjectID string, projectID string, organizationID string) ([]string, error) {
	rows, err := q.QueryContext(ctx, `
SELECT DISTINCT g.permission
FROM hosted_role_bindings b
JOIN hosted_roles r ON r.id = b.role_id
JOIN hosted_permission_grants g ON g.role_id = r.id
WHERE b.subject_id = $1
  AND b.project_id = $2
  AND b.organization_id = $3
  AND b.status = 'active'
  AND r.status = 'active'
  AND g.status = 'active'
ORDER BY g.permission`, subjectID, projectID, organizationID)
	if err != nil {
		return nil, fmt.Errorf("query hosted permissions: %w", err)
	}
	defer rows.Close()
	return scanHostedStrings(rows, "hosted permission")
}

func scanHostedStrings(rows *sql.Rows, label string) ([]string, error) {
	var out []string
	for rows.Next() {
		var value string
		if err := rows.Scan(&value); err != nil {
			return nil, fmt.Errorf("scan %s: %w", label, err)
		}
		out = append(out, value)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate %s rows: %w", label, err)
	}
	return out, nil
}

func hostedDeniedDecision(req HostedPermissionLookupRequest, policy hostedPermissionPolicyVersion, status int, errorType string, denyReason string) HostedPermissionDecision {
	decision := HostedPermissionDecision{
		Allowed:            false,
		Status:             status,
		ErrorType:          errorType,
		DenyReason:         denyReason,
		ProjectID:          req.ProjectID,
		TokenID:            req.TokenID,
		RequiredPermission: req.RequiredPermission,
		PolicySource:       policy.Source,
		PolicyVersion:      policy.Version,
		PolicyFingerprint:  policy.Fingerprint,
		PermissionSource:   policy.Source,
		ResolvedAt:         req.ResolvedAt,
	}
	decision.DecisionID = hostedPermissionDecisionID(decision.SubjectID, decision.ProjectID, decision.RequiredPermission, decision.PolicyVersion, decision.ResolvedAt)
	return decision
}

func hostedPermissionDecisionID(subjectID string, projectID string, requiredPermission string, policyVersion string, resolvedAt time.Time) string {
	source := fmt.Sprintf("%s|%s|%s|%s|%s", subjectID, projectID, requiredPermission, policyVersion, resolvedAt.UTC().Format(time.RFC3339Nano))
	sum := sha256.Sum256([]byte(source))
	return fmt.Sprintf("decision-%x", sum[:8])
}
