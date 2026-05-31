package registry

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

type PostgresStore struct {
	DB *sql.DB
}

func NewPostgresStore(db *sql.DB) PostgresStore {
	return PostgresStore{DB: db}
}

func (s PostgresStore) Load(ctx context.Context) (*Registry, error) {
	if s.DB == nil {
		return nil, fmt.Errorf("postgres registry db is required")
	}
	tx, err := s.DB.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelRepeatableRead,
		ReadOnly:  true,
	})
	if err != nil {
		return nil, fmt.Errorf("begin registry read transaction: %w", err)
	}
	defer tx.Rollback()

	rows, err := LoadPersistentRows(ctx, tx)
	if err != nil {
		return nil, err
	}
	reg, err := BuildRegistryFromPersistentRows(rows)
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("commit registry read transaction: %w", err)
	}
	return reg, nil
}

type sqlQueryer interface {
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
}

func LoadPersistentRows(ctx context.Context, q sqlQueryer) (PersistentRegistryRows, error) {
	var out PersistentRegistryRows
	var err error
	if out.Projects, err = loadPersistentProjects(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	if out.APIKeys, err = loadPersistentAPIKeys(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	if out.Capabilities, err = loadPersistentCapabilities(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	if out.Providers, err = loadPersistentProviders(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	if out.CredentialMetadata, err = loadPersistentCredentialMetadata(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	if out.RoutingPolicies, err = loadPersistentRoutingPolicies(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	if out.SnapshotConfigs, err = loadPersistentSnapshotConfigs(ctx, q); err != nil {
		return PersistentRegistryRows{}, err
	}
	return out, nil
}

func BuildRegistryFromPersistentRows(rows PersistentRegistryRows) (*Registry, error) {
	canonical := canonicalPersistentRows(rows)
	if len(canonical.RoutingPolicies) != 1 {
		return nil, fmt.Errorf("expected exactly one active routing policy, got %d", len(canonical.RoutingPolicies))
	}
	if len(canonical.SnapshotConfigs) != 1 {
		return nil, fmt.Errorf("expected exactly one active snapshot config, got %d", len(canonical.SnapshotConfigs))
	}

	reg := Registry{}
	for _, row := range canonical.Projects {
		reg.Projects = append(reg.Projects, Project{
			ID:          row.ID,
			Name:        row.Name,
			Status:      row.Status,
			DefaultMode: row.DefaultMode,
		})
	}
	for _, row := range canonical.APIKeys {
		reg.APIKeys = append(reg.APIKeys, APIKey{
			ID:        row.ID,
			ProjectID: row.ProjectID,
			KeyPrefix: row.KeyPrefix,
			Status:    row.Status,
		})
	}
	for _, row := range canonical.Capabilities {
		reg.Capabilities = append(reg.Capabilities, Capability{
			ID:      row.ID,
			Version: row.Version,
			Name:    row.Name,
		})
	}
	for _, row := range canonical.Providers {
		reg.Providers = append(reg.Providers, Provider{
			ID:                row.ID,
			CapabilityID:      row.CapabilityID,
			CapabilityVersion: row.CapabilityVersion,
			ProviderID:        row.ProviderID,
			ProviderVersion:   row.ProviderVersion,
			MappingVersion:    row.MappingVersion,
			ToolID:            row.ToolID,
			Regions:           append([]string(nil), row.Regions...),
			GeoAffinity:       row.GeoAffinity,
			EstimatedCost:     row.EstimatedCost,
			Metadata:          copyStringMap(row.Metadata),
			Status:            row.Status,
		})
	}
	for _, row := range canonical.CredentialMetadata {
		reg.CredentialMetadata = append(reg.CredentialMetadata, CredentialMetadata{
			CredentialID:      row.CredentialID,
			CredentialVersion: row.CredentialVersion,
			OwnerType:         row.OwnerType,
			OwnerID:           row.OwnerID,
			ProviderID:        row.ProviderID,
			AuthType:          row.AuthType,
			InjectionMode:     row.InjectionMode,
			Source:            row.Source,
			Scope:             append([]string(nil), row.Scope...),
			Status:            row.Status,
			RotationHint:      row.RotationHint,
		})
	}
	policy := canonical.RoutingPolicies[0]
	reg.RoutingPolicy = RoutingPolicy{
		Strategy:       policy.Strategy,
		RoutingMode:    policy.RoutingMode,
		RoutingSeed:    policy.RoutingSeed,
		FailoverPolicy: policy.FailoverPolicy,
	}
	config := canonical.SnapshotConfigs[0]
	fetchedAt, err := time.Parse(time.RFC3339, config.FetchedAt)
	if err != nil {
		return nil, fmt.Errorf("snapshot_config %q fetched_at is invalid: %w", config.ID, err)
	}
	reg.Snapshot = SnapshotExportOptions{
		Version:   config.Version,
		FetchedAt: fetchedAt.UTC(),
		TTL:       config.TTL,
		Source:    config.Source,
	}

	reg = CanonicalRegistry(reg)
	if err := reg.Validate(); err != nil {
		return nil, err
	}
	return &reg, nil
}

func loadPersistentProjects(ctx context.Context, q sqlQueryer) ([]PersistentProjectRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT id, name, status, default_mode
FROM projects
WHERE status = 'active'
ORDER BY id`)
	if err != nil {
		return nil, fmt.Errorf("query projects: %w", err)
	}
	defer rows.Close()
	var out []PersistentProjectRow
	for rows.Next() {
		var row PersistentProjectRow
		if err := rows.Scan(&row.ID, &row.Name, &row.Status, &row.DefaultMode); err != nil {
			return nil, fmt.Errorf("scan project: %w", err)
		}
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate projects: %w", err)
	}
	return out, nil
}

func loadPersistentAPIKeys(ctx context.Context, q sqlQueryer) ([]PersistentAPIKeyRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT id, project_id, key_prefix, key_hash, status
FROM api_keys
WHERE status = 'active'
ORDER BY id`)
	if err != nil {
		return nil, fmt.Errorf("query api_keys: %w", err)
	}
	defer rows.Close()
	var out []PersistentAPIKeyRow
	for rows.Next() {
		var row PersistentAPIKeyRow
		if err := rows.Scan(&row.ID, &row.ProjectID, &row.KeyPrefix, &row.KeyHash, &row.Status); err != nil {
			return nil, fmt.Errorf("scan api_key: %w", err)
		}
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate api_keys: %w", err)
	}
	return out, nil
}

func loadPersistentCapabilities(ctx context.Context, q sqlQueryer) ([]PersistentCapabilityRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT id, version, name, status
FROM capabilities
WHERE status = 'active'
ORDER BY id, version`)
	if err != nil {
		return nil, fmt.Errorf("query capabilities: %w", err)
	}
	defer rows.Close()
	var out []PersistentCapabilityRow
	for rows.Next() {
		var row PersistentCapabilityRow
		if err := rows.Scan(&row.ID, &row.Version, &row.Name, &row.Status); err != nil {
			return nil, fmt.Errorf("scan capability: %w", err)
		}
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate capabilities: %w", err)
	}
	return out, nil
}

func loadPersistentProviders(ctx context.Context, q sqlQueryer) ([]PersistentProviderRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT id, capability_id, capability_version, provider_id, provider_version, mapping_version, tool_id, regions, geo_affinity, estimated_cost, metadata, status
FROM providers
WHERE status = 'active'
ORDER BY id`)
	if err != nil {
		return nil, fmt.Errorf("query providers: %w", err)
	}
	defer rows.Close()
	var out []PersistentProviderRow
	for rows.Next() {
		var row PersistentProviderRow
		var regionsRaw any
		var metadataRaw any
		if err := rows.Scan(&row.ID, &row.CapabilityID, &row.CapabilityVersion, &row.ProviderID, &row.ProviderVersion, &row.MappingVersion, &row.ToolID, &regionsRaw, &row.GeoAffinity, &row.EstimatedCost, &metadataRaw, &row.Status); err != nil {
			return nil, fmt.Errorf("scan provider: %w", err)
		}
		regions, err := parsePostgresTextArray(regionsRaw)
		if err != nil {
			return nil, fmt.Errorf("provider %q regions: %w", row.ID, err)
		}
		metadata, err := parseJSONMap(metadataRaw)
		if err != nil {
			return nil, fmt.Errorf("provider %q metadata: %w", row.ID, err)
		}
		row.Regions = regions
		row.Metadata = metadata
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate providers: %w", err)
	}
	return out, nil
}

func loadPersistentCredentialMetadata(ctx context.Context, q sqlQueryer) ([]PersistentCredentialMetadataRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT credential_id, credential_version, owner_type, owner_id, provider_id, auth_type, injection_mode, source, scope, status, rotation_hint
FROM credential_metadata
WHERE status = 'active'
ORDER BY credential_id`)
	if err != nil {
		return nil, fmt.Errorf("query credential_metadata: %w", err)
	}
	defer rows.Close()
	var out []PersistentCredentialMetadataRow
	for rows.Next() {
		var row PersistentCredentialMetadataRow
		var scopeRaw any
		if err := rows.Scan(&row.CredentialID, &row.CredentialVersion, &row.OwnerType, &row.OwnerID, &row.ProviderID, &row.AuthType, &row.InjectionMode, &row.Source, &scopeRaw, &row.Status, &row.RotationHint); err != nil {
			return nil, fmt.Errorf("scan credential_metadata: %w", err)
		}
		scope, err := parsePostgresTextArray(scopeRaw)
		if err != nil {
			return nil, fmt.Errorf("credential_metadata %q scope: %w", row.CredentialID, err)
		}
		row.Scope = scope
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate credential_metadata: %w", err)
	}
	return out, nil
}

func loadPersistentRoutingPolicies(ctx context.Context, q sqlQueryer) ([]PersistentRoutingPolicyRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT id, scope_type, scope_id, strategy, routing_mode, routing_seed, failover_policy, status
FROM routing_policies
WHERE status = 'active' AND scope_type = 'global'
ORDER BY id`)
	if err != nil {
		return nil, fmt.Errorf("query routing_policies: %w", err)
	}
	defer rows.Close()
	var out []PersistentRoutingPolicyRow
	for rows.Next() {
		var row PersistentRoutingPolicyRow
		var seed sql.NullString
		var failoverRaw any
		if err := rows.Scan(&row.ID, &row.ScopeType, &row.ScopeID, &row.Strategy, &row.RoutingMode, &seed, &failoverRaw, &row.Status); err != nil {
			return nil, fmt.Errorf("scan routing_policy: %w", err)
		}
		if seed.Valid {
			row.RoutingSeed = &seed.String
		}
		failover, err := parseFailoverPolicy(failoverRaw)
		if err != nil {
			return nil, fmt.Errorf("routing_policy %q failover_policy: %w", row.ID, err)
		}
		row.FailoverPolicy = failover
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate routing_policies: %w", err)
	}
	return out, nil
}

func loadPersistentSnapshotConfigs(ctx context.Context, q sqlQueryer) ([]PersistentSnapshotConfigRow, error) {
	rows, err := q.QueryContext(ctx, `
SELECT id, version, fetched_at, ttl, source, status
FROM snapshot_configs
WHERE status = 'active'
ORDER BY id`)
	if err != nil {
		return nil, fmt.Errorf("query snapshot_configs: %w", err)
	}
	defer rows.Close()
	var out []PersistentSnapshotConfigRow
	for rows.Next() {
		var row PersistentSnapshotConfigRow
		var fetchedAt time.Time
		if err := rows.Scan(&row.ID, &row.Version, &fetchedAt, &row.TTL, &row.Source, &row.Status); err != nil {
			return nil, fmt.Errorf("scan snapshot_config: %w", err)
		}
		row.FetchedAt = fetchedAt.UTC().Format(time.RFC3339)
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate snapshot_configs: %w", err)
	}
	return out, nil
}

func canonicalPersistentRows(rows PersistentRegistryRows) PersistentRegistryRows {
	canonical := rows
	canonical.Projects = append([]PersistentProjectRow(nil), rows.Projects...)
	canonical.APIKeys = append([]PersistentAPIKeyRow(nil), rows.APIKeys...)
	canonical.Capabilities = append([]PersistentCapabilityRow(nil), rows.Capabilities...)
	canonical.Providers = append([]PersistentProviderRow(nil), rows.Providers...)
	canonical.CredentialMetadata = append([]PersistentCredentialMetadataRow(nil), rows.CredentialMetadata...)
	canonical.RoutingPolicies = append([]PersistentRoutingPolicyRow(nil), rows.RoutingPolicies...)
	canonical.SnapshotConfigs = append([]PersistentSnapshotConfigRow(nil), rows.SnapshotConfigs...)

	sort.Slice(canonical.Projects, func(i, j int) bool { return canonical.Projects[i].ID < canonical.Projects[j].ID })
	sort.Slice(canonical.APIKeys, func(i, j int) bool { return canonical.APIKeys[i].ID < canonical.APIKeys[j].ID })
	sort.Slice(canonical.Capabilities, func(i, j int) bool {
		if canonical.Capabilities[i].ID == canonical.Capabilities[j].ID {
			return canonical.Capabilities[i].Version < canonical.Capabilities[j].Version
		}
		return canonical.Capabilities[i].ID < canonical.Capabilities[j].ID
	})
	sort.Slice(canonical.Providers, func(i, j int) bool { return canonical.Providers[i].ID < canonical.Providers[j].ID })
	for i := range canonical.Providers {
		canonical.Providers[i].Regions = append([]string(nil), canonical.Providers[i].Regions...)
		sort.Strings(canonical.Providers[i].Regions)
		canonical.Providers[i].Metadata = copyStringMap(canonical.Providers[i].Metadata)
	}
	sort.Slice(canonical.CredentialMetadata, func(i, j int) bool {
		return canonical.CredentialMetadata[i].CredentialID < canonical.CredentialMetadata[j].CredentialID
	})
	for i := range canonical.CredentialMetadata {
		canonical.CredentialMetadata[i].Scope = append([]string(nil), canonical.CredentialMetadata[i].Scope...)
		sort.Strings(canonical.CredentialMetadata[i].Scope)
	}
	sort.Slice(canonical.RoutingPolicies, func(i, j int) bool { return canonical.RoutingPolicies[i].ID < canonical.RoutingPolicies[j].ID })
	sort.Slice(canonical.SnapshotConfigs, func(i, j int) bool { return canonical.SnapshotConfigs[i].ID < canonical.SnapshotConfigs[j].ID })
	return canonical
}

func parseJSONMap(raw any) (map[string]string, error) {
	data, err := rawBytes(raw)
	if err != nil {
		return nil, err
	}
	if len(data) == 0 {
		return map[string]string{}, nil
	}
	var out map[string]string
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	if out == nil {
		return map[string]string{}, nil
	}
	return out, nil
}

func parseFailoverPolicy(raw any) (*FailoverPolicy, error) {
	data, err := rawBytes(raw)
	if err != nil {
		return nil, err
	}
	if len(data) == 0 || string(data) == "null" {
		return nil, nil
	}
	var out FailoverPolicy
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func rawBytes(raw any) ([]byte, error) {
	switch value := raw.(type) {
	case nil:
		return nil, nil
	case []byte:
		return value, nil
	case string:
		return []byte(value), nil
	default:
		return nil, fmt.Errorf("unsupported raw value type %T", raw)
	}
}

func parsePostgresTextArray(raw any) ([]string, error) {
	switch value := raw.(type) {
	case nil:
		return nil, nil
	case []string:
		return append([]string(nil), value...), nil
	case []byte:
		return parsePostgresTextArrayString(string(value))
	case string:
		return parsePostgresTextArrayString(value)
	default:
		return nil, fmt.Errorf("unsupported text array type %T", raw)
	}
}

func parsePostgresTextArrayString(value string) ([]string, error) {
	value = strings.TrimSpace(value)
	if value == "" || value == "{}" {
		return nil, nil
	}
	if !strings.HasPrefix(value, "{") || !strings.HasSuffix(value, "}") {
		return nil, fmt.Errorf("expected postgres text array literal, got %q", value)
	}
	body := strings.TrimSuffix(strings.TrimPrefix(value, "{"), "}")
	var out []string
	var current strings.Builder
	inQuotes := false
	escaped := false
	for _, r := range body {
		switch {
		case escaped:
			current.WriteRune(r)
			escaped = false
		case r == '\\':
			escaped = true
		case r == '"':
			inQuotes = !inQuotes
		case r == ',' && !inQuotes:
			out = append(out, current.String())
			current.Reset()
		default:
			current.WriteRune(r)
		}
	}
	if inQuotes || escaped {
		return nil, fmt.Errorf("unterminated postgres text array literal")
	}
	out = append(out, current.String())
	return out, nil
}

func postgresTextArrayLiteral(values []string) string {
	if len(values) == 0 {
		return "{}"
	}
	parts := make([]string, 0, len(values))
	for _, value := range values {
		escaped := strings.ReplaceAll(value, `\`, `\\`)
		escaped = strings.ReplaceAll(escaped, `"`, `\"`)
		parts = append(parts, `"`+escaped+`"`)
	}
	return "{" + strings.Join(parts, ",") + "}"
}
