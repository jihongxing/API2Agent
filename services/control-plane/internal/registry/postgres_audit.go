package registry

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
)

type PersistentAuditSink interface {
	RecordRegistryRevision(ctx context.Context, row PersistentRegistryRevisionRow) error
	RecordArtifactPublication(ctx context.Context, row PersistentArtifactPublicationRow) error
	RecordAdminAuditEvent(ctx context.Context, row PersistentAdminAuditEventRow) error
}

type PostgresAuditSink struct {
	DB *sql.DB
}

func NewPostgresAuditSink(db *sql.DB) PostgresAuditSink {
	return PostgresAuditSink{DB: db}
}

func (s PostgresAuditSink) RecordRegistryRevision(ctx context.Context, row PersistentRegistryRevisionRow) error {
	if s.DB == nil {
		return fmt.Errorf("postgres audit db is required")
	}
	if _, err := s.DB.ExecContext(ctx, `
INSERT INTO registry_revisions (registry_fingerprint, snapshot_version, source_store, source_revision)
VALUES ($1, $2, $3, $4)`, row.RegistryFingerprint, row.SnapshotVersion, row.SourceStore, row.SourceRevision); err != nil {
		return fmt.Errorf("record registry revision: %w", err)
	}
	return nil
}

func (s PostgresAuditSink) RecordArtifactPublication(ctx context.Context, row PersistentArtifactPublicationRow) error {
	if s.DB == nil {
		return fmt.Errorf("postgres audit db is required")
	}
	if _, err := s.DB.ExecContext(ctx, `
INSERT INTO snapshot_artifact_publications (snapshot_version, registry_fingerprint, snapshot_digest, artifact_uri, manifest_uri, distribution_uri, status)
VALUES ($1, $2, $3, $4, $5, $6, $7)`, row.SnapshotVersion, row.RegistryFingerprint, row.SnapshotDigest, row.ArtifactURI, row.ManifestURI, row.DistributionURI, row.Status); err != nil {
		return fmt.Errorf("record artifact publication: %w", err)
	}
	return nil
}

func (s PostgresAuditSink) RecordAdminAuditEvent(ctx context.Context, row PersistentAdminAuditEventRow) error {
	if s.DB == nil {
		return fmt.Errorf("postgres audit db is required")
	}
	metadata, err := json.Marshal(row.Metadata)
	if err != nil {
		return fmt.Errorf("encode admin audit metadata: %w", err)
	}
	if _, err := s.DB.ExecContext(ctx, `
INSERT INTO admin_audit_events (actor_id, action, resource_type, resource_id, request_id, outcome, error_type, metadata)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)`, row.ActorID, row.Action, row.ResourceType, row.ResourceID, row.RequestID, row.Outcome, row.ErrorType, metadata); err != nil {
		return fmt.Errorf("record admin audit event: %w", err)
	}
	return nil
}
