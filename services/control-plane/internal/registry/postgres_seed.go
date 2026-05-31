package registry

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
)

func SeedPostgresRegistry(ctx context.Context, db *sql.DB, reg Registry) (PersistentRegistryRows, error) {
	if db == nil {
		return PersistentRegistryRows{}, fmt.Errorf("postgres registry db is required")
	}
	rows, err := MapRegistryToPersistentRows(reg)
	if err != nil {
		return PersistentRegistryRows{}, err
	}
	tx, err := db.BeginTx(ctx, &sql.TxOptions{})
	if err != nil {
		return PersistentRegistryRows{}, fmt.Errorf("begin registry seed transaction: %w", err)
	}
	defer tx.Rollback()
	if err := seedPersistentRows(ctx, tx, rows); err != nil {
		return PersistentRegistryRows{}, err
	}
	if err := tx.Commit(); err != nil {
		return PersistentRegistryRows{}, fmt.Errorf("commit registry seed transaction: %w", err)
	}
	return rows, nil
}

func seedPersistentRows(ctx context.Context, tx *sql.Tx, rows PersistentRegistryRows) error {
	for _, row := range rows.Projects {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO projects (id, name, status, default_mode)
VALUES ($1, $2, $3, $4)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    status = EXCLUDED.status,
    default_mode = EXCLUDED.default_mode,
    updated_at = now()`, row.ID, row.Name, row.Status, row.DefaultMode); err != nil {
			return fmt.Errorf("seed project %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.APIKeys {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO api_keys (id, project_id, key_prefix, key_hash, status)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (id) DO UPDATE
SET project_id = EXCLUDED.project_id,
    key_prefix = EXCLUDED.key_prefix,
    key_hash = EXCLUDED.key_hash,
    status = EXCLUDED.status,
    updated_at = now()`, row.ID, row.ProjectID, row.KeyPrefix, row.KeyHash, row.Status); err != nil {
			return fmt.Errorf("seed api_key %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.Capabilities {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO capabilities (id, version, name, status)
VALUES ($1, $2, $3, $4)
ON CONFLICT (id, version) DO UPDATE
SET name = EXCLUDED.name,
    status = EXCLUDED.status,
    updated_at = now()`, row.ID, row.Version, row.Name, row.Status); err != nil {
			return fmt.Errorf("seed capability %q@%q: %w", row.ID, row.Version, err)
		}
	}
	for _, row := range rows.Providers {
		metadata, err := json.Marshal(row.Metadata)
		if err != nil {
			return fmt.Errorf("encode provider %q metadata: %w", row.ID, err)
		}
		if _, err := tx.ExecContext(ctx, `
INSERT INTO providers (id, capability_id, capability_version, provider_id, provider_version, mapping_version, tool_id, regions, geo_affinity, estimated_cost, metadata, status)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::text[], $9, $10, $11::jsonb, $12)
ON CONFLICT (id) DO UPDATE
SET capability_id = EXCLUDED.capability_id,
    capability_version = EXCLUDED.capability_version,
    provider_id = EXCLUDED.provider_id,
    provider_version = EXCLUDED.provider_version,
    mapping_version = EXCLUDED.mapping_version,
    tool_id = EXCLUDED.tool_id,
    regions = EXCLUDED.regions,
    geo_affinity = EXCLUDED.geo_affinity,
    estimated_cost = EXCLUDED.estimated_cost,
    metadata = EXCLUDED.metadata,
    status = EXCLUDED.status,
    updated_at = now()`, row.ID, row.CapabilityID, row.CapabilityVersion, row.ProviderID, row.ProviderVersion, row.MappingVersion, row.ToolID, postgresTextArrayLiteral(row.Regions), row.GeoAffinity, row.EstimatedCost, metadata, row.Status); err != nil {
			return fmt.Errorf("seed provider %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.CredentialMetadata {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO credential_metadata (credential_id, credential_version, owner_type, owner_id, provider_id, auth_type, injection_mode, source, scope, status, rotation_hint)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text[], $10, $11)
ON CONFLICT (credential_id) DO UPDATE
SET credential_version = EXCLUDED.credential_version,
    owner_type = EXCLUDED.owner_type,
    owner_id = EXCLUDED.owner_id,
    provider_id = EXCLUDED.provider_id,
    auth_type = EXCLUDED.auth_type,
    injection_mode = EXCLUDED.injection_mode,
    source = EXCLUDED.source,
    scope = EXCLUDED.scope,
    status = EXCLUDED.status,
    rotation_hint = EXCLUDED.rotation_hint,
    updated_at = now()`, row.CredentialID, row.CredentialVersion, row.OwnerType, row.OwnerID, row.ProviderID, row.AuthType, row.InjectionMode, row.Source, postgresTextArrayLiteral(row.Scope), row.Status, row.RotationHint); err != nil {
			return fmt.Errorf("seed credential_metadata %q: %w", row.CredentialID, err)
		}
	}
	for _, row := range rows.RoutingPolicies {
		failover, err := json.Marshal(row.FailoverPolicy)
		if err != nil {
			return fmt.Errorf("encode routing_policy %q failover_policy: %w", row.ID, err)
		}
		if _, err := tx.ExecContext(ctx, `
INSERT INTO routing_policies (id, scope_type, scope_id, strategy, routing_mode, routing_seed, failover_policy, status)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
ON CONFLICT (id) DO UPDATE
SET scope_type = EXCLUDED.scope_type,
    scope_id = EXCLUDED.scope_id,
    strategy = EXCLUDED.strategy,
    routing_mode = EXCLUDED.routing_mode,
    routing_seed = EXCLUDED.routing_seed,
    failover_policy = EXCLUDED.failover_policy,
    status = EXCLUDED.status,
    updated_at = now()`, row.ID, row.ScopeType, row.ScopeID, row.Strategy, row.RoutingMode, row.RoutingSeed, failover, row.Status); err != nil {
			return fmt.Errorf("seed routing_policy %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.SnapshotConfigs {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO snapshot_configs (id, version, fetched_at, ttl, source, status)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (id) DO UPDATE
SET version = EXCLUDED.version,
    fetched_at = EXCLUDED.fetched_at,
    ttl = EXCLUDED.ttl,
    source = EXCLUDED.source,
    status = EXCLUDED.status,
    updated_at = now()`, row.ID, row.Version, row.FetchedAt, row.TTL, row.Source, row.Status); err != nil {
			return fmt.Errorf("seed snapshot_config %q: %w", row.ID, err)
		}
	}
	for _, row := range rows.RegistryRevisions {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO registry_revisions (registry_fingerprint, snapshot_version, source_store, source_revision)
VALUES ($1, $2, $3, $4)`, row.RegistryFingerprint, row.SnapshotVersion, row.SourceStore, row.SourceRevision); err != nil {
			return fmt.Errorf("seed registry_revision %q: %w", row.RegistryFingerprint, err)
		}
	}
	return nil
}
