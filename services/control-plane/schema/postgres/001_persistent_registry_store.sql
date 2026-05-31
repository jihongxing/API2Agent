-- API2Agent Go Control Plane Persistent Registry Store Schema v0
--
-- This schema is a draft for local schema/load-parity work. It is not wired
-- into the runtime service yet. FileStore remains the default store.

CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  default_mode TEXT NOT NULL DEFAULT '' CHECK (default_mode = '' OR default_mode IN ('direct', 'proxy', 'shadow', 'replay')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  key_prefix TEXT NOT NULL DEFAULT '',
  key_hash TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled', 'revoked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE capabilities (
  id TEXT NOT NULL,
  version TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, version)
);

CREATE TABLE providers (
  id TEXT PRIMARY KEY,
  capability_id TEXT NOT NULL,
  capability_version TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  provider_version TEXT NOT NULL,
  mapping_version TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  regions TEXT[] NOT NULL,
  geo_affinity TEXT NOT NULL,
  estimated_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (capability_id, capability_version) REFERENCES capabilities(id, version),
  CHECK (array_length(regions, 1) > 0),
  CHECK (status <> 'active' OR metadata ? 'base_url')
);

CREATE TABLE credential_metadata (
  credential_id TEXT PRIMARY KEY,
  credential_version TEXT NOT NULL DEFAULT '',
  owner_type TEXT NOT NULL CHECK (owner_type IN ('user', 'project', 'platform', 'provider')),
  owner_id TEXT NOT NULL,
  provider_id TEXT NOT NULL,
  auth_type TEXT NOT NULL CHECK (auth_type IN ('api_key', 'bearer', 'basic', 'oauth', 'none')),
  injection_mode TEXT NOT NULL CHECK (injection_mode IN ('header', 'query', 'body', 'none')),
  source TEXT NOT NULL CHECK (source IN ('env', 'config', 'inline', 'vault', 'none')),
  scope TEXT[] NOT NULL DEFAULT '{}'::text[],
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled', 'expired')),
  rotation_hint TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE routing_policies (
  id TEXT PRIMARY KEY,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'project', 'capability')),
  scope_id TEXT NOT NULL DEFAULT '',
  strategy TEXT NOT NULL CHECK (strategy IN ('first', 'lowest_cost', 'lowest_latency', 'region_aware_latency', 'highest_success_rate', 'balanced')),
  routing_mode TEXT NOT NULL CHECK (routing_mode IN ('deterministic', 'stochastic')),
  routing_seed TEXT,
  failover_policy JSONB,
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX routing_policies_one_active_global
  ON routing_policies (scope_type)
  WHERE scope_type = 'global' AND status = 'active';

CREATE TABLE snapshot_configs (
  id TEXT PRIMARY KEY,
  version TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL,
  ttl TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('push', 'pull')),
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX snapshot_configs_one_active
  ON snapshot_configs (status)
  WHERE status = 'active';

CREATE TABLE registry_revisions (
  id BIGSERIAL PRIMARY KEY,
  registry_fingerprint TEXT NOT NULL,
  snapshot_version TEXT NOT NULL,
  source_store TEXT NOT NULL,
  source_revision TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE snapshot_artifact_publications (
  id BIGSERIAL PRIMARY KEY,
  snapshot_version TEXT NOT NULL,
  registry_fingerprint TEXT NOT NULL,
  snapshot_digest TEXT NOT NULL,
  artifact_uri TEXT NOT NULL,
  manifest_uri TEXT NOT NULL,
  distribution_uri TEXT NOT NULL,
  published_by TEXT NOT NULL DEFAULT '',
  published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL CHECK (status IN ('pending', 'published', 'failed', 'replaced'))
);

CREATE UNIQUE INDEX snapshot_artifact_publications_one_active_version
  ON snapshot_artifact_publications (snapshot_version)
  WHERE status IN ('pending', 'published');

CREATE TABLE admin_audit_events (
  id BIGSERIAL PRIMARY KEY,
  actor_id TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL DEFAULT '',
  request_id TEXT NOT NULL DEFAULT '',
  outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failure')),
  error_type TEXT NOT NULL DEFAULT '',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE admin_mutation_idempotency_records (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT 'control_plane',
  actor_id TEXT NOT NULL DEFAULT '',
  operation TEXT NOT NULL,
  idempotency_key_hash TEXT NOT NULL,
  idempotency_key_prefix TEXT NOT NULL DEFAULT '',
  idempotency_key_hash_algorithm TEXT NOT NULL DEFAULT 'sha256',
  request_fingerprint TEXT NOT NULL,
  request_fingerprint_algorithm TEXT NOT NULL DEFAULT 'sha256',
  request_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_request_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('processing', 'succeeded')),
  response_status_code INTEGER,
  response_body JSONB,
  response_fingerprint TEXT NOT NULL DEFAULT '',
  registry_fingerprint TEXT NOT NULL DEFAULT '',
  previous_registry_fingerprint TEXT NOT NULL DEFAULT '',
  snapshot_version TEXT NOT NULL DEFAULT '',
  noop BOOLEAN NOT NULL DEFAULT false,
  registry_revision_id BIGINT REFERENCES registry_revisions(id),
  admin_audit_event_id BIGINT REFERENCES admin_audit_events(id),
  replay_count BIGINT NOT NULL DEFAULT 0,
  last_replay_request_id TEXT NOT NULL DEFAULT '',
  last_replayed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX admin_mutation_idempotency_records_unique_key
  ON admin_mutation_idempotency_records (
    project_id,
    actor_id,
    operation,
    idempotency_key_hash
  );

CREATE INDEX admin_mutation_idempotency_records_expires_at
  ON admin_mutation_idempotency_records (expires_at);

CREATE INDEX admin_mutation_idempotency_records_request_fingerprint
  ON admin_mutation_idempotency_records (request_fingerprint);
