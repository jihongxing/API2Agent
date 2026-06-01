package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"slices"
	"strings"
	"time"

	"api2agent/services/control-plane/internal/registry"
	_ "github.com/jackc/pgx/v5/stdlib"
)

const (
	projectID               = "gateway-harness-project"
	adminExternalRef        = "dogfood/idp/admin"
	readonlyExternalRef     = "dogfood/idp/readonly"
	noMembershipExternalRef = "dogfood/idp/no-membership"
	suspendedExternalRef    = "dogfood/idp/suspended"
	revokedExternalRef      = "dogfood/idp/revoked"
	adminTokenID            = "gateway-harness-token-admin"
	readonlyTokenID         = "gateway-harness-token-readonly"
	noMembershipTokenID     = "gateway-harness-token-no-membership"
	suspendedTokenID        = "gateway-harness-token-suspended"
	revokedTokenID          = "gateway-harness-token-revoked"
	policySource            = "hosted-permission-store-fixture"
	policyVersion           = "hosted-policy-v1"
	policyFingerprint       = "sha256:hosted-permission-store-fixture-v1"
	resolvedAtText          = "2026-06-01T00:00:00Z"
)

type dogfoodReport struct {
	Status                string             `json:"status"`
	Dogfood               string             `json:"dogfood"`
	Cases                 map[string]caseOut `json:"cases"`
	SecretSafeEvidence    bool               `json:"secret_safe_evidence"`
	DecisionRowsPersisted int                `json:"decision_rows_persisted"`
}

type caseOut struct {
	Allowed            bool     `json:"allowed"`
	Status             int      `json:"status"`
	ErrorType          string   `json:"error_type"`
	DenyReason         string   `json:"deny_reason,omitempty"`
	SubjectID          string   `json:"subject_id,omitempty"`
	ActorID            string   `json:"actor_id,omitempty"`
	ProjectID          string   `json:"project_id,omitempty"`
	OrganizationID     string   `json:"organization_id,omitempty"`
	TokenID            string   `json:"token_id,omitempty"`
	Roles              []string `json:"roles,omitempty"`
	Permissions        []string `json:"permissions,omitempty"`
	RequiredPermission string   `json:"required_permission"`
	PolicySource       string   `json:"policy_source,omitempty"`
	PolicyVersion      string   `json:"policy_version,omitempty"`
	PolicyFingerprint  string   `json:"policy_fingerprint,omitempty"`
	DecisionID         string   `json:"decision_id"`
	ResolvedAt         string   `json:"resolved_at"`
}

func main() {
	postgresDSN := flag.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN")
	flag.Parse()
	if *postgresDSN == "" {
		fail("postgres dsn is required")
	}

	ctx := context.Background()
	db, err := sql.Open("pgx", *postgresDSN)
	if err != nil {
		fail("open postgres: %v", err)
	}
	defer db.Close()
	if err := db.PingContext(ctx); err != nil {
		fail("ping postgres: %v", err)
	}

	report, err := runDogfood(ctx, db)
	if err != nil {
		fail("%v", err)
	}
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fail("marshal report: %v", err)
	}
	fmt.Println(string(data))
}

func runDogfood(ctx context.Context, db *sql.DB) (dogfoodReport, error) {
	resolvedAt, err := time.Parse(time.RFC3339, resolvedAtText)
	if err != nil {
		return dogfoodReport{}, err
	}
	model := registry.NewHostedPermissionReadModel(db)
	cases := map[string]caseOut{}

	admin, err := model.Resolve(ctx, lookup(adminExternalRef, adminTokenID, registry.PermissionRegistryImportReplace, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve admin: %w", err)
	}
	if err := requireAllowed(admin, registry.PermissionRegistryImportReplace); err != nil {
		return dogfoodReport{}, fmt.Errorf("admin allowed case: %w", err)
	}
	cases["admin_allowed"] = toCaseOut(admin)

	readonlyDenied, err := model.Resolve(ctx, lookup(readonlyExternalRef, readonlyTokenID, registry.PermissionRegistryImportReplace, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve readonly denied: %w", err)
	}
	if err := requireDenied(readonlyDenied, registry.HostedPermissionDecisionDenied, registry.HostedPermissionErrorPublicAuthzDenied, registry.HostedPermissionDenyMissingEndpointPermission); err != nil {
		return dogfoodReport{}, fmt.Errorf("readonly missing permission case: %w", err)
	}
	cases["readonly_missing_permission"] = toCaseOut(readonlyDenied)

	missingMembership, err := model.Resolve(ctx, lookup(noMembershipExternalRef, noMembershipTokenID, registry.PermissionRegistryValidate, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve missing membership: %w", err)
	}
	if err := requireDenied(missingMembership, registry.HostedPermissionDecisionDenied, registry.HostedPermissionErrorPublicAuthzDenied, registry.HostedPermissionDenyMissingMembership); err != nil {
		return dogfoodReport{}, fmt.Errorf("missing membership case: %w", err)
	}
	cases["missing_membership"] = toCaseOut(missingMembership)

	suspended, err := model.Resolve(ctx, lookup(suspendedExternalRef, suspendedTokenID, registry.PermissionRegistryValidate, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve suspended membership: %w", err)
	}
	if err := requireDenied(suspended, registry.HostedPermissionDecisionDenied, registry.HostedPermissionErrorPublicAuthzDenied, registry.HostedPermissionDenyMembershipInactive); err != nil {
		return dogfoodReport{}, fmt.Errorf("suspended membership case: %w", err)
	}
	cases["suspended_membership"] = toCaseOut(suspended)

	revoked, err := model.Resolve(ctx, lookup(revokedExternalRef, revokedTokenID, registry.PermissionRegistryValidate, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve revoked grant: %w", err)
	}
	if err := requireDenied(revoked, registry.HostedPermissionDecisionDenied, registry.HostedPermissionErrorPublicAuthzDenied, registry.HostedPermissionDenyMissingEndpointPermission); err != nil {
		return dogfoodReport{}, fmt.Errorf("revoked grant case: %w", err)
	}
	cases["revoked_grant"] = toCaseOut(revoked)

	if _, err := db.ExecContext(ctx, "UPDATE hosted_policy_versions SET status = 'superseded' WHERE status = 'active'"); err != nil {
		return dogfoodReport{}, fmt.Errorf("disable active policy: %w", err)
	}
	noActivePolicy, err := model.Resolve(ctx, lookup(adminExternalRef, adminTokenID, registry.PermissionRegistryValidate, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve no active policy: %w", err)
	}
	if err := requireDenied(noActivePolicy, registry.HostedPermissionDecisionSourceUnavailable, registry.HostedPermissionErrorSourceUnavailable, registry.HostedPermissionDenyPolicyUnavailable); err != nil {
		return dogfoodReport{}, fmt.Errorf("no active policy case: %w", err)
	}
	cases["no_active_policy"] = toCaseOut(noActivePolicy)

	if _, err := db.ExecContext(ctx, "UPDATE hosted_policy_versions SET status = 'active' WHERE policy_source = $1 AND policy_version = $2", policySource, policyVersion); err != nil {
		return dogfoodReport{}, fmt.Errorf("restore active policy: %w", err)
	}
	if _, err := db.ExecContext(ctx, `
INSERT INTO hosted_policy_versions (policy_source, policy_version, policy_fingerprint, status, activated_at)
VALUES ('hosted-permission-store-secondary', 'hosted-policy-v2', 'sha256:hosted-permission-store-secondary-v2', 'active', now())`); err != nil {
		return dogfoodReport{}, fmt.Errorf("insert secondary active policy: %w", err)
	}
	ambiguousPolicy, err := model.Resolve(ctx, lookup(adminExternalRef, adminTokenID, registry.PermissionRegistryValidate, resolvedAt))
	if err != nil {
		return dogfoodReport{}, fmt.Errorf("resolve ambiguous active policy: %w", err)
	}
	if err := requireDenied(ambiguousPolicy, registry.HostedPermissionDecisionSourceUnavailable, registry.HostedPermissionErrorSourceUnavailable, registry.HostedPermissionDenyPolicyUnavailable); err != nil {
		return dogfoodReport{}, fmt.Errorf("ambiguous policy case: %w", err)
	}
	cases["ambiguous_active_policy"] = toCaseOut(ambiguousPolicy)

	var decisionRows int
	if err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM hosted_permission_decisions").Scan(&decisionRows); err != nil {
		return dogfoodReport{}, fmt.Errorf("count decision rows: %w", err)
	}
	report := dogfoodReport{
		Status:                "passed",
		Dogfood:               "go_control_plane_hosted_permission_store_read_model_live_postgres",
		Cases:                 cases,
		SecretSafeEvidence:    secretSafe(cases),
		DecisionRowsPersisted: decisionRows,
	}
	if !report.SecretSafeEvidence {
		return dogfoodReport{}, fmt.Errorf("decision evidence leaked secret-like material")
	}
	if report.DecisionRowsPersisted != 0 {
		return dogfoodReport{}, fmt.Errorf("read model persisted decision rows: %d", report.DecisionRowsPersisted)
	}
	return report, nil
}

func lookup(externalSubjectRef string, tokenID string, requiredPermission string, resolvedAt time.Time) registry.HostedPermissionLookupRequest {
	return registry.HostedPermissionLookupRequest{
		PublicPrincipalID:  strings.TrimPrefix(externalSubjectRef, "dogfood/idp/"),
		ExternalSubjectRef: externalSubjectRef,
		ProjectID:          projectID,
		TokenID:            tokenID,
		RequiredPermission: requiredPermission,
		ResolvedAt:         resolvedAt,
	}
}

func requireAllowed(decision registry.HostedPermissionDecision, requiredPermission string) error {
	if !decision.Allowed || decision.Status != registry.HostedPermissionDecisionAllowed {
		return fmt.Errorf("expected allowed 200, got %#v", decision)
	}
	if decision.ErrorType != "" || decision.DenyReason != "" {
		return fmt.Errorf("expected empty denial evidence, got %#v", decision)
	}
	if decision.PolicySource != policySource || decision.PermissionSource != policySource {
		return fmt.Errorf("unexpected policy source evidence: %#v", decision)
	}
	if decision.PolicyVersion != policyVersion || decision.PolicyFingerprint != policyFingerprint {
		return fmt.Errorf("unexpected policy version evidence: %#v", decision)
	}
	if !strings.HasPrefix(decision.DecisionID, "decision-") {
		return fmt.Errorf("missing decision id evidence: %#v", decision)
	}
	if !slices.Contains(decision.Permissions, requiredPermission) {
		return fmt.Errorf("missing required permission evidence: %#v", decision)
	}
	return nil
}

func requireDenied(decision registry.HostedPermissionDecision, status int, errorType string, denyReason string) error {
	if decision.Allowed {
		return fmt.Errorf("expected denied decision, got %#v", decision)
	}
	if decision.Status != status || decision.ErrorType != errorType || decision.DenyReason != denyReason {
		return fmt.Errorf("unexpected denial evidence: %#v", decision)
	}
	if !strings.HasPrefix(decision.DecisionID, "decision-") {
		return fmt.Errorf("missing denial decision id: %#v", decision)
	}
	return nil
}

func toCaseOut(decision registry.HostedPermissionDecision) caseOut {
	return caseOut{
		Allowed:            decision.Allowed,
		Status:             decision.Status,
		ErrorType:          decision.ErrorType,
		DenyReason:         decision.DenyReason,
		SubjectID:          decision.SubjectID,
		ActorID:            decision.ActorID,
		ProjectID:          decision.ProjectID,
		OrganizationID:     decision.OrganizationID,
		TokenID:            decision.TokenID,
		Roles:              decision.Roles,
		Permissions:        decision.Permissions,
		RequiredPermission: decision.RequiredPermission,
		PolicySource:       decision.PolicySource,
		PolicyVersion:      decision.PolicyVersion,
		PolicyFingerprint:  decision.PolicyFingerprint,
		DecisionID:         decision.DecisionID,
		ResolvedAt:         decision.ResolvedAt.UTC().Format(time.RFC3339Nano),
	}
}

func secretSafe(cases map[string]caseOut) bool {
	data, err := json.Marshal(cases)
	if err != nil {
		return false
	}
	rendered := strings.ToLower(string(data))
	forbidden := []string{
		"dogfood-public-admin-token",
		"dogfood-public-readonly-token",
		"gateway_secret",
		"gateway-secret",
		"raw_token",
		"public_token",
		"access_token",
		"refresh_token",
		"plaintext",
	}
	for _, item := range forbidden {
		if strings.Contains(rendered, item) {
			return false
		}
	}
	return true
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}
