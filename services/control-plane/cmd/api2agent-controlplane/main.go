package main

import (
	"context"
	"database/sql"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"api2agent/services/control-plane/internal/httpapi"
	"api2agent/services/control-plane/internal/registry"
	_ "github.com/jackc/pgx/v5/stdlib"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "export-snapshot":
		if err := exportSnapshot(os.Args[2:]); err != nil {
			log.Fatalf("export snapshot: %v", err)
		}
	case "export-artifact":
		if err := exportArtifact(os.Args[2:]); err != nil {
			log.Fatalf("export artifact: %v", err)
		}
	case "publish-artifact":
		if err := publishArtifact(os.Args[2:]); err != nil {
			log.Fatalf("publish artifact: %v", err)
		}
	case "seed-postgres":
		if err := seedPostgres(os.Args[2:]); err != nil {
			log.Fatalf("seed postgres: %v", err)
		}
	case "import-replace-postgres":
		if err := importReplacePostgres(os.Args[2:]); err != nil {
			log.Fatalf("import replace postgres: %v", err)
		}
	case "serve":
		if err := serve(os.Args[2:]); err != nil {
			log.Fatalf("serve: %v", err)
		}
	default:
		usage()
		os.Exit(2)
	}
}

func exportSnapshot(args []string) error {
	flags := flag.NewFlagSet("export-snapshot", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json")
	registryStore := flags.String("registry-store", defaultRegistryStore(), "registry store: file or postgres")
	postgresDSN := flags.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN for --registry-store=postgres")
	outputPath := flags.String("output", "", "path to write routing snapshot json")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *outputPath == "" {
		return fmt.Errorf("--output is required")
	}
	runtime, err := openRegistryRuntime(context.Background(), *registryStore, *registryPath, *postgresDSN)
	if err != nil {
		return err
	}
	defer runtime.Close()
	reg, err := runtime.Store.Load(context.Background())
	if err != nil {
		return err
	}
	snapshot, err := reg.ExportSnapshot()
	if err != nil {
		return err
	}
	return registry.WriteSnapshotFile(*outputPath, snapshot)
}

func exportArtifact(args []string) error {
	flags := flag.NewFlagSet("export-artifact", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json")
	registryStore := flags.String("registry-store", defaultRegistryStore(), "registry store: file or postgres")
	postgresDSN := flags.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN for --registry-store=postgres")
	outputDir := flags.String("output-dir", "", "directory to write snapshot artifact")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *outputDir == "" {
		return fmt.Errorf("--output-dir is required")
	}
	runtime, err := openRegistryRuntime(context.Background(), *registryStore, *registryPath, *postgresDSN)
	if err != nil {
		return err
	}
	defer runtime.Close()
	reg, err := runtime.Store.Load(context.Background())
	if err != nil {
		return err
	}
	snapshot, manifest, err := reg.ExportArtifact(time.Now().UTC(), runtime.StoreName, runtime.Source)
	if err != nil {
		return err
	}
	return registry.WriteArtifactDir(*outputDir, snapshot, manifest)
}

func publishArtifact(args []string) error {
	flags := flag.NewFlagSet("publish-artifact", flag.ExitOnError)
	artifactDir := flags.String("artifact-dir", "", "directory containing snapshot.json and manifest.json")
	distributionDir := flags.String("distribution-dir", "", "directory to publish current snapshot distribution")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *artifactDir == "" {
		return fmt.Errorf("--artifact-dir is required")
	}
	if *distributionDir == "" {
		return fmt.Errorf("--distribution-dir is required")
	}
	_, err := registry.PublishArtifactDir(*artifactDir, *distributionDir, time.Now().UTC())
	return err
}

func seedPostgres(args []string) error {
	flags := flag.NewFlagSet("seed-postgres", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json to seed")
	postgresDSN := flags.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *registryPath == "" {
		return fmt.Errorf("--registry is required")
	}
	if *postgresDSN == "" {
		return fmt.Errorf("--postgres-dsn is required or API2AGENT_CONTROL_PLANE_POSTGRES_DSN must be set")
	}
	reg, err := registry.LoadFile(*registryPath)
	if err != nil {
		return err
	}
	db, err := openPostgresDB(context.Background(), *postgresDSN)
	if err != nil {
		return err
	}
	defer db.Close()
	rows, err := registry.SeedPostgresRegistry(context.Background(), db, *reg)
	if err != nil {
		return err
	}
	fmt.Printf("seeded postgres registry: projects=%d api_keys=%d capabilities=%d providers=%d credentials=%d snapshot_configs=%d\n", len(rows.Projects), len(rows.APIKeys), len(rows.Capabilities), len(rows.Providers), len(rows.CredentialMetadata), len(rows.SnapshotConfigs))
	return nil
}

func importReplacePostgres(args []string) error {
	flags := flag.NewFlagSet("import-replace-postgres", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json to import/replace")
	postgresDSN := flags.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN")
	actorID := flags.String("actor-id", "local-admin", "actor id for persistent audit")
	requestID := flags.String("request-id", "", "request id for persistent audit")
	idempotencyKey := flags.String("idempotency-key", "", "optional idempotency key for persistent audit")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *registryPath == "" {
		return fmt.Errorf("--registry is required")
	}
	if *postgresDSN == "" {
		return fmt.Errorf("--postgres-dsn is required or API2AGENT_CONTROL_PLANE_POSTGRES_DSN must be set")
	}
	reg, err := registry.LoadFile(*registryPath)
	if err != nil {
		return err
	}
	db, err := openPostgresDB(context.Background(), *postgresDSN)
	if err != nil {
		return err
	}
	defer db.Close()
	result, err := registry.ReplacePersistentRegistry(context.Background(), db, *reg, registry.ImportReplaceOptions{
		ActorID:        *actorID,
		RequestID:      *requestID,
		IdempotencyKey: *idempotencyKey,
		Source:         *registryPath,
	})
	if err != nil {
		return err
	}
	fmt.Printf("import-replace postgres registry: fingerprint=%s previous=%s snapshot=%s noop=%t projects=%d api_keys=%d capabilities=%d providers=%d credentials=%d\n",
		result.RegistryFingerprint,
		result.PreviousRegistryFingerprint,
		result.SnapshotVersion,
		result.Noop,
		result.Counts.Projects,
		result.Counts.APIKeys,
		result.Counts.Capabilities,
		result.Counts.Providers,
		result.Counts.CredentialMetadata,
	)
	return nil
}

func serve(args []string) error {
	flags := flag.NewFlagSet("serve", flag.ExitOnError)
	registryPath := flags.String("registry", "", "path to control plane registry json")
	registryStore := flags.String("registry-store", defaultRegistryStore(), "registry store: file or postgres")
	postgresDSN := flags.String("postgres-dsn", os.Getenv("API2AGENT_CONTROL_PLANE_POSTGRES_DSN"), "Postgres DSN for --registry-store=postgres")
	addr := flags.String("addr", "127.0.0.1:8081", "address for the local control plane service")
	adminToken := flags.String("admin-token", os.Getenv("API2AGENT_CONTROL_PLANE_ADMIN_TOKEN"), "admin bearer token for non-health endpoints")
	adminIdentityMode := flags.String("admin-identity-mode", os.Getenv("API2AGENT_CONTROL_PLANE_ADMIN_IDENTITY_MODE"), "admin identity mode: local_private or hosted")
	adminAuthenticator := flags.String("admin-authenticator", os.Getenv("API2AGENT_CONTROL_PLANE_ADMIN_AUTHENTICATOR"), "admin authenticator mode: local_private or trusted_gateway")
	trustedGatewaySecret := flags.String("trusted-gateway-secret", os.Getenv("API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRET"), "trusted gateway secret for --admin-authenticator=trusted_gateway")
	trustedGatewaySecrets := flags.String("trusted-gateway-secrets", os.Getenv("API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_SECRETS"), "comma-separated trusted gateway secrets for rotation-compatible --admin-authenticator=trusted_gateway")
	trustedGatewayKeyID := flags.String("trusted-gateway-key-id", os.Getenv("API2AGENT_CONTROL_PLANE_TRUSTED_GATEWAY_KEY_ID"), "optional non-secret trusted gateway key id for audit evidence")
	distributionDir := flags.String("distribution-dir", "", "optional local snapshot distribution directory")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if requiresLocalAdminToken(*adminIdentityMode, *adminAuthenticator) && *adminToken == "" {
		return fmt.Errorf("--admin-token is required or API2AGENT_CONTROL_PLANE_ADMIN_TOKEN must be set")
	}
	runtime, err := openRegistryRuntime(context.Background(), *registryStore, *registryPath, *postgresDSN)
	if err != nil {
		return err
	}
	defer runtime.Close()
	mux := http.NewServeMux()
	handler := httpapi.Handler{
		Store:                    runtime.Store,
		AuditSink:                runtime.AuditSink,
		ImportReplacer:           runtime.ImportReplacer,
		ProjectPartitionReplacer: runtime.ProjectPartitionReplacer,
		HostedPolicyMutator:      runtime.HostedPolicyMutator,
		RegistryStore:            runtime.StoreName,
		RegistrySource:           runtime.Source,
		DistributionDir:          *distributionDir,
		AdminToken:               *adminToken,
		AdminIdentityMode:        *adminIdentityMode,
		AdminAuthenticatorMode:   *adminAuthenticator,
		TrustedGatewaySecret:     *trustedGatewaySecret,
		TrustedGatewaySecrets:    parseTrustedGatewaySecrets(*trustedGatewaySecrets),
		TrustedGatewayKeyID:      *trustedGatewayKeyID,
	}
	handler.Register(mux)
	log.Printf("api2agent control plane listening on %s", *addr)
	return http.ListenAndServe(*addr, mux)
}

func requiresLocalAdminToken(identityMode string, authenticatorMode string) bool {
	identityMode = strings.TrimSpace(identityMode)
	authenticatorMode = strings.TrimSpace(authenticatorMode)
	if identityMode == "" {
		identityMode = httpapi.AdminIdentityModeLocalPrivate
	}
	if authenticatorMode == "" {
		return identityMode == httpapi.AdminIdentityModeLocalPrivate
	}
	return authenticatorMode == httpapi.AdminAuthenticatorModeLocalPrivate
}

func parseTrustedGatewaySecrets(raw string) []string {
	var secrets []string
	seen := map[string]struct{}{}
	for _, part := range strings.Split(raw, ",") {
		secret := strings.TrimSpace(part)
		if secret == "" {
			continue
		}
		if _, ok := seen[secret]; ok {
			continue
		}
		seen[secret] = struct{}{}
		secrets = append(secrets, secret)
	}
	return secrets
}

type registryRuntime struct {
	Store                    registry.Store
	AuditSink                registry.PersistentAuditSink
	ImportReplacer           httpapi.RegistryImportReplacer
	ProjectPartitionReplacer httpapi.RegistryProjectPartitionReplacer
	HostedPolicyMutator      httpapi.HostedPermissionPolicyMutator
	StoreName                string
	Source                   string
	close                    func() error
}

func (r registryRuntime) Close() error {
	if r.close == nil {
		return nil
	}
	return r.close()
}

func defaultRegistryStore() string {
	value := os.Getenv("API2AGENT_CONTROL_PLANE_REGISTRY_STORE")
	if value == "" {
		return "file"
	}
	return value
}

func openRegistryRuntime(ctx context.Context, storeName string, registryPath string, postgresDSN string) (registryRuntime, error) {
	switch storeName {
	case "", "file":
		if registryPath == "" {
			return registryRuntime{}, fmt.Errorf("--registry is required when --registry-store=file")
		}
		return registryRuntime{
			Store:     registry.NewFileStore(registryPath),
			StoreName: "file",
			Source:    registryPath,
		}, nil
	case "postgres":
		if postgresDSN == "" {
			return registryRuntime{}, fmt.Errorf("--postgres-dsn is required when --registry-store=postgres or API2AGENT_CONTROL_PLANE_POSTGRES_DSN must be set")
		}
		db, err := openPostgresDBForRuntime(ctx, postgresDSN)
		if err != nil {
			return registryRuntime{}, err
		}
		return registryRuntime{
			Store:                    registry.NewPostgresStore(db),
			AuditSink:                registry.NewPostgresAuditSink(db),
			ImportReplacer:           postgresRegistryImportReplacer{db: db},
			ProjectPartitionReplacer: postgresRegistryProjectPartitionReplacer{db: db},
			HostedPolicyMutator:      postgresHostedPermissionPolicyMutator{db: db},
			StoreName:                "postgres",
			Source:                   "postgres",
			close:                    db.Close,
		}, nil
	default:
		return registryRuntime{}, fmt.Errorf("--registry-store must be file or postgres")
	}
}

type postgresRegistryImportReplacer struct {
	db *sql.DB
}

func (r postgresRegistryImportReplacer) ReplacePersistentRegistry(ctx context.Context, reg registry.Registry, opts registry.ImportReplaceOptions) (registry.ImportReplaceResult, error) {
	return registry.ReplacePersistentRegistry(ctx, r.db, reg, opts)
}

type postgresRegistryProjectPartitionReplacer struct {
	db *sql.DB
}

func (r postgresRegistryProjectPartitionReplacer) ReplaceProjectPartitionRegistry(ctx context.Context, reg registry.Registry, opts registry.ProjectPartitionReplaceOptions) (registry.ProjectPartitionReplaceResult, error) {
	return registry.ReplaceProjectPartitionRegistry(ctx, r.db, reg, opts)
}

type postgresHostedPermissionPolicyMutator struct {
	db *sql.DB
}

var _ httpapi.HostedPermissionPolicyMutator = postgresHostedPermissionPolicyMutator{}

func (m postgresHostedPermissionPolicyMutator) BeginHostedPermissionPolicyDraft(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	return registry.BeginHostedPermissionPolicyDraft(ctx, m.db, opts)
}

func (m postgresHostedPermissionPolicyMutator) ApplyHostedPermissionPolicyDraftChange(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions, change registry.HostedPermissionPolicyDraftChange) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	return registry.ApplyHostedPermissionPolicyDraftChange(ctx, m.db, opts, change)
}

func (m postgresHostedPermissionPolicyMutator) RequestHostedPermissionPolicyReview(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	return registry.RequestHostedPermissionPolicyReview(ctx, m.db, opts)
}

func (m postgresHostedPermissionPolicyMutator) PromoteHostedPermissionPolicyDraft(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	return registry.PromoteHostedPermissionPolicyDraft(ctx, m.db, opts)
}

func (m postgresHostedPermissionPolicyMutator) RollbackHostedPermissionPolicy(ctx context.Context, opts registry.HostedPermissionPolicyMutationOptions) (registry.HostedPermissionPolicyMutationDurableResult, error) {
	return registry.RollbackHostedPermissionPolicy(ctx, m.db, opts)
}

func openPostgresDB(ctx context.Context, dsn string) (*sql.DB, error) {
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		return nil, fmt.Errorf("open postgres registry db: %w", err)
	}
	if err := db.PingContext(ctx); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("connect postgres registry db: %w", err)
	}
	return db, nil
}

var openPostgresDBForRuntime = openPostgresDB

func usage() {
	fmt.Fprintln(os.Stderr, "usage:")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane export-snapshot --registry <registry.json> --output <snapshot.json> [--registry-store file|postgres] [--postgres-dsn <dsn>]")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane export-artifact --registry <registry.json> --output-dir <artifact-dir> [--registry-store file|postgres] [--postgres-dsn <dsn>]")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane publish-artifact --artifact-dir <artifact-dir> --distribution-dir <distribution-dir>")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane seed-postgres --registry <registry.json> --postgres-dsn <dsn>")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane import-replace-postgres --registry <registry.json> --postgres-dsn <dsn> [--actor-id <actor>] [--request-id <request-id>] [--idempotency-key <key>]")
	fmt.Fprintln(os.Stderr, "  api2agent-controlplane serve --registry <registry.json> [--admin-token <token>] [--registry-store file|postgres] [--postgres-dsn <dsn>] [--addr <addr>] [--distribution-dir <dir>] [--admin-identity-mode local_private|hosted] [--admin-authenticator local_private|trusted_gateway] [--trusted-gateway-secret <secret>] [--trusted-gateway-secrets <secret-a,secret-b>] [--trusted-gateway-key-id <key-id>]")
}
