package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	"api2agent/services/control-plane/internal/registry"
	_ "github.com/jackc/pgx/v5/stdlib"
)

type decisionOut struct {
	Allowed            bool     `json:"allowed"`
	Status             int      `json:"status"`
	ErrorType          string   `json:"error_type"`
	DenyReason         string   `json:"deny_reason"`
	SubjectID          string   `json:"subject_id"`
	ActorID            string   `json:"actor_id"`
	ProjectID          string   `json:"project_id"`
	OrganizationID     string   `json:"organization_id"`
	TokenID            string   `json:"token_id"`
	Roles              []string `json:"roles"`
	Permissions        []string `json:"permissions"`
	RequiredPermission string   `json:"required_permission"`
	PolicySource       string   `json:"policy_source"`
	PolicyVersion      string   `json:"policy_version"`
	PolicyFingerprint  string   `json:"policy_fingerprint"`
	DecisionID         string   `json:"decision_id"`
	PermissionSource   string   `json:"permission_source"`
	ResolvedAt         string   `json:"resolved_at"`
}

func main() {
	postgresDSN := flag.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN")
	publicPrincipalID := flag.String("public-principal-id", "", "Public principal ID evidence")
	externalSubjectRef := flag.String("external-subject-ref", "", "External subject reference")
	projectID := flag.String("project-id", "", "Project authorization scope")
	tokenID := flag.String("token-id", "", "Token ID evidence")
	requiredPermission := flag.String("required-permission", "", "Required endpoint permission")
	resolvedAtText := flag.String("resolved-at", "", "RFC3339 decision time")
	flag.Parse()

	if *postgresDSN == "" {
		fail("postgres dsn is required")
	}
	if *projectID == "" || *requiredPermission == "" {
		fail("project id and required permission are required")
	}

	resolvedAt := time.Now().UTC()
	if *resolvedAtText != "" {
		parsed, err := time.Parse(time.RFC3339, *resolvedAtText)
		if err != nil {
			fail("parse resolved-at: %v", err)
		}
		resolvedAt = parsed.UTC()
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

	decision, err := registry.NewHostedPermissionReadModel(db).Resolve(ctx, registry.HostedPermissionLookupRequest{
		PublicPrincipalID:  *publicPrincipalID,
		ExternalSubjectRef: *externalSubjectRef,
		ProjectID:          *projectID,
		TokenID:            *tokenID,
		RequiredPermission: *requiredPermission,
		ResolvedAt:         resolvedAt,
	})
	if err != nil {
		fail("resolve hosted permission: %v", err)
	}

	data, err := json.Marshal(toDecisionOut(decision))
	if err != nil {
		fail("marshal decision: %v", err)
	}
	fmt.Println(string(data))
}

func toDecisionOut(decision registry.HostedPermissionDecision) decisionOut {
	return decisionOut{
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
		PermissionSource:   decision.PermissionSource,
		ResolvedAt:         decision.ResolvedAt.UTC().Format(time.RFC3339Nano),
	}
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}
