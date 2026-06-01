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

CREATE TABLE hosted_subjects (
  id TEXT PRIMARY KEY,
  external_subject_ref TEXT NOT NULL DEFAULT '',
  display_name TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'disabled')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX hosted_subjects_external_ref_unique
  ON hosted_subjects (external_subject_ref)
  WHERE external_subject_ref <> '';

CREATE TABLE hosted_project_memberships (
  id BIGSERIAL PRIMARY KEY,
  subject_id TEXT NOT NULL REFERENCES hosted_subjects(id),
  actor_id TEXT NOT NULL,
  project_id TEXT NOT NULL REFERENCES projects(id),
  organization_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'revoked')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (actor_id <> ''),
  CHECK (organization_id <> '')
);

CREATE UNIQUE INDEX hosted_project_memberships_subject_project_unique
  ON hosted_project_memberships (subject_id, project_id);

CREATE INDEX hosted_project_memberships_project_status
  ON hosted_project_memberships (project_id, status);

CREATE TABLE hosted_roles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('project', 'organization', 'platform')),
  public_assignable BOOLEAN NOT NULL DEFAULT false,
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE hosted_role_bindings (
  id BIGSERIAL PRIMARY KEY,
  subject_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  organization_id TEXT NOT NULL,
  role_id TEXT NOT NULL REFERENCES hosted_roles(id),
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  source TEXT NOT NULL CHECK (source IN ('seed', 'system', 'operator')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (subject_id, project_id) REFERENCES hosted_project_memberships(subject_id, project_id),
  CHECK (organization_id <> '')
);

CREATE UNIQUE INDEX hosted_role_bindings_active_unique
  ON hosted_role_bindings (subject_id, project_id, role_id)
  WHERE status = 'active';

CREATE INDEX hosted_role_bindings_project_status
  ON hosted_role_bindings (project_id, status);

CREATE TABLE hosted_permission_grants (
  id BIGSERIAL PRIMARY KEY,
  role_id TEXT NOT NULL REFERENCES hosted_roles(id),
  permission TEXT NOT NULL CHECK (permission <> ''),
  scope_type TEXT NOT NULL CHECK (scope_type IN ('project', 'organization', 'platform')),
  status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX hosted_permission_grants_active_unique
  ON hosted_permission_grants (role_id, permission, scope_type)
  WHERE status = 'active';

CREATE INDEX hosted_permission_grants_permission_status
  ON hosted_permission_grants (permission, status);

CREATE TABLE hosted_policy_versions (
  id BIGSERIAL PRIMARY KEY,
  policy_source TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  policy_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'superseded', 'revoked')),
  activated_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (policy_source <> ''),
  CHECK (policy_version <> ''),
  CHECK (policy_fingerprint LIKE 'sha256:%')
);

CREATE UNIQUE INDEX hosted_policy_versions_source_version_unique
  ON hosted_policy_versions (policy_source, policy_version);

CREATE UNIQUE INDEX hosted_policy_versions_one_active_source
  ON hosted_policy_versions (policy_source)
  WHERE status = 'active';

CREATE TABLE hosted_permission_decisions (
  id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL REFERENCES hosted_subjects(id),
  actor_id TEXT NOT NULL,
  project_id TEXT NOT NULL REFERENCES projects(id),
  organization_id TEXT NOT NULL,
  token_id TEXT NOT NULL DEFAULT '',
  required_permission TEXT NOT NULL DEFAULT '',
  allowed BOOLEAN NOT NULL,
  deny_reason TEXT NOT NULL DEFAULT '',
  roles TEXT[] NOT NULL DEFAULT '{}'::text[],
  permissions TEXT[] NOT NULL DEFAULT '{}'::text[],
  policy_source TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  policy_fingerprint TEXT NOT NULL,
  resolved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (policy_source, policy_version) REFERENCES hosted_policy_versions(policy_source, policy_version),
  CHECK (id <> ''),
  CHECK (actor_id <> ''),
  CHECK (organization_id <> ''),
  CHECK (required_permission <> ''),
  CHECK (policy_fingerprint LIKE 'sha256:%')
);

CREATE INDEX hosted_permission_decisions_subject_project_resolved_at
  ON hosted_permission_decisions (subject_id, project_id, resolved_at DESC);

CREATE INDEX hosted_permission_decisions_policy_version
  ON hosted_permission_decisions (policy_source, policy_version);
