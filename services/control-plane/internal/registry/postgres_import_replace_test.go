package registry

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"strings"
	"testing"
)

func TestReplacePersistentRegistryNoopWritesAdminAuditOnly(t *testing.T) {
	reg := loadValidRegistry(t)
	rows, err := MapRegistryToPersistentRows(reg)
	if err != nil {
		t.Fatalf("map registry rows: %v", err)
	}
	initialRevisionCount := len(rows.RegistryRevisions)
	db, script := openScriptedRegistryDB(t, rows)
	defer db.Close()

	result, err := ReplacePersistentRegistry(context.Background(), db, reg, ImportReplaceOptions{
		ActorID:        "tester",
		RequestID:      "req-noop",
		IdempotencyKey: "idem-noop",
		Source:         "test-registry.json",
	})
	if err != nil {
		t.Fatalf("replace persistent registry: %v", err)
	}

	if !result.Noop {
		t.Fatalf("expected no-op result: %#v", result)
	}
	if script.beginOptions.Isolation != driver.IsolationLevel(sql.LevelSerializable) || script.beginOptions.ReadOnly {
		t.Fatalf("unexpected transaction options: %#v", script.beginOptions)
	}
	if !script.committed || script.rolledBack {
		t.Fatalf("expected commit without rollback: committed=%v rolledBack=%v", script.committed, script.rolledBack)
	}
	if len(script.rows.RegistryRevisions) != initialRevisionCount {
		t.Fatalf("noop should not write registry revision: %#v", script.rows.RegistryRevisions)
	}
	if len(script.rows.AdminAuditEvents) != 1 {
		t.Fatalf("expected one admin audit event, got %#v", script.rows.AdminAuditEvents)
	}
	event := script.rows.AdminAuditEvents[0]
	if event.Action != "registry.import_replace" || event.Outcome != "success" || event.Metadata["mutation_mode"] != "import_replace_noop" {
		t.Fatalf("unexpected audit event: %#v", event)
	}
	if containsExec(script.execQueries, "DELETE FROM") {
		t.Fatalf("noop should not delete mutable rows: %#v", script.execQueries)
	}
	if len(script.rows.IdempotencyRecords) != 1 {
		t.Fatalf("expected one idempotency record, got %#v", script.rows.IdempotencyRecords)
	}
	idempotency := script.rows.IdempotencyRecords[0]
	if idempotency.Status != "succeeded" || idempotency.ResponseStatusCode != 200 || idempotency.RegistryRevisionID != nil || idempotency.AdminAuditEventID == nil {
		t.Fatalf("unexpected noop idempotency record: %#v", idempotency)
	}
	if idempotency.IdempotencyKeyHash == "idem-noop" || idempotency.IdempotencyKeyPrefix == "idem-noop" {
		t.Fatalf("idempotency record stored raw key: %#v", idempotency)
	}
}

func TestReplacePersistentRegistryReplacesRowsAndWritesRevisionAndAudit(t *testing.T) {
	current := loadValidRegistry(t)
	currentRows, err := MapRegistryToPersistentRows(current)
	if err != nil {
		t.Fatalf("map current rows: %v", err)
	}
	incoming := loadValidRegistry(t)
	incoming.Providers[0].ID = "httpbin_public_ip_v1"
	incoming.Providers[0].ProviderID = "httpbin"
	incoming.Providers[0].Metadata["base_url"] = "https://httpbin.org"
	incoming.CredentialMetadata[0].ProviderID = "httpbin"
	incoming.Snapshot.Version = "snapshot_import_replace_v2"
	db, script := openScriptedRegistryDB(t, currentRows)
	defer db.Close()

	result, err := ReplacePersistentRegistry(context.Background(), db, incoming, ImportReplaceOptions{
		ProjectID:      "project-hosted",
		SubjectID:      "subject-hosted",
		ActorID:        "tester",
		OrganizationID: "org-hosted",
		AuthMethod:     AdminAuthMethodTrustedGateway,
		TokenID:        "token-hosted",
		LocalPrivate:   false,
		RequestID:      "req-replace",
		IdempotencyKey: "idem-replace",
		Source:         "test-registry.json",
	})
	if err != nil {
		t.Fatalf("replace persistent registry: %v", err)
	}

	if result.Noop {
		t.Fatalf("expected non-noop result: %#v", result)
	}
	if !script.committed || script.rolledBack {
		t.Fatalf("expected commit without rollback: committed=%v rolledBack=%v", script.committed, script.rolledBack)
	}
	if len(script.rows.Providers) != 1 || script.rows.Providers[0].ID != "httpbin_public_ip_v1" {
		t.Fatalf("expected provider replacement, got %#v", script.rows.Providers)
	}
	if len(script.rows.RegistryRevisions) != 2 {
		t.Fatalf("expected initial plus new registry revision, got %#v", script.rows.RegistryRevisions)
	}
	revision := script.rows.RegistryRevisions[1]
	if revision.RegistryFingerprint != result.RegistryFingerprint || revision.SourceStore != "postgres" || revision.SourceRevision != "req-replace" {
		t.Fatalf("unexpected registry revision: %#v result=%#v", revision, result)
	}
	if len(script.rows.AdminAuditEvents) != 1 {
		t.Fatalf("expected one admin audit event, got %#v", script.rows.AdminAuditEvents)
	}
	event := script.rows.AdminAuditEvents[0]
	if event.Metadata["mutation_mode"] != "import_replace" || event.Metadata["previous_registry_fingerprint"] == "" {
		t.Fatalf("unexpected admin audit metadata: %#v", event)
	}
	if event.Metadata["project_id"] != "project-hosted" || event.Metadata["principal_subject_id"] != "subject-hosted" || event.Metadata["organization_id"] != "org-hosted" || event.Metadata["auth_method"] != AdminAuthMethodTrustedGateway || event.Metadata["token_id"] != "token-hosted" || event.Metadata["local_private"] != "false" {
		t.Fatalf("unexpected principal audit metadata: %#v", event.Metadata)
	}
	if !containsExec(script.execQueries, "DELETE FROM providers") {
		t.Fatalf("expected mutable row deletion: %#v", script.execQueries)
	}
	if len(script.rows.IdempotencyRecords) != 1 {
		t.Fatalf("expected one idempotency record, got %#v", script.rows.IdempotencyRecords)
	}
	idempotency := script.rows.IdempotencyRecords[0]
	if idempotency.Status != "succeeded" || idempotency.ResponseStatusCode != 201 || idempotency.RegistryRevisionID == nil || idempotency.AdminAuditEventID == nil {
		t.Fatalf("unexpected replace idempotency record: %#v", idempotency)
	}
	if idempotency.RegistryFingerprint != result.RegistryFingerprint || idempotency.SnapshotVersion != result.SnapshotVersion {
		t.Fatalf("idempotency record did not cache result metadata: %#v result=%#v", idempotency, result)
	}
}

func TestReplacePersistentRegistryReplaysSameIdempotencyRequest(t *testing.T) {
	current := loadValidRegistry(t)
	currentRows, err := MapRegistryToPersistentRows(current)
	if err != nil {
		t.Fatalf("map current rows: %v", err)
	}
	incoming := loadValidRegistry(t)
	incoming.Providers[0].ID = "httpbin_public_ip_v1"
	incoming.Providers[0].ProviderID = "httpbin"
	incoming.Providers[0].Metadata["base_url"] = "https://httpbin.org"
	incoming.CredentialMetadata[0].ProviderID = "httpbin"
	incoming.Snapshot.Version = "snapshot_import_replace_v2"
	db, script := openScriptedRegistryDB(t, currentRows)
	defer db.Close()

	first, err := ReplacePersistentRegistry(context.Background(), db, incoming, ImportReplaceOptions{
		ActorID:        "tester",
		RequestID:      "req-replay-first",
		IdempotencyKey: "idem-replay",
		Source:         "test-registry.json",
	})
	if err != nil {
		t.Fatalf("first replace persistent registry: %v", err)
	}
	script.execQueries = nil
	beforeAuditCount := len(script.rows.AdminAuditEvents)
	beforeRevisionCount := len(script.rows.RegistryRevisions)

	replayed, err := ReplacePersistentRegistry(context.Background(), db, incoming, ImportReplaceOptions{
		ActorID:        "tester",
		RequestID:      "req-replay-second",
		IdempotencyKey: "idem-replay",
		Source:         "test-registry.json",
	})
	if err != nil {
		t.Fatalf("replay replace persistent registry: %v", err)
	}

	if !replayed.Replayed || replayed.RegistryFingerprint != first.RegistryFingerprint || replayed.SnapshotVersion != first.SnapshotVersion || replayed.Noop != first.Noop {
		t.Fatalf("unexpected replay result: first=%#v replayed=%#v", first, replayed)
	}
	if containsExec(script.execQueries, "DELETE FROM") {
		t.Fatalf("replay should not replace mutable rows: %#v", script.execQueries)
	}
	if len(script.rows.AdminAuditEvents) != beforeAuditCount || len(script.rows.RegistryRevisions) != beforeRevisionCount {
		t.Fatalf("replay should not create audit/revision rows: audits=%#v revisions=%#v", script.rows.AdminAuditEvents, script.rows.RegistryRevisions)
	}
	if script.rows.IdempotencyRecords[0].ReplayCount != 1 || script.rows.IdempotencyRecords[0].LastReplayRequestID != "req-replay-second" {
		t.Fatalf("expected replay metadata update, got %#v", script.rows.IdempotencyRecords[0])
	}
}

func TestReplacePersistentRegistryRejectsSameIdempotencyKeyDifferentRequest(t *testing.T) {
	current := loadValidRegistry(t)
	currentRows, err := MapRegistryToPersistentRows(current)
	if err != nil {
		t.Fatalf("map current rows: %v", err)
	}
	incoming := loadValidRegistry(t)
	incoming.Providers[0].ID = "httpbin_public_ip_v1"
	incoming.Providers[0].ProviderID = "httpbin"
	incoming.Providers[0].Metadata["base_url"] = "https://httpbin.org"
	incoming.CredentialMetadata[0].ProviderID = "httpbin"
	incoming.Snapshot.Version = "snapshot_import_replace_v2"
	db, script := openScriptedRegistryDB(t, currentRows)
	defer db.Close()

	if _, err := ReplacePersistentRegistry(context.Background(), db, incoming, ImportReplaceOptions{
		ActorID:        "tester",
		RequestID:      "req-conflict-first",
		IdempotencyKey: "idem-conflict",
		Source:         "test-registry.json",
	}); err != nil {
		t.Fatalf("first replace persistent registry: %v", err)
	}
	conflicting := incoming
	conflicting.Snapshot.Version = "snapshot_import_replace_v3"
	script.execQueries = nil

	_, err = ReplacePersistentRegistry(context.Background(), db, conflicting, ImportReplaceOptions{
		ActorID:        "tester",
		RequestID:      "req-conflict-second",
		IdempotencyKey: "idem-conflict",
		Source:         "test-registry.json",
	})
	if err == nil {
		t.Fatalf("expected idempotency key conflict")
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "IDEMPOTENCY_KEY_CONFLICT" || mutationErr.Retryable {
		t.Fatalf("unexpected conflict error: %#v", mutationErr)
	}
	if containsExec(script.execQueries, "DELETE FROM") {
		t.Fatalf("conflict should not replace mutable rows: %#v", script.execQueries)
	}
}

func TestReplacePersistentRegistryLockConflictFailsWithMutationConflict(t *testing.T) {
	reg := loadValidRegistry(t)
	rows, err := MapRegistryToPersistentRows(reg)
	if err != nil {
		t.Fatalf("map registry rows: %v", err)
	}
	db, script := openScriptedRegistryDB(t, rows)
	script.lockAvailable = false
	defer db.Close()

	_, err = ReplacePersistentRegistry(context.Background(), db, reg, ImportReplaceOptions{ActorID: "tester", RequestID: "req-lock"})
	if err == nil {
		t.Fatalf("expected lock conflict error")
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "REGISTRY_MUTATION_CONFLICT" || !mutationErr.Retryable {
		t.Fatalf("unexpected mutation error: %#v", mutationErr)
	}
	if script.committed || !script.rolledBack {
		t.Fatalf("expected rollback without commit: committed=%v rolledBack=%v", script.committed, script.rolledBack)
	}
}

func TestReplacePersistentRegistryAuditFailureRollsBackMutation(t *testing.T) {
	current := loadValidRegistry(t)
	currentRows, err := MapRegistryToPersistentRows(current)
	if err != nil {
		t.Fatalf("map current rows: %v", err)
	}
	incoming := loadValidRegistry(t)
	incoming.Providers[0].ID = "httpbin_public_ip_v1"
	incoming.Providers[0].ProviderID = "httpbin"
	incoming.Providers[0].Metadata["base_url"] = "https://httpbin.org"
	incoming.CredentialMetadata[0].ProviderID = "httpbin"
	incoming.Snapshot.Version = "snapshot_import_replace_v2"
	db, script := openScriptedRegistryDB(t, currentRows)
	script.failExecContains = "INSERT INTO admin_audit_events"
	defer db.Close()

	_, err = ReplacePersistentRegistry(context.Background(), db, incoming, ImportReplaceOptions{ActorID: "tester", RequestID: "req-audit-fail"})
	if err == nil {
		t.Fatalf("expected audit failure")
	}
	mutationErr, ok := err.(RegistryMutationError)
	if !ok {
		t.Fatalf("expected RegistryMutationError, got %T: %v", err, err)
	}
	if mutationErr.ErrorType != "AUDIT_WRITE_FAILED" {
		t.Fatalf("unexpected mutation error: %#v", mutationErr)
	}
	if script.committed || !script.rolledBack {
		t.Fatalf("expected rollback without commit: committed=%v rolledBack=%v", script.committed, script.rolledBack)
	}
	if len(script.rows.Providers) != 1 || script.rows.Providers[0].ID != currentRows.Providers[0].ID {
		t.Fatalf("expected rollback to preserve previous provider rows: %#v", script.rows.Providers)
	}
}

func containsExec(queries []string, pattern string) bool {
	for _, query := range queries {
		if strings.Contains(query, pattern) {
			return true
		}
	}
	return false
}
