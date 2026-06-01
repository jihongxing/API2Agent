package registry

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"fmt"
	"reflect"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"
)

const (
	hostedTestSubjectID      = "gateway-harness-principal"
	hostedTestExternalRef    = "dogfood/idp/admin"
	hostedTestActorID        = "gateway-harness-actor"
	hostedTestProjectID      = "gateway-harness-project"
	hostedTestOrganizationID = "gateway-harness-org"
	hostedTestTokenID        = "gateway-harness-token-admin"
	hostedTestPolicySource   = "hosted-permission-store-fixture"
	hostedTestPolicyVersion  = "hosted-policy-v1"
	hostedTestFingerprint    = "sha256:hosted-permission-store-fixture-v1"
)

func TestHostedPermissionReadModelAllowsActiveGrantAndEvidence(t *testing.T) {
	db, script := openHostedPermissionScriptedDB(t, hostedPermissionBaseRows())
	defer db.Close()

	resolvedAt := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	decision, err := NewHostedPermissionReadModel(db).Resolve(context.Background(), hostedPermissionLookupRequest(PermissionRegistryImportReplace, resolvedAt))
	if err != nil {
		t.Fatalf("resolve hosted permission: %v", err)
	}

	if !script.beginCalled {
		t.Fatalf("expected read transaction to begin")
	}
	if script.beginOptions.Isolation != driver.IsolationLevel(sql.LevelRepeatableRead) {
		t.Fatalf("unexpected isolation level: %#v", script.beginOptions)
	}
	if !script.beginOptions.ReadOnly {
		t.Fatalf("expected read-only transaction")
	}
	if !script.committed {
		t.Fatalf("expected transaction commit")
	}
	if script.rolledBack {
		t.Fatalf("did not expect rollback after successful read")
	}
	if len(script.execQueries) != 0 {
		t.Fatalf("read model must not write hosted decisions in v0: %#v", script.execQueries)
	}

	if !decision.Allowed || decision.Status != HostedPermissionDecisionAllowed || decision.ErrorType != "" {
		t.Fatalf("expected allowed decision, got %#v", decision)
	}
	if decision.SubjectID != hostedTestSubjectID || decision.ActorID != hostedTestActorID || decision.ProjectID != hostedTestProjectID || decision.OrganizationID != hostedTestOrganizationID {
		t.Fatalf("unexpected identity evidence: %#v", decision)
	}
	if decision.TokenID != hostedTestTokenID {
		t.Fatalf("expected token id evidence without raw token, got %#v", decision)
	}
	if !reflect.DeepEqual(decision.Roles, []string{"control-plane-admin", "dogfood"}) {
		t.Fatalf("unexpected roles: %#v", decision.Roles)
	}
	if !slices.Contains(decision.Permissions, PermissionRegistryImportReplace) || !slices.Contains(decision.Permissions, PermissionRegistryProjectPartitionReplace) {
		t.Fatalf("unexpected permissions: %#v", decision.Permissions)
	}
	if decision.PolicySource != hostedTestPolicySource || decision.PermissionSource != hostedTestPolicySource {
		t.Fatalf("unexpected policy source evidence: %#v", decision)
	}
	if decision.PolicyVersion != hostedTestPolicyVersion || decision.PolicyFingerprint != hostedTestFingerprint {
		t.Fatalf("unexpected policy version evidence: %#v", decision)
	}
	expectedDecisionID := hostedPermissionDecisionID(hostedTestSubjectID, hostedTestProjectID, PermissionRegistryImportReplace, hostedTestPolicyVersion, resolvedAt)
	if decision.DecisionID != expectedDecisionID || !strings.HasPrefix(decision.DecisionID, "decision-") {
		t.Fatalf("unexpected decision id: %q want %q", decision.DecisionID, expectedDecisionID)
	}
}

func TestHostedPermissionReadModelFailClosedCases(t *testing.T) {
	resolvedAt := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	tests := []struct {
		name       string
		rows       hostedPermissionScriptRows
		wantStatus int
		wantError  string
		wantReason string
		wantRoles  []string
	}{
		{
			name:       "missing membership",
			rows:       hostedPermissionRowsWithoutMembership(),
			wantStatus: HostedPermissionDecisionDenied,
			wantError:  HostedPermissionErrorPublicAuthzDenied,
			wantReason: HostedPermissionDenyMissingMembership,
		},
		{
			name:       "suspended membership",
			rows:       hostedPermissionRowsWithMembershipStatus("suspended"),
			wantStatus: HostedPermissionDecisionDenied,
			wantError:  HostedPermissionErrorPublicAuthzDenied,
			wantReason: HostedPermissionDenyMembershipInactive,
		},
		{
			name:       "revoked grant",
			rows:       hostedPermissionRowsWithGrantStatus(PermissionRegistryImportReplace, "revoked"),
			wantStatus: HostedPermissionDecisionDenied,
			wantError:  HostedPermissionErrorPublicAuthzDenied,
			wantReason: HostedPermissionDenyMissingEndpointPermission,
			wantRoles:  []string{"control-plane-admin", "dogfood"},
		},
		{
			name:       "missing permission",
			rows:       hostedPermissionRowsWithoutPermission(PermissionRegistryImportReplace),
			wantStatus: HostedPermissionDecisionDenied,
			wantError:  HostedPermissionErrorPublicAuthzDenied,
			wantReason: HostedPermissionDenyMissingEndpointPermission,
			wantRoles:  []string{"control-plane-admin", "dogfood"},
		},
		{
			name:       "no active policy",
			rows:       hostedPermissionRowsWithPolicyStatus("superseded"),
			wantStatus: HostedPermissionDecisionSourceUnavailable,
			wantError:  HostedPermissionErrorSourceUnavailable,
			wantReason: HostedPermissionDenyPolicyUnavailable,
		},
		{
			name:       "ambiguous active policy",
			rows:       hostedPermissionRowsWithAmbiguousPolicy(),
			wantStatus: HostedPermissionDecisionSourceUnavailable,
			wantError:  HostedPermissionErrorSourceUnavailable,
			wantReason: HostedPermissionDenyPolicyUnavailable,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			db, script := openHostedPermissionScriptedDB(t, tt.rows)
			defer db.Close()

			decision, err := NewHostedPermissionReadModel(db).Resolve(context.Background(), hostedPermissionLookupRequest(PermissionRegistryImportReplace, resolvedAt))
			if err != nil {
				t.Fatalf("resolve hosted permission: %v", err)
			}
			if decision.Allowed {
				t.Fatalf("expected fail-closed decision, got %#v", decision)
			}
			if decision.Status != tt.wantStatus || decision.ErrorType != tt.wantError || decision.DenyReason != tt.wantReason {
				t.Fatalf("unexpected denial: %#v", decision)
			}
			if len(tt.wantRoles) > 0 && !reflect.DeepEqual(decision.Roles, tt.wantRoles) {
				t.Fatalf("unexpected role evidence: %#v", decision.Roles)
			}
			if slices.Contains(decision.Permissions, PermissionRegistryImportReplace) && tt.name != "ambiguous active policy" {
				t.Fatalf("denied decision must not expose revoked/missing required permission: %#v", decision.Permissions)
			}
			if !script.committed {
				t.Fatalf("expected deny decision transaction to commit")
			}
			if len(script.execQueries) != 0 {
				t.Fatalf("read model must not write on denial: %#v", script.execQueries)
			}
		})
	}
}

func TestHostedPermissionReadModelEvidenceDoesNotCarryRawSecrets(t *testing.T) {
	db, _ := openHostedPermissionScriptedDB(t, hostedPermissionBaseRows())
	defer db.Close()

	req := hostedPermissionLookupRequest(PermissionRegistryValidate, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	req.PublicPrincipalID = "raw-public-token-should-not-appear"
	decision, err := NewHostedPermissionReadModel(db).Resolve(context.Background(), req)
	if err != nil {
		t.Fatalf("resolve hosted permission: %v", err)
	}

	rendered := fmt.Sprintf("%#v", decision)
	forbidden := []string{
		"raw-public-token-should-not-appear",
		"gateway_secret",
		"raw_token",
		"public_token",
		"access_token",
		"refresh_token",
		"plaintext",
	}
	for _, item := range forbidden {
		if strings.Contains(strings.ToLower(rendered), item) {
			t.Fatalf("hosted permission decision leaked secret-like evidence %q in %#v", item, decision)
		}
	}
}

func TestHostedPermissionReadModelRequiresDB(t *testing.T) {
	_, err := NewHostedPermissionReadModel(nil).Resolve(context.Background(), HostedPermissionLookupRequest{})
	if err == nil {
		t.Fatalf("expected missing db error")
	}
	if !strings.Contains(err.Error(), "hosted permission db is required") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func hostedPermissionLookupRequest(requiredPermission string, resolvedAt time.Time) HostedPermissionLookupRequest {
	return HostedPermissionLookupRequest{
		PublicPrincipalID:  "public-admin",
		ExternalSubjectRef: hostedTestExternalRef,
		ProjectID:          hostedTestProjectID,
		TokenID:            hostedTestTokenID,
		RequiredPermission: requiredPermission,
		ResolvedAt:         resolvedAt,
	}
}

type hostedPermissionScriptRows struct {
	subjects    []hostedPermissionScriptSubject
	memberships []hostedPermissionScriptMembership
	roles       []hostedPermissionScriptRole
	bindings    []hostedPermissionScriptBinding
	grants      []hostedPermissionScriptGrant
	policies    []hostedPermissionScriptPolicy
}

type hostedPermissionScriptSubject struct {
	id                 string
	externalSubjectRef string
	status             string
}

type hostedPermissionScriptMembership struct {
	subjectID      string
	actorID        string
	projectID      string
	organizationID string
	status         string
}

type hostedPermissionScriptRole struct {
	id     string
	status string
}

type hostedPermissionScriptBinding struct {
	subjectID      string
	projectID      string
	organizationID string
	roleID         string
	status         string
}

type hostedPermissionScriptGrant struct {
	roleID     string
	permission string
	status     string
}

type hostedPermissionScriptPolicy struct {
	source      string
	version     string
	fingerprint string
	status      string
}

func hostedPermissionBaseRows() hostedPermissionScriptRows {
	return hostedPermissionScriptRows{
		subjects: []hostedPermissionScriptSubject{
			{id: hostedTestSubjectID, externalSubjectRef: hostedTestExternalRef, status: "active"},
		},
		memberships: []hostedPermissionScriptMembership{
			{subjectID: hostedTestSubjectID, actorID: hostedTestActorID, projectID: hostedTestProjectID, organizationID: hostedTestOrganizationID, status: "active"},
		},
		roles: []hostedPermissionScriptRole{
			{id: "control-plane-admin", status: "active"},
			{id: "dogfood", status: "active"},
		},
		bindings: []hostedPermissionScriptBinding{
			{subjectID: hostedTestSubjectID, projectID: hostedTestProjectID, organizationID: hostedTestOrganizationID, roleID: "control-plane-admin", status: "active"},
			{subjectID: hostedTestSubjectID, projectID: hostedTestProjectID, organizationID: hostedTestOrganizationID, roleID: "dogfood", status: "active"},
		},
		grants: []hostedPermissionScriptGrant{
			{roleID: "control-plane-admin", permission: PermissionRegistryValidate, status: "active"},
			{roleID: "control-plane-admin", permission: PermissionRegistryImportReplace, status: "active"},
			{roleID: "control-plane-admin", permission: PermissionRegistryProjectPartitionReplace, status: "active"},
			{roleID: "control-plane-admin", permission: PermissionSnapshotExportArtifact, status: "active"},
			{roleID: "control-plane-admin", permission: PermissionDistributionPublish, status: "active"},
			{roleID: "control-plane-admin", permission: PermissionDistributionReadCurrent, status: "active"},
		},
		policies: []hostedPermissionScriptPolicy{
			{source: hostedTestPolicySource, version: hostedTestPolicyVersion, fingerprint: hostedTestFingerprint, status: "active"},
		},
	}
}

func hostedPermissionRowsWithoutMembership() hostedPermissionScriptRows {
	rows := hostedPermissionBaseRows()
	rows.memberships = nil
	rows.bindings = nil
	return rows
}

func hostedPermissionRowsWithMembershipStatus(status string) hostedPermissionScriptRows {
	rows := hostedPermissionBaseRows()
	rows.memberships[0].status = status
	return rows
}

func hostedPermissionRowsWithGrantStatus(permission string, status string) hostedPermissionScriptRows {
	rows := hostedPermissionBaseRows()
	for i := range rows.grants {
		if rows.grants[i].permission == permission {
			rows.grants[i].status = status
		}
	}
	return rows
}

func hostedPermissionRowsWithoutPermission(permission string) hostedPermissionScriptRows {
	rows := hostedPermissionBaseRows()
	filtered := rows.grants[:0]
	for _, grant := range rows.grants {
		if grant.permission != permission {
			filtered = append(filtered, grant)
		}
	}
	rows.grants = filtered
	return rows
}

func hostedPermissionRowsWithPolicyStatus(status string) hostedPermissionScriptRows {
	rows := hostedPermissionBaseRows()
	rows.policies[0].status = status
	return rows
}

func hostedPermissionRowsWithAmbiguousPolicy() hostedPermissionScriptRows {
	rows := hostedPermissionBaseRows()
	rows.policies = append(rows.policies, hostedPermissionScriptPolicy{
		source:      "hosted-permission-store-secondary",
		version:     "hosted-policy-v2",
		fingerprint: "sha256:secondary",
		status:      "active",
	})
	return rows
}

func openHostedPermissionScriptedDB(t *testing.T, rows hostedPermissionScriptRows) (*sql.DB, *hostedPermissionScript) {
	t.Helper()
	registerHostedPermissionScriptedDriverOnce()
	script := &hostedPermissionScript{rows: rows}
	hostedPermissionScriptMu.Lock()
	hostedPermissionScriptNext = script
	hostedPermissionScriptMu.Unlock()
	db, err := sql.Open(hostedPermissionScriptedDriverName, "hosted-permission")
	if err != nil {
		t.Fatalf("open scripted db: %v", err)
	}
	return db, script
}

const hostedPermissionScriptedDriverName = "api2agent_hosted_permission_scripted"

var (
	hostedPermissionScriptRegisterOnce sync.Once
	hostedPermissionScriptMu           sync.Mutex
	hostedPermissionScriptNext         *hostedPermissionScript
)

func registerHostedPermissionScriptedDriverOnce() {
	hostedPermissionScriptRegisterOnce.Do(func() {
		sql.Register(hostedPermissionScriptedDriverName, hostedPermissionDriver{})
	})
}

type hostedPermissionScript struct {
	rows         hostedPermissionScriptRows
	beginCalled  bool
	beginOptions driver.TxOptions
	committed    bool
	rolledBack   bool
	execQueries  []string
}

type hostedPermissionDriver struct{}

func (hostedPermissionDriver) Open(name string) (driver.Conn, error) {
	hostedPermissionScriptMu.Lock()
	defer hostedPermissionScriptMu.Unlock()
	if hostedPermissionScriptNext == nil {
		return nil, fmt.Errorf("scripted hosted permission db was not configured")
	}
	script := hostedPermissionScriptNext
	hostedPermissionScriptNext = nil
	return &hostedPermissionConn{script: script}, nil
}

type hostedPermissionConn struct {
	script *hostedPermissionScript
}

func (c *hostedPermissionConn) Prepare(query string) (driver.Stmt, error) {
	return nil, errors.New("prepare is not supported")
}

func (c *hostedPermissionConn) Close() error {
	return nil
}

func (c *hostedPermissionConn) Begin() (driver.Tx, error) {
	return c.BeginTx(context.Background(), driver.TxOptions{})
}

func (c *hostedPermissionConn) BeginTx(ctx context.Context, opts driver.TxOptions) (driver.Tx, error) {
	c.script.beginCalled = true
	c.script.beginOptions = opts
	return &hostedPermissionTx{script: c.script}, nil
}

func (c *hostedPermissionConn) QueryContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	if strings.Contains(query, "INSERT INTO") || strings.Contains(query, "UPDATE ") || strings.Contains(query, "DELETE FROM") {
		c.script.execQueries = append(c.script.execQueries, query)
	}
	switch {
	case strings.Contains(query, "FROM hosted_policy_versions"):
		return newScriptedRows([]string{"policy_source", "policy_version", "policy_fingerprint"}, c.policyValues()), nil
	case strings.Contains(query, "FROM hosted_subjects"):
		return newScriptedRows([]string{"id", "status"}, c.subjectValues(namedString(args, 0))), nil
	case strings.Contains(query, "FROM hosted_project_memberships"):
		return newScriptedRows([]string{"actor_id", "project_id", "organization_id", "status"}, c.membershipValues(namedString(args, 0), namedString(args, 1))), nil
	case strings.Contains(query, "FROM hosted_role_bindings") && strings.Contains(query, "hosted_permission_grants"):
		return newScriptedRows([]string{"permission"}, c.permissionValues(namedString(args, 0), namedString(args, 1), namedString(args, 2))), nil
	case strings.Contains(query, "FROM hosted_role_bindings"):
		return newScriptedRows([]string{"id"}, c.roleValues(namedString(args, 0), namedString(args, 1), namedString(args, 2))), nil
	default:
		return nil, fmt.Errorf("unexpected hosted permission query: %s", query)
	}
}

func (c *hostedPermissionConn) policyValues() [][]driver.Value {
	out := [][]driver.Value{}
	for _, policy := range c.script.rows.policies {
		if policy.status == "active" {
			out = append(out, []driver.Value{policy.source, policy.version, policy.fingerprint})
		}
	}
	return out
}

func (c *hostedPermissionConn) subjectValues(externalSubjectRef string) [][]driver.Value {
	out := [][]driver.Value{}
	for _, subject := range c.script.rows.subjects {
		if subject.externalSubjectRef == externalSubjectRef {
			out = append(out, []driver.Value{subject.id, subject.status})
		}
	}
	return out
}

func (c *hostedPermissionConn) membershipValues(subjectID string, projectID string) [][]driver.Value {
	out := [][]driver.Value{}
	for _, membership := range c.script.rows.memberships {
		if membership.subjectID == subjectID && membership.projectID == projectID {
			out = append(out, []driver.Value{membership.actorID, membership.projectID, membership.organizationID, membership.status})
		}
	}
	return out
}

func (c *hostedPermissionConn) roleValues(subjectID string, projectID string, organizationID string) [][]driver.Value {
	roleStatus := map[string]string{}
	for _, role := range c.script.rows.roles {
		roleStatus[role.id] = role.status
	}
	out := [][]driver.Value{}
	for _, binding := range c.script.rows.bindings {
		if binding.subjectID == subjectID && binding.projectID == projectID && binding.organizationID == organizationID && binding.status == "active" && roleStatus[binding.roleID] == "active" {
			out = append(out, []driver.Value{binding.roleID})
		}
	}
	slices.SortFunc(out, func(left []driver.Value, right []driver.Value) int {
		return strings.Compare(left[0].(string), right[0].(string))
	})
	return out
}

func (c *hostedPermissionConn) permissionValues(subjectID string, projectID string, organizationID string) [][]driver.Value {
	activeRoles := map[string]bool{}
	for _, values := range c.roleValues(subjectID, projectID, organizationID) {
		activeRoles[values[0].(string)] = true
	}
	permissions := map[string]bool{}
	for _, grant := range c.script.rows.grants {
		if activeRoles[grant.roleID] && grant.status == "active" {
			permissions[grant.permission] = true
		}
	}
	out := [][]driver.Value{}
	for permission := range permissions {
		out = append(out, []driver.Value{permission})
	}
	slices.SortFunc(out, func(left []driver.Value, right []driver.Value) int {
		return strings.Compare(left[0].(string), right[0].(string))
	})
	return out
}

type hostedPermissionTx struct {
	script *hostedPermissionScript
}

func (tx *hostedPermissionTx) Commit() error {
	tx.script.committed = true
	return nil
}

func (tx *hostedPermissionTx) Rollback() error {
	tx.script.rolledBack = true
	return nil
}
