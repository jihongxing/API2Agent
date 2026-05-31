package registry

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestPostgresStoreRequiresDB(t *testing.T) {
	_, err := NewPostgresStore(nil).Load(context.Background())
	if err == nil {
		t.Fatalf("expected missing db error")
	}
	if !strings.Contains(err.Error(), "postgres registry db is required") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestPostgresStoreLoadBuildsEquivalentRegistryFromActiveRows(t *testing.T) {
	fileRegistry := loadValidRegistry(t)
	persistentRows, err := MapRegistryToPersistentRows(fileRegistry)
	if err != nil {
		t.Fatalf("map registry rows: %v", err)
	}
	db, script := openScriptedRegistryDB(t, persistentRows)
	defer db.Close()

	loaded, err := NewPostgresStore(db).Load(context.Background())
	if err != nil {
		t.Fatalf("load postgres registry: %v", err)
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
		t.Fatalf("did not expect driver rollback after successful load")
	}

	fileSnapshot, err := CanonicalRegistry(fileRegistry).ExportSnapshot()
	if err != nil {
		t.Fatalf("export file snapshot: %v", err)
	}
	postgresSnapshot, err := loaded.ExportSnapshot()
	if err != nil {
		t.Fatalf("export postgres snapshot: %v", err)
	}
	if !reflectSnapshotsEquivalent(fileSnapshot, postgresSnapshot) {
		t.Fatalf("expected equivalent snapshots:\nfile=%#v\npostgres=%#v", fileSnapshot, postgresSnapshot)
	}
}

func openScriptedRegistryDB(t *testing.T, rows PersistentRegistryRows) (*sql.DB, *scriptedRegistryDB) {
	t.Helper()
	registerScriptedRegistryDriverOnce()
	script := &scriptedRegistryDB{rows: rows, lockAvailable: true}
	scriptedRegistryMu.Lock()
	scriptedRegistryNext = script
	scriptedRegistryMu.Unlock()
	db, err := sql.Open(scriptedRegistryDriverName, "registry")
	if err != nil {
		t.Fatalf("open scripted db: %v", err)
	}
	return db, script
}

const scriptedRegistryDriverName = "api2agent_registry_postgres_scripted"

var (
	scriptedRegistryRegisterOnce sync.Once
	scriptedRegistryMu           sync.Mutex
	scriptedRegistryNext         *scriptedRegistryDB
)

func registerScriptedRegistryDriverOnce() {
	scriptedRegistryRegisterOnce.Do(func() {
		sql.Register(scriptedRegistryDriverName, scriptedRegistryDriver{})
	})
}

type scriptedRegistryDB struct {
	rows             PersistentRegistryRows
	beginCalled      bool
	beginOptions     driver.TxOptions
	committed        bool
	rolledBack       bool
	lockAvailable    bool
	execQueries      []string
	failExecContains string
	txBackup         *PersistentRegistryRows
}

type scriptedRegistryDriver struct{}

func (scriptedRegistryDriver) Open(name string) (driver.Conn, error) {
	scriptedRegistryMu.Lock()
	defer scriptedRegistryMu.Unlock()
	if scriptedRegistryNext == nil {
		return nil, fmt.Errorf("scripted registry db was not configured")
	}
	script := scriptedRegistryNext
	scriptedRegistryNext = nil
	return &scriptedRegistryConn{script: script}, nil
}

type scriptedRegistryConn struct {
	script *scriptedRegistryDB
}

func (c *scriptedRegistryConn) Prepare(query string) (driver.Stmt, error) {
	return nil, errors.New("prepare is not supported")
}

func (c *scriptedRegistryConn) Close() error {
	return nil
}

func (c *scriptedRegistryConn) Begin() (driver.Tx, error) {
	return c.BeginTx(context.Background(), driver.TxOptions{})
}

func (c *scriptedRegistryConn) BeginTx(ctx context.Context, opts driver.TxOptions) (driver.Tx, error) {
	c.script.beginCalled = true
	c.script.beginOptions = opts
	backup := clonePersistentRows(c.script.rows)
	c.script.txBackup = &backup
	return &scriptedRegistryTx{script: c.script}, nil
}

func (c *scriptedRegistryConn) QueryContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Rows, error) {
	if strings.Contains(query, "INSERT INTO") || strings.Contains(query, "UPDATE ") {
		c.script.execQueries = append(c.script.execQueries, query)
	}
	if c.script.failExecContains != "" && strings.Contains(query, c.script.failExecContains) {
		return nil, fmt.Errorf("scripted exec failure for %s", c.script.failExecContains)
	}
	return c.rowsFor(query, args)
}

func (c *scriptedRegistryConn) rowsFor(query string, args []driver.NamedValue) (driver.Rows, error) {
	switch {
	case strings.Contains(query, "INSERT INTO admin_mutation_idempotency_records"):
		return c.insertIdempotencyRecord(query, args)
	case strings.Contains(query, "SELECT id, request_fingerprint, status, response_body"):
		return c.selectIdempotencyRecord(args)
	case strings.Contains(query, "INSERT INTO registry_revisions"):
		if err := c.applyExec(query, args); err != nil {
			return nil, err
		}
		id := c.script.rows.RegistryRevisions[len(c.script.rows.RegistryRevisions)-1].ID
		return newScriptedRows([]string{"id"}, [][]driver.Value{{id}}), nil
	case strings.Contains(query, "INSERT INTO admin_audit_events"):
		if err := c.applyExec(query, args); err != nil {
			return nil, err
		}
		id := c.script.rows.AdminAuditEvents[len(c.script.rows.AdminAuditEvents)-1].ID
		return newScriptedRows([]string{"id"}, [][]driver.Value{{id}}), nil
	case strings.Contains(query, "pg_try_advisory_xact_lock"):
		return newScriptedRows([]string{"locked"}, [][]driver.Value{{c.script.lockAvailable}}), nil
	case strings.Contains(query, "FROM projects"):
		return newScriptedRows([]string{"id", "name", "status", "default_mode"}, projectValues(c.script.rows.Projects)), nil
	case strings.Contains(query, "FROM api_keys"):
		return newScriptedRows([]string{"id", "project_id", "key_prefix", "key_hash", "status"}, apiKeyValues(c.script.rows.APIKeys)), nil
	case strings.Contains(query, "FROM capabilities"):
		return newScriptedRows([]string{"id", "version", "name", "status"}, capabilityValues(c.script.rows.Capabilities)), nil
	case strings.Contains(query, "FROM providers"):
		return newScriptedRows([]string{"id", "capability_id", "capability_version", "provider_id", "provider_version", "mapping_version", "tool_id", "regions", "geo_affinity", "estimated_cost", "metadata", "status"}, providerValues(c.script.rows.Providers)), nil
	case strings.Contains(query, "FROM credential_metadata"):
		return newScriptedRows([]string{"credential_id", "credential_version", "owner_type", "owner_id", "provider_id", "auth_type", "injection_mode", "source", "scope", "status", "rotation_hint"}, credentialValues(c.script.rows.CredentialMetadata)), nil
	case strings.Contains(query, "FROM routing_policies"):
		return newScriptedRows([]string{"id", "scope_type", "scope_id", "strategy", "routing_mode", "routing_seed", "failover_policy", "status"}, routingPolicyValues(c.script.rows.RoutingPolicies)), nil
	case strings.Contains(query, "FROM snapshot_configs"):
		return newScriptedRows([]string{"id", "version", "fetched_at", "ttl", "source", "status"}, snapshotConfigValues(c.script.rows.SnapshotConfigs)), nil
	default:
		return nil, fmt.Errorf("unexpected query: %s", query)
	}
}

func (c *scriptedRegistryConn) insertIdempotencyRecord(query string, args []driver.NamedValue) (driver.Rows, error) {
	for _, row := range c.script.rows.IdempotencyRecords {
		if row.ProjectID == namedString(args, 0) &&
			row.ActorID == namedString(args, 1) &&
			row.Operation == namedString(args, 2) &&
			row.IdempotencyKeyHash == namedString(args, 3) {
			return newScriptedRows([]string{"id"}, nil), nil
		}
	}
	summary, err := parseJSONMap(namedBytes(args, 6))
	if err != nil {
		return nil, err
	}
	id := int64(len(c.script.rows.IdempotencyRecords) + 1)
	c.script.rows.IdempotencyRecords = append(c.script.rows.IdempotencyRecords, PersistentIdempotencyRecordRow{
		ID:                   id,
		ProjectID:            namedString(args, 0),
		ActorID:              namedString(args, 1),
		Operation:            namedString(args, 2),
		IdempotencyKeyHash:   namedString(args, 3),
		IdempotencyKeyPrefix: namedString(args, 4),
		RequestFingerprint:   namedString(args, 5),
		RequestSummary:       summary,
		FirstRequestID:       namedString(args, 7),
		Status:               "processing",
	})
	return newScriptedRows([]string{"id"}, [][]driver.Value{{id}}), nil
}

func (c *scriptedRegistryConn) selectIdempotencyRecord(args []driver.NamedValue) (driver.Rows, error) {
	for _, row := range c.script.rows.IdempotencyRecords {
		if row.ProjectID == namedString(args, 0) &&
			row.ActorID == namedString(args, 1) &&
			row.Operation == namedString(args, 2) &&
			row.IdempotencyKeyHash == namedString(args, 3) {
			return newScriptedRows(
				[]string{"id", "request_fingerprint", "status", "response_body"},
				[][]driver.Value{{row.ID, row.RequestFingerprint, row.Status, row.ResponseBody}},
			), nil
		}
	}
	return newScriptedRows([]string{"id", "request_fingerprint", "status", "response_body"}, nil), nil
}

func (c *scriptedRegistryConn) ExecContext(ctx context.Context, query string, args []driver.NamedValue) (driver.Result, error) {
	c.script.execQueries = append(c.script.execQueries, query)
	if c.script.failExecContains != "" && strings.Contains(query, c.script.failExecContains) {
		return nil, fmt.Errorf("scripted exec failure for %s", c.script.failExecContains)
	}
	if err := c.applyExec(query, args); err != nil {
		return nil, err
	}
	return driver.RowsAffected(1), nil
}

func (c *scriptedRegistryConn) applyExec(query string, args []driver.NamedValue) error {
	switch {
	case strings.Contains(query, "DELETE FROM providers"):
		c.script.rows.Providers = nil
	case strings.Contains(query, "DELETE FROM credential_metadata"):
		c.script.rows.CredentialMetadata = nil
	case strings.Contains(query, "DELETE FROM api_keys"):
		c.script.rows.APIKeys = nil
	case strings.Contains(query, "DELETE FROM routing_policies"):
		c.script.rows.RoutingPolicies = nil
	case strings.Contains(query, "DELETE FROM snapshot_configs"):
		c.script.rows.SnapshotConfigs = nil
	case strings.Contains(query, "DELETE FROM capabilities"):
		c.script.rows.Capabilities = nil
	case strings.Contains(query, "DELETE FROM projects"):
		c.script.rows.Projects = nil
	case strings.Contains(query, "INSERT INTO projects"):
		c.script.rows.Projects = append(c.script.rows.Projects, PersistentProjectRow{
			ID:          namedString(args, 0),
			Name:        namedString(args, 1),
			Status:      namedString(args, 2),
			DefaultMode: namedString(args, 3),
		})
	case strings.Contains(query, "INSERT INTO api_keys"):
		c.script.rows.APIKeys = append(c.script.rows.APIKeys, PersistentAPIKeyRow{
			ID:        namedString(args, 0),
			ProjectID: namedString(args, 1),
			KeyPrefix: namedString(args, 2),
			KeyHash:   namedString(args, 3),
			Status:    namedString(args, 4),
		})
	case strings.Contains(query, "INSERT INTO capabilities"):
		c.script.rows.Capabilities = append(c.script.rows.Capabilities, PersistentCapabilityRow{
			ID:      namedString(args, 0),
			Version: namedString(args, 1),
			Name:    namedString(args, 2),
			Status:  namedString(args, 3),
		})
	case strings.Contains(query, "INSERT INTO providers"):
		regions, err := parsePostgresTextArray(namedString(args, 7))
		if err != nil {
			return err
		}
		metadata, err := parseJSONMap(namedBytes(args, 10))
		if err != nil {
			return err
		}
		c.script.rows.Providers = append(c.script.rows.Providers, PersistentProviderRow{
			ID:                namedString(args, 0),
			CapabilityID:      namedString(args, 1),
			CapabilityVersion: namedString(args, 2),
			ProviderID:        namedString(args, 3),
			ProviderVersion:   namedString(args, 4),
			MappingVersion:    namedString(args, 5),
			ToolID:            namedString(args, 6),
			Regions:           regions,
			GeoAffinity:       namedString(args, 8),
			EstimatedCost:     namedFloat(args, 9),
			Metadata:          metadata,
			Status:            namedString(args, 11),
		})
	case strings.Contains(query, "INSERT INTO credential_metadata"):
		scope, err := parsePostgresTextArray(namedString(args, 8))
		if err != nil {
			return err
		}
		c.script.rows.CredentialMetadata = append(c.script.rows.CredentialMetadata, PersistentCredentialMetadataRow{
			CredentialID:      namedString(args, 0),
			CredentialVersion: namedString(args, 1),
			OwnerType:         namedString(args, 2),
			OwnerID:           namedString(args, 3),
			ProviderID:        namedString(args, 4),
			AuthType:          namedString(args, 5),
			InjectionMode:     namedString(args, 6),
			Source:            namedString(args, 7),
			Scope:             scope,
			Status:            namedString(args, 9),
			RotationHint:      namedString(args, 10),
		})
	case strings.Contains(query, "INSERT INTO routing_policies"):
		var seed *string
		if value, ok := args[5].Value.(string); ok {
			seed = &value
		}
		failover, err := parseFailoverPolicy(namedBytes(args, 6))
		if err != nil {
			return err
		}
		c.script.rows.RoutingPolicies = append(c.script.rows.RoutingPolicies, PersistentRoutingPolicyRow{
			ID:             namedString(args, 0),
			ScopeType:      namedString(args, 1),
			ScopeID:        namedString(args, 2),
			Strategy:       namedString(args, 3),
			RoutingMode:    namedString(args, 4),
			RoutingSeed:    seed,
			FailoverPolicy: failover,
			Status:         namedString(args, 7),
		})
	case strings.Contains(query, "INSERT INTO snapshot_configs"):
		c.script.rows.SnapshotConfigs = append(c.script.rows.SnapshotConfigs, PersistentSnapshotConfigRow{
			ID:        namedString(args, 0),
			Version:   namedString(args, 1),
			FetchedAt: namedString(args, 2),
			TTL:       namedString(args, 3),
			Source:    namedString(args, 4),
			Status:    namedString(args, 5),
		})
	case strings.Contains(query, "INSERT INTO registry_revisions"):
		id := int64(len(c.script.rows.RegistryRevisions) + 1)
		c.script.rows.RegistryRevisions = append(c.script.rows.RegistryRevisions, PersistentRegistryRevisionRow{
			ID:                  id,
			RegistryFingerprint: namedString(args, 0),
			SnapshotVersion:     namedString(args, 1),
			SourceStore:         namedString(args, 2),
			SourceRevision:      namedString(args, 3),
		})
	case strings.Contains(query, "INSERT INTO admin_audit_events"):
		metadata, err := parseJSONMap(namedBytes(args, 7))
		if err != nil {
			return err
		}
		id := int64(len(c.script.rows.AdminAuditEvents) + 1)
		c.script.rows.AdminAuditEvents = append(c.script.rows.AdminAuditEvents, PersistentAdminAuditEventRow{
			ID:           id,
			ActorID:      namedString(args, 0),
			Action:       namedString(args, 1),
			ResourceType: namedString(args, 2),
			ResourceID:   namedString(args, 3),
			RequestID:    namedString(args, 4),
			Outcome:      namedString(args, 5),
			ErrorType:    namedString(args, 6),
			Metadata:     metadata,
		})
	case strings.Contains(query, "UPDATE admin_mutation_idempotency_records") && strings.Contains(query, "replay_count"):
		id := namedInt64(args, 1)
		for i := range c.script.rows.IdempotencyRecords {
			if c.script.rows.IdempotencyRecords[i].ID == id {
				c.script.rows.IdempotencyRecords[i].ReplayCount++
				c.script.rows.IdempotencyRecords[i].LastReplayRequestID = namedString(args, 0)
				return nil
			}
		}
		return fmt.Errorf("idempotency record %d not found", id)
	case strings.Contains(query, "UPDATE admin_mutation_idempotency_records"):
		id := namedInt64(args, 9)
		for i := range c.script.rows.IdempotencyRecords {
			if c.script.rows.IdempotencyRecords[i].ID == id {
				row := &c.script.rows.IdempotencyRecords[i]
				row.Status = "succeeded"
				row.ResponseStatusCode = namedInt(args, 0)
				row.ResponseBody = string(namedBytes(args, 1))
				row.ResponseFingerprint = namedString(args, 2)
				row.RegistryFingerprint = namedString(args, 3)
				row.PreviousRegistryFingerprint = namedString(args, 4)
				row.SnapshotVersion = namedString(args, 5)
				row.Noop = namedBool(args, 6)
				row.RegistryRevisionID = namedInt64Ptr(args, 7)
				row.AdminAuditEventID = namedInt64Ptr(args, 8)
				return nil
			}
		}
		return fmt.Errorf("idempotency record %d not found", id)
	default:
		return fmt.Errorf("unexpected exec: %s", query)
	}
	return nil
}

type scriptedRegistryTx struct {
	script *scriptedRegistryDB
}

func (tx *scriptedRegistryTx) Commit() error {
	tx.script.committed = true
	return nil
}

func (tx *scriptedRegistryTx) Rollback() error {
	tx.script.rolledBack = true
	if tx.script.txBackup != nil {
		tx.script.rows = clonePersistentRows(*tx.script.txBackup)
	}
	return nil
}

type scriptedRows struct {
	columns []string
	values  [][]driver.Value
	index   int
}

func newScriptedRows(columns []string, values [][]driver.Value) *scriptedRows {
	return &scriptedRows{columns: columns, values: values}
}

func (r *scriptedRows) Columns() []string {
	return r.columns
}

func (r *scriptedRows) Close() error {
	return nil
}

func (r *scriptedRows) Next(dest []driver.Value) error {
	if r.index >= len(r.values) {
		return io.EOF
	}
	copy(dest, r.values[r.index])
	r.index++
	return nil
}

func projectValues(rows []PersistentProjectRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		out = append(out, []driver.Value{row.ID, row.Name, row.Status, row.DefaultMode})
	}
	return out
}

func apiKeyValues(rows []PersistentAPIKeyRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		out = append(out, []driver.Value{row.ID, row.ProjectID, row.KeyPrefix, row.KeyHash, row.Status})
	}
	return out
}

func capabilityValues(rows []PersistentCapabilityRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		out = append(out, []driver.Value{row.ID, row.Version, row.Name, row.Status})
	}
	return out
}

func providerValues(rows []PersistentProviderRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		out = append(out, []driver.Value{row.ID, row.CapabilityID, row.CapabilityVersion, row.ProviderID, row.ProviderVersion, row.MappingVersion, row.ToolID, postgresTextArrayLiteral(row.Regions), row.GeoAffinity, row.EstimatedCost, tMustJSON(row.Metadata), row.Status})
	}
	return out
}

func credentialValues(rows []PersistentCredentialMetadataRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		out = append(out, []driver.Value{row.CredentialID, row.CredentialVersion, row.OwnerType, row.OwnerID, row.ProviderID, row.AuthType, row.InjectionMode, row.Source, postgresTextArrayLiteral(row.Scope), row.Status, row.RotationHint})
	}
	return out
}

func routingPolicyValues(rows []PersistentRoutingPolicyRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		var seed any
		if row.RoutingSeed != nil {
			seed = *row.RoutingSeed
		}
		var failover any
		if row.FailoverPolicy != nil {
			failover = tMustJSON(row.FailoverPolicy)
		}
		out = append(out, []driver.Value{row.ID, row.ScopeType, row.ScopeID, row.Strategy, row.RoutingMode, seed, failover, row.Status})
	}
	return out
}

func snapshotConfigValues(rows []PersistentSnapshotConfigRow) [][]driver.Value {
	out := make([][]driver.Value, 0, len(rows))
	for _, row := range rows {
		fetchedAt, err := time.Parse(time.RFC3339, row.FetchedAt)
		if err != nil {
			panic(err)
		}
		out = append(out, []driver.Value{row.ID, row.Version, fetchedAt, row.TTL, row.Source, row.Status})
	}
	return out
}

func tMustJSON(value any) []byte {
	data, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	return data
}

func namedString(args []driver.NamedValue, index int) string {
	if index >= len(args) || args[index].Value == nil {
		return ""
	}
	switch value := args[index].Value.(type) {
	case string:
		return value
	case []byte:
		return string(value)
	default:
		return fmt.Sprint(value)
	}
}

func namedBytes(args []driver.NamedValue, index int) []byte {
	if index >= len(args) || args[index].Value == nil {
		return nil
	}
	switch value := args[index].Value.(type) {
	case []byte:
		return value
	case string:
		return []byte(value)
	default:
		return []byte(fmt.Sprint(value))
	}
}

func namedFloat(args []driver.NamedValue, index int) float64 {
	if index >= len(args) || args[index].Value == nil {
		return 0
	}
	switch value := args[index].Value.(type) {
	case float64:
		return value
	case float32:
		return float64(value)
	case int64:
		return float64(value)
	case int:
		return float64(value)
	default:
		panic(fmt.Sprintf("unexpected float value %T", value))
	}
}

func namedInt(args []driver.NamedValue, index int) int {
	return int(namedInt64(args, index))
}

func namedInt64(args []driver.NamedValue, index int) int64 {
	if index >= len(args) || args[index].Value == nil {
		return 0
	}
	switch value := args[index].Value.(type) {
	case int64:
		return value
	case int:
		return int64(value)
	case int32:
		return int64(value)
	default:
		panic(fmt.Sprintf("unexpected int value %T", value))
	}
}

func namedInt64Ptr(args []driver.NamedValue, index int) *int64 {
	if index >= len(args) || args[index].Value == nil {
		return nil
	}
	value := namedInt64(args, index)
	return &value
}

func namedBool(args []driver.NamedValue, index int) bool {
	if index >= len(args) || args[index].Value == nil {
		return false
	}
	value, ok := args[index].Value.(bool)
	if !ok {
		panic(fmt.Sprintf("unexpected bool value %T", args[index].Value))
	}
	return value
}

func reflectSnapshotsEquivalent(left RoutingSnapshot, right RoutingSnapshot) bool {
	return left.SnapshotVersion == right.SnapshotVersion &&
		left.SnapshotTTL == right.SnapshotTTL &&
		left.SnapshotSource == right.SnapshotSource &&
		left.SnapshotFetchedAt.Equal(right.SnapshotFetchedAt) &&
		reflectDeepEqual(left.Capabilities, right.Capabilities) &&
		reflectDeepEqual(left.Providers, right.Providers) &&
		reflectDeepEqual(left.RoutingPolicy, right.RoutingPolicy) &&
		left.Metadata["registry_fingerprint"] == right.Metadata["registry_fingerprint"] &&
		left.Metadata["schema_version"] == right.Metadata["schema_version"] &&
		left.Metadata["snapshot_version_policy"] == right.Metadata["snapshot_version_policy"]
}

func reflectDeepEqual(left any, right any) bool {
	leftData, err := json.Marshal(left)
	if err != nil {
		panic(err)
	}
	rightData, err := json.Marshal(right)
	if err != nil {
		panic(err)
	}
	return string(leftData) == string(rightData)
}

func clonePersistentRows(rows PersistentRegistryRows) PersistentRegistryRows {
	data, err := json.Marshal(rows)
	if err != nil {
		panic(err)
	}
	var cloned PersistentRegistryRows
	if err := json.Unmarshal(data, &cloned); err != nil {
		panic(err)
	}
	return cloned
}
