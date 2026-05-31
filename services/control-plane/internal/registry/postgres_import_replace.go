package registry

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
)

type ImportReplaceOptions struct {
	ProjectID      string
	SubjectID      string
	ActorID        string
	OrganizationID string
	AuthMethod     string
	TokenID        string
	LocalPrivate   bool
	RequestID      string
	IdempotencyKey string
	Source         string
}

type ImportReplaceCounts struct {
	Projects           int `json:"projects"`
	APIKeys            int `json:"api_keys"`
	Capabilities       int `json:"capabilities"`
	Providers          int `json:"providers"`
	CredentialMetadata int `json:"credential_metadata"`
	RoutingPolicies    int `json:"routing_policies"`
	SnapshotConfigs    int `json:"snapshot_configs"`
}

type ImportReplaceResult struct {
	RegistryFingerprint         string              `json:"registry_fingerprint"`
	PreviousRegistryFingerprint string              `json:"previous_registry_fingerprint,omitempty"`
	SnapshotVersion             string              `json:"snapshot_version"`
	Noop                        bool                `json:"noop"`
	Counts                      ImportReplaceCounts `json:"counts"`
	Replayed                    bool                `json:"-"`
	IdempotencyRecordID         int64               `json:"-"`
}

type RegistryMutationError struct {
	ErrorType  string
	Scope      string
	Retryable  bool
	Underlying error
}

func (e RegistryMutationError) Error() string {
	if e.Underlying == nil {
		return e.ErrorType
	}
	return e.ErrorType + ": " + e.Underlying.Error()
}

func (e RegistryMutationError) Unwrap() error {
	return e.Underlying
}

func ReplacePersistentRegistry(ctx context.Context, db *sql.DB, reg Registry, opts ImportReplaceOptions) (ImportReplaceResult, error) {
	if db == nil {
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("postgres registry db is required"))
	}
	prepared, rows, err := prepareImportReplaceRows(reg)
	if err != nil {
		return ImportReplaceResult{}, mutationError("REGISTRY_MUTATION_INVALID", "caller", false, err)
	}
	incomingFingerprint, err := prepared.Fingerprint()
	if err != nil {
		return ImportReplaceResult{}, mutationError("REGISTRY_MUTATION_INVALID", "caller", false, err)
	}
	counts := importReplaceCounts(rows)
	result := ImportReplaceResult{
		RegistryFingerprint: incomingFingerprint,
		SnapshotVersion:     prepared.Snapshot.Version,
		Counts:              counts,
	}
	idempotency, err := newImportReplaceIdempotencyRequest(opts, incomingFingerprint)
	if err != nil {
		return ImportReplaceResult{}, mutationError("REGISTRY_MUTATION_INVALID", "caller", false, err)
	}

	tx, err := db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelSerializable,
		ReadOnly:  false,
	})
	if err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_WRITE_FAILED", incomingFingerprint, "")
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("begin registry import/replace transaction: %w", err))
	}
	committed := false
	defer func() {
		if !committed {
			_ = tx.Rollback()
		}
	}()

	idempotencyRecord, replay, err := reserveImportReplaceIdempotency(ctx, tx, idempotency)
	if err != nil {
		return ImportReplaceResult{}, err
	}
	if replay {
		if err := tx.Commit(); err != nil {
			return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit registry import/replace replay: %w", err))
		}
		committed = true
		return idempotencyRecord.Result, nil
	}
	result.IdempotencyRecordID = idempotencyRecord.ID

	locked, err := acquireRegistryMutationLock(ctx, tx)
	if err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_WRITE_FAILED", incomingFingerprint, "")
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, err)
	}
	if !locked {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "REGISTRY_MUTATION_CONFLICT", incomingFingerprint, "")
		return ImportReplaceResult{}, mutationError("REGISTRY_MUTATION_CONFLICT", "platform", true, fmt.Errorf("registry mutation lock is already held"))
	}

	previousFingerprint, err := currentPersistentRegistryFingerprint(ctx, tx)
	if err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_READ_FAILED", incomingFingerprint, "")
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_READ_FAILED", "platform", true, err)
	}
	result.PreviousRegistryFingerprint = previousFingerprint
	if previousFingerprint != "" && previousFingerprint == incomingFingerprint {
		result.Noop = true
		auditID, err := insertImportReplaceAdminAudit(ctx, tx, opts, result, "import_replace_noop", "success", "")
		if err != nil {
			_ = recordImportReplaceFailureAudit(ctx, db, opts, "AUDIT_WRITE_FAILED", incomingFingerprint, previousFingerprint)
			return ImportReplaceResult{}, mutationError("AUDIT_WRITE_FAILED", "platform", true, err)
		}
		if err := completeImportReplaceIdempotency(ctx, tx, idempotencyRecord, result, 0, auditID); err != nil {
			_ = recordImportReplaceFailureAudit(ctx, db, opts, "IDEMPOTENCY_STORE_WRITE_FAILED", incomingFingerprint, previousFingerprint)
			return ImportReplaceResult{}, err
		}
		if err := tx.Commit(); err != nil {
			_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_WRITE_FAILED", incomingFingerprint, previousFingerprint)
			return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit registry import/replace noop: %w", err))
		}
		committed = true
		return result, nil
	}

	if err := replaceMutableRegistryRows(ctx, tx, rows); err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_WRITE_FAILED", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, err)
	}
	writtenFingerprint, err := currentPersistentRegistryFingerprint(ctx, tx)
	if err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_READ_FAILED", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_READ_FAILED", "platform", true, err)
	}
	if writtenFingerprint != incomingFingerprint {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "REGISTRY_MUTATION_INVALID", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, mutationError("REGISTRY_MUTATION_INVALID", "caller", false, fmt.Errorf("written registry fingerprint %q does not match incoming fingerprint %q", writtenFingerprint, incomingFingerprint))
	}
	revisionID, err := insertRegistryRevisionTx(ctx, tx, PersistentRegistryRevisionRow{
		RegistryFingerprint: incomingFingerprint,
		SnapshotVersion:     prepared.Snapshot.Version,
		SourceStore:         "postgres",
		SourceRevision:      importReplaceSourceRevision(opts),
	}, opts.ActorID)
	if err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "AUDIT_WRITE_FAILED", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, mutationError("AUDIT_WRITE_FAILED", "platform", true, err)
	}
	auditID, err := insertImportReplaceAdminAudit(ctx, tx, opts, result, "import_replace", "success", "")
	if err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "AUDIT_WRITE_FAILED", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, mutationError("AUDIT_WRITE_FAILED", "platform", true, err)
	}
	if err := completeImportReplaceIdempotency(ctx, tx, idempotencyRecord, result, revisionID, auditID); err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "IDEMPOTENCY_STORE_WRITE_FAILED", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, err
	}
	if err := tx.Commit(); err != nil {
		_ = recordImportReplaceFailureAudit(ctx, db, opts, "PERSISTENT_STORE_WRITE_FAILED", incomingFingerprint, previousFingerprint)
		return ImportReplaceResult{}, mutationError("PERSISTENT_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("commit registry import/replace: %w", err))
	}
	committed = true
	return result, nil
}

func prepareImportReplaceRows(reg Registry) (Registry, PersistentRegistryRows, error) {
	canonical := CanonicalRegistry(reg)
	if err := canonical.Validate(); err != nil {
		return Registry{}, PersistentRegistryRows{}, err
	}
	rows, err := MapRegistryToPersistentRows(canonical)
	if err != nil {
		return Registry{}, PersistentRegistryRows{}, err
	}
	normalized, err := BuildRegistryFromPersistentRows(rows)
	if err != nil {
		return Registry{}, PersistentRegistryRows{}, err
	}
	return *normalized, rows, nil
}

func acquireRegistryMutationLock(ctx context.Context, tx *sql.Tx) (bool, error) {
	var locked bool
	if err := tx.QueryRowContext(ctx, `SELECT pg_try_advisory_xact_lock(22021, 1)`).Scan(&locked); err != nil {
		return false, fmt.Errorf("acquire registry mutation lock: %w", err)
	}
	return locked, nil
}

func currentPersistentRegistryFingerprint(ctx context.Context, tx *sql.Tx) (string, error) {
	rows, err := LoadPersistentRows(ctx, tx)
	if err != nil {
		return "", err
	}
	if persistentRowsEmpty(rows) {
		return "", nil
	}
	reg, err := BuildRegistryFromPersistentRows(rows)
	if err != nil {
		return "", err
	}
	fingerprint, err := reg.Fingerprint()
	if err != nil {
		return "", err
	}
	return fingerprint, nil
}

func persistentRowsEmpty(rows PersistentRegistryRows) bool {
	return len(rows.Projects) == 0 &&
		len(rows.APIKeys) == 0 &&
		len(rows.Capabilities) == 0 &&
		len(rows.Providers) == 0 &&
		len(rows.CredentialMetadata) == 0 &&
		len(rows.RoutingPolicies) == 0 &&
		len(rows.SnapshotConfigs) == 0
}

func replaceMutableRegistryRows(ctx context.Context, tx *sql.Tx, rows PersistentRegistryRows) error {
	deleteQueries := []string{
		`DELETE FROM providers`,
		`DELETE FROM credential_metadata`,
		`DELETE FROM api_keys`,
		`DELETE FROM routing_policies`,
		`DELETE FROM snapshot_configs`,
		`DELETE FROM capabilities`,
		`DELETE FROM projects`,
	}
	for _, query := range deleteQueries {
		if _, err := tx.ExecContext(ctx, query); err != nil {
			return fmt.Errorf("delete mutable registry rows: %w", err)
		}
	}
	return insertMutableRegistryRows(ctx, tx, rows)
}

func insertMutableRegistryRows(ctx context.Context, tx *sql.Tx, rows PersistentRegistryRows) error {
	for _, row := range rows.Projects {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO projects (id, name, status, default_mode)
VALUES ($1, $2, $3, $4)`, row.ID, row.Name, row.Status, row.DefaultMode); err != nil {
			return fmt.Errorf("insert project %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.APIKeys {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO api_keys (id, project_id, key_prefix, key_hash, status)
VALUES ($1, $2, $3, $4, $5)`, row.ID, row.ProjectID, row.KeyPrefix, row.KeyHash, row.Status); err != nil {
			return fmt.Errorf("insert api_key %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.Capabilities {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO capabilities (id, version, name, status)
VALUES ($1, $2, $3, $4)`, row.ID, row.Version, row.Name, row.Status); err != nil {
			return fmt.Errorf("insert capability %q@%q: %w", row.ID, row.Version, err)
		}
	}
	for _, row := range rows.Providers {
		metadata, err := json.Marshal(row.Metadata)
		if err != nil {
			return fmt.Errorf("encode provider %q metadata: %w", row.ID, err)
		}
		if _, err := tx.ExecContext(ctx, `
INSERT INTO providers (id, capability_id, capability_version, provider_id, provider_version, mapping_version, tool_id, regions, geo_affinity, estimated_cost, metadata, status)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::text[], $9, $10, $11::jsonb, $12)`, row.ID, row.CapabilityID, row.CapabilityVersion, row.ProviderID, row.ProviderVersion, row.MappingVersion, row.ToolID, postgresTextArrayLiteral(row.Regions), row.GeoAffinity, row.EstimatedCost, metadata, row.Status); err != nil {
			return fmt.Errorf("insert provider %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.CredentialMetadata {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO credential_metadata (credential_id, credential_version, owner_type, owner_id, provider_id, auth_type, injection_mode, source, scope, status, rotation_hint)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text[], $10, $11)`, row.CredentialID, row.CredentialVersion, row.OwnerType, row.OwnerID, row.ProviderID, row.AuthType, row.InjectionMode, row.Source, postgresTextArrayLiteral(row.Scope), row.Status, row.RotationHint); err != nil {
			return fmt.Errorf("insert credential_metadata %q: %w", row.CredentialID, err)
		}
	}
	for _, row := range rows.RoutingPolicies {
		failover, err := json.Marshal(row.FailoverPolicy)
		if err != nil {
			return fmt.Errorf("encode routing_policy %q failover_policy: %w", row.ID, err)
		}
		if _, err := tx.ExecContext(ctx, `
INSERT INTO routing_policies (id, scope_type, scope_id, strategy, routing_mode, routing_seed, failover_policy, status)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)`, row.ID, row.ScopeType, row.ScopeID, row.Strategy, row.RoutingMode, row.RoutingSeed, failover, row.Status); err != nil {
			return fmt.Errorf("insert routing_policy %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.SnapshotConfigs {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO snapshot_configs (id, version, fetched_at, ttl, source, status)
VALUES ($1, $2, $3, $4, $5, $6)`, row.ID, row.Version, row.FetchedAt, row.TTL, row.Source, row.Status); err != nil {
			return fmt.Errorf("insert snapshot_config %q: %w", row.ID, err)
		}
	}
	return nil
}

func insertRegistryRevisionTx(ctx context.Context, tx *sql.Tx, row PersistentRegistryRevisionRow, actorID string) (int64, error) {
	var id int64
	if err := tx.QueryRowContext(ctx, `
INSERT INTO registry_revisions (registry_fingerprint, snapshot_version, source_store, source_revision, created_by)
VALUES ($1, $2, $3, $4, $5)
RETURNING id`, row.RegistryFingerprint, row.SnapshotVersion, row.SourceStore, row.SourceRevision, actorID).Scan(&id); err != nil {
		return 0, fmt.Errorf("record registry revision: %w", err)
	}
	return id, nil
}

func insertImportReplaceAdminAudit(ctx context.Context, tx *sql.Tx, opts ImportReplaceOptions, result ImportReplaceResult, mutationMode string, outcome string, errorType string) (int64, error) {
	return insertAdminAuditTx(ctx, tx, PersistentAdminAuditEventRow{
		ActorID:      opts.ActorID,
		Action:       "registry.import_replace",
		ResourceType: "registry",
		ResourceID:   result.RegistryFingerprint,
		RequestID:    opts.RequestID,
		Outcome:      outcome,
		ErrorType:    errorType,
		Metadata: importReplaceAuditMetadata(opts, result, map[string]string{
			"mutation_mode": mutationMode,
		}),
	})
}

func insertAdminAuditTx(ctx context.Context, tx *sql.Tx, row PersistentAdminAuditEventRow) (int64, error) {
	metadata, err := json.Marshal(row.Metadata)
	if err != nil {
		return 0, fmt.Errorf("encode admin audit metadata: %w", err)
	}
	var id int64
	if err := tx.QueryRowContext(ctx, `
INSERT INTO admin_audit_events (actor_id, action, resource_type, resource_id, request_id, outcome, error_type, metadata)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
RETURNING id`, row.ActorID, row.Action, row.ResourceType, row.ResourceID, row.RequestID, row.Outcome, row.ErrorType, metadata).Scan(&id); err != nil {
		return 0, fmt.Errorf("record admin audit event: %w", err)
	}
	return id, nil
}

func recordImportReplaceFailureAudit(ctx context.Context, db *sql.DB, opts ImportReplaceOptions, errorType string, fingerprint string, previousFingerprint string) error {
	if db == nil {
		return nil
	}
	metadata := importReplaceAuditMetadata(opts, ImportReplaceResult{
		RegistryFingerprint:         fingerprint,
		PreviousRegistryFingerprint: previousFingerprint,
	}, map[string]string{
		"mutation_mode": "import_replace_failure",
	})
	metadata["error_type"] = errorType
	row := PersistentAdminAuditEventRow{
		ActorID:      opts.ActorID,
		Action:       "registry.import_replace",
		ResourceType: "registry",
		ResourceID:   fingerprint,
		RequestID:    opts.RequestID,
		Outcome:      "failure",
		ErrorType:    errorType,
		Metadata:     metadata,
	}
	metadataJSON, err := json.Marshal(row.Metadata)
	if err != nil {
		return err
	}
	_, err = db.ExecContext(ctx, `
INSERT INTO admin_audit_events (actor_id, action, resource_type, resource_id, request_id, outcome, error_type, metadata)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)`, row.ActorID, row.Action, row.ResourceType, row.ResourceID, row.RequestID, row.Outcome, row.ErrorType, metadataJSON)
	return err
}

const (
	adminMutationIdempotencyVersion = "admin-mutation-idempotency-v0"
	importReplaceOperation          = "registry.import_replace"
	defaultIdempotencyProjectID     = "control_plane"
)

type importReplaceIdempotencyRequest struct {
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

type importReplaceIdempotencyRecord struct {
	ID     int64
	Result ImportReplaceResult
}

type idempotencyScopeRecord struct {
	ProjectID string
	ActorID   string
	Operation string
	KeyHash   string
	KeyPrefix string
}

func newImportReplaceIdempotencyRequest(opts ImportReplaceOptions, registryFingerprint string) (importReplaceIdempotencyRequest, error) {
	if strings.TrimSpace(opts.IdempotencyKey) == "" {
		return importReplaceIdempotencyRequest{}, nil
	}
	scope := idempotencyScope(opts)
	source := strings.TrimSpace(opts.Source)
	if source == "" {
		source = "admin_http_import"
	}
	summary := map[string]string{
		"version":              adminMutationIdempotencyVersion,
		"operation":            importReplaceOperation,
		"method":               "POST",
		"path":                 "/v1/admin/registry/import-replace",
		"registry_fingerprint": registryFingerprint,
		"source":               source,
		"dry_run":              "false",
	}
	fingerprint, err := hashCanonicalJSON(summary)
	if err != nil {
		return importReplaceIdempotencyRequest{}, err
	}
	return importReplaceIdempotencyRequest{
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

func idempotencyScope(opts ImportReplaceOptions) idempotencyScopeRecord {
	projectID := strings.TrimSpace(opts.ProjectID)
	if projectID == "" {
		projectID = defaultIdempotencyProjectID
	}
	actorID := strings.TrimSpace(opts.ActorID)
	keyHash := hashString(strings.TrimSpace(opts.IdempotencyKey))
	keyPrefix := keyHash
	if len(keyPrefix) > len("sha256:")+12 {
		keyPrefix = keyPrefix[:len("sha256:")+12]
	}
	return idempotencyScopeRecord{
		ProjectID: projectID,
		ActorID:   actorID,
		Operation: importReplaceOperation,
		KeyHash:   keyHash,
		KeyPrefix: keyPrefix,
	}
}

func reserveImportReplaceIdempotency(ctx context.Context, tx *sql.Tx, req importReplaceIdempotencyRequest) (importReplaceIdempotencyRecord, bool, error) {
	if !req.Enabled {
		return importReplaceIdempotencyRecord{}, false, nil
	}
	summary, err := json.Marshal(req.RequestSummary)
	if err != nil {
		return importReplaceIdempotencyRecord{}, false, mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode idempotency request summary: %w", err))
	}
	var id int64
	err = tx.QueryRowContext(ctx, `
INSERT INTO admin_mutation_idempotency_records (
  project_id,
  actor_id,
  operation,
  idempotency_key_hash,
  idempotency_key_prefix,
  request_fingerprint,
  request_summary,
  first_request_id,
  status,
  expires_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, 'processing', now() + interval '30 days')
ON CONFLICT (project_id, actor_id, operation, idempotency_key_hash) DO NOTHING
RETURNING id`, req.ProjectID, req.ActorID, req.Operation, req.KeyHash, req.KeyPrefix, req.RequestFingerprint, summary, req.FirstRequestID).Scan(&id)
	if err == nil {
		return importReplaceIdempotencyRecord{ID: id}, false, nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return importReplaceIdempotencyRecord{}, false, mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("reserve idempotency record: %w", err))
	}
	existing, err := loadImportReplaceIdempotencyRecord(ctx, tx, req)
	if err != nil {
		return importReplaceIdempotencyRecord{}, false, err
	}
	if existing.RequestFingerprint != req.RequestFingerprint {
		return importReplaceIdempotencyRecord{}, false, mutationError("IDEMPOTENCY_KEY_CONFLICT", "caller", false, fmt.Errorf("idempotency key was already used for a different request"))
	}
	if existing.Status != "succeeded" {
		return importReplaceIdempotencyRecord{}, false, mutationError("IDEMPOTENCY_REQUEST_IN_PROGRESS", "platform", true, fmt.Errorf("idempotency request is still in progress"))
	}
	result, err := importReplaceResultFromCachedResponse(existing.ResponseBody)
	if err != nil {
		return importReplaceIdempotencyRecord{}, false, mutationError("IDEMPOTENCY_RESPONSE_REPLAY_FAILED", "platform", true, err)
	}
	result.Replayed = true
	result.IdempotencyRecordID = existing.ID
	if err := recordImportReplaceReplay(ctx, tx, existing.ID, req.FirstRequestID); err != nil {
		return importReplaceIdempotencyRecord{}, false, err
	}
	return importReplaceIdempotencyRecord{ID: existing.ID, Result: result}, true, nil
}

func completeImportReplaceIdempotency(ctx context.Context, tx *sql.Tx, record importReplaceIdempotencyRecord, result ImportReplaceResult, registryRevisionID int64, adminAuditEventID int64) error {
	if record.ID == 0 {
		return nil
	}
	body, err := json.Marshal(result)
	if err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("encode idempotency response body: %w", err))
	}
	responseFingerprint, err := hashCanonicalJSON(result)
	if err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("fingerprint idempotency response body: %w", err))
	}
	status := 201
	if result.Noop {
		status = 200
	}
	var revision any
	if registryRevisionID != 0 {
		revision = registryRevisionID
	}
	if _, err := tx.ExecContext(ctx, `
UPDATE admin_mutation_idempotency_records
SET status = 'succeeded',
    response_status_code = $1,
    response_body = $2::jsonb,
    response_fingerprint = $3,
    registry_fingerprint = $4,
    previous_registry_fingerprint = $5,
    snapshot_version = $6,
    noop = $7,
    registry_revision_id = $8,
    admin_audit_event_id = $9,
    completed_at = now(),
    expires_at = now() + interval '30 days',
    updated_at = now()
WHERE id = $10`, status, body, responseFingerprint, result.RegistryFingerprint, result.PreviousRegistryFingerprint, result.SnapshotVersion, result.Noop, revision, adminAuditEventID, record.ID); err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("complete idempotency record: %w", err))
	}
	return nil
}

type storedImportReplaceIdempotencyRecord struct {
	ID                 int64
	RequestFingerprint string
	Status             string
	ResponseBody       []byte
}

func loadImportReplaceIdempotencyRecord(ctx context.Context, tx *sql.Tx, req importReplaceIdempotencyRequest) (storedImportReplaceIdempotencyRecord, error) {
	var record storedImportReplaceIdempotencyRecord
	var responseRaw any
	if err := tx.QueryRowContext(ctx, `
SELECT id, request_fingerprint, status, response_body
FROM admin_mutation_idempotency_records
WHERE project_id = $1
  AND actor_id = $2
  AND operation = $3
  AND idempotency_key_hash = $4`, req.ProjectID, req.ActorID, req.Operation, req.KeyHash).Scan(&record.ID, &record.RequestFingerprint, &record.Status, &responseRaw); err != nil {
		return storedImportReplaceIdempotencyRecord{}, mutationError("IDEMPOTENCY_STORE_READ_FAILED", "platform", true, fmt.Errorf("load idempotency record: %w", err))
	}
	data, err := rawBytes(responseRaw)
	if err != nil {
		return storedImportReplaceIdempotencyRecord{}, mutationError("IDEMPOTENCY_RESPONSE_REPLAY_FAILED", "platform", true, err)
	}
	record.ResponseBody = data
	return record, nil
}

func recordImportReplaceReplay(ctx context.Context, tx *sql.Tx, recordID int64, requestID string) error {
	if _, err := tx.ExecContext(ctx, `
UPDATE admin_mutation_idempotency_records
SET replay_count = replay_count + 1,
    last_replay_request_id = $1,
    last_replayed_at = now(),
    updated_at = now()
WHERE id = $2`, requestID, recordID); err != nil {
		return mutationError("IDEMPOTENCY_STORE_WRITE_FAILED", "platform", true, fmt.Errorf("record idempotency replay: %w", err))
	}
	return nil
}

func importReplaceResultFromCachedResponse(data []byte) (ImportReplaceResult, error) {
	if len(data) == 0 || string(data) == "null" {
		return ImportReplaceResult{}, fmt.Errorf("cached idempotency response is empty")
	}
	var result ImportReplaceResult
	if err := json.Unmarshal(data, &result); err != nil {
		return ImportReplaceResult{}, fmt.Errorf("decode cached idempotency response: %w", err)
	}
	return result, nil
}

func hashCanonicalJSON(value any) (string, error) {
	data, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	return hashBytes(data), nil
}

func hashString(value string) string {
	return hashBytes([]byte(value))
}

func hashBytes(value []byte) string {
	sum := sha256.Sum256(value)
	return "sha256:" + fmt.Sprintf("%x", sum[:])
}

func importReplaceAuditMetadata(opts ImportReplaceOptions, result ImportReplaceResult, extra map[string]string) map[string]string {
	metadata := map[string]string{
		"registry_store":       "postgres",
		"registry_fingerprint": result.RegistryFingerprint,
		"snapshot_version":     result.SnapshotVersion,
		"projects":             strconv.Itoa(result.Counts.Projects),
		"api_keys":             strconv.Itoa(result.Counts.APIKeys),
		"capabilities":         strconv.Itoa(result.Counts.Capabilities),
		"providers":            strconv.Itoa(result.Counts.Providers),
		"credential_metadata":  strconv.Itoa(result.Counts.CredentialMetadata),
		"routing_policies":     strconv.Itoa(result.Counts.RoutingPolicies),
		"snapshot_configs":     strconv.Itoa(result.Counts.SnapshotConfigs),
	}
	if result.PreviousRegistryFingerprint != "" {
		metadata["previous_registry_fingerprint"] = result.PreviousRegistryFingerprint
	}
	if opts.ProjectID != "" {
		metadata["project_id"] = opts.ProjectID
	}
	if opts.SubjectID != "" {
		metadata["principal_subject_id"] = opts.SubjectID
	}
	if opts.OrganizationID != "" {
		metadata["organization_id"] = opts.OrganizationID
	}
	if opts.AuthMethod != "" {
		metadata["auth_method"] = opts.AuthMethod
		metadata["local_private"] = strconv.FormatBool(opts.LocalPrivate)
	}
	if opts.TokenID != "" {
		metadata["token_id"] = opts.TokenID
	}
	if opts.IdempotencyKey != "" {
		scope := idempotencyScope(opts)
		metadata["idempotency_key_hash"] = scope.KeyHash
		metadata["idempotency_key_prefix"] = scope.KeyPrefix
	}
	if opts.Source != "" {
		metadata["source"] = opts.Source
	}
	for key, value := range extra {
		metadata[key] = value
	}
	return metadata
}

func importReplaceCounts(rows PersistentRegistryRows) ImportReplaceCounts {
	return ImportReplaceCounts{
		Projects:           len(rows.Projects),
		APIKeys:            len(rows.APIKeys),
		Capabilities:       len(rows.Capabilities),
		Providers:          len(rows.Providers),
		CredentialMetadata: len(rows.CredentialMetadata),
		RoutingPolicies:    len(rows.RoutingPolicies),
		SnapshotConfigs:    len(rows.SnapshotConfigs),
	}
}

func importReplaceSourceRevision(opts ImportReplaceOptions) string {
	if opts.RequestID != "" {
		return opts.RequestID
	}
	if opts.IdempotencyKey != "" {
		return opts.IdempotencyKey
	}
	return opts.Source
}

func mutationError(errorType string, scope string, retryable bool, err error) RegistryMutationError {
	return RegistryMutationError{
		ErrorType:  errorType,
		Scope:      scope,
		Retryable:  retryable,
		Underlying: err,
	}
}
