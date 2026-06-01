from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "go_control_plane_hosted_admin_gateway_contract_dogfood.py"


def load_harness_module():
    spec = importlib.util.spec_from_file_location("hosted_admin_gateway_contract", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_permission_source_resolves_public_principals_and_denies_before_forwarding() -> None:
    harness = load_harness_module()

    admin = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
        harness.PERMISSION_REGISTRY_IMPORT_REPLACE,
    )
    assert admin.allowed
    assert admin.actor_id == harness.HARNESS_ACTOR_ID
    assert harness.PERMISSION_REGISTRY_IMPORT_REPLACE in admin.permissions
    assert harness.PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE in admin.permissions
    assert admin.policy_source == harness.HOSTED_PERMISSION_STORE_SOURCE
    assert admin.policy_version == harness.HOSTED_POLICY_VERSION
    assert admin.policy_fingerprint == harness.HOSTED_POLICY_FINGERPRINT
    assert admin.required_permission == harness.PERMISSION_REGISTRY_IMPORT_REPLACE
    assert admin.decision_id.startswith("decision-")

    readonly_validate = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_READONLY_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    assert readonly_validate.allowed
    assert readonly_validate.actor_id == harness.READONLY_POLICY.actor_id

    readonly_import = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_READONLY_TOKEN}"},
        harness.PERMISSION_REGISTRY_IMPORT_REPLACE,
    )
    assert not readonly_import.allowed
    assert readonly_import.status == 403
    assert readonly_import.error_type == "PUBLIC_AUTHZ_DENIED"
    assert readonly_import.policy_fingerprint == harness.HOSTED_POLICY_FINGERPRINT


def test_permission_source_failures_are_typed_gateway_local_decisions() -> None:
    harness = load_harness_module()

    missing = harness.resolve_gateway_admin_principal({}, harness.PERMISSION_REGISTRY_VALIDATE)
    assert missing.status == 401
    assert missing.error_type == "PUBLIC_AUTH_REQUIRED"

    invalid = harness.resolve_gateway_admin_principal(
        {"Authorization": "Bearer unknown-public-token"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    assert invalid.status == 401
    assert invalid.error_type == "PUBLIC_AUTH_INVALID"

    unavailable = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
        permission_source_available=False,
    )
    assert unavailable.status == 503
    assert unavailable.error_type == "PERMISSION_SOURCE_UNAVAILABLE"


def test_permission_store_membership_revocation_and_stale_policy_fail_closed() -> None:
    harness = load_harness_module()

    no_membership = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_NO_MEMBERSHIP_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    assert no_membership.status == 403
    assert no_membership.error_type == "PUBLIC_AUTHZ_DENIED"

    suspended = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_SUSPENDED_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    assert suspended.status == 403
    assert suspended.error_type == "PUBLIC_AUTHZ_DENIED"
    assert suspended.project_id == harness.HARNESS_PROJECT_ID

    revoked_store = harness.DEFAULT_PERMISSION_STORE.without_permission(
        "project_revoked",
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    revoked = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_REVOKED_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
        permission_store=revoked_store,
    )
    assert revoked.status == 403
    assert revoked.error_type == "PUBLIC_AUTHZ_DENIED"
    assert harness.PERMISSION_REGISTRY_VALIDATE not in revoked.permissions
    assert revoked.policy_version.endswith("-revoked")

    stale = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
        permission_store=harness.DEFAULT_PERMISSION_STORE.with_stale_policy(),
    )
    assert stale.status == 503
    assert stale.error_type == "PERMISSION_SOURCE_UNAVAILABLE"
    assert stale.subject_id == harness.HARNESS_PRINCIPAL_ID


def test_forwarded_headers_strip_public_identity_and_inject_trusted_claims() -> None:
    harness = load_harness_module()
    decision = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )

    forwarded = harness.forwarded_headers(
        {
            "Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}",
            "X-Actor-ID": "caller-controlled",
            "X-API2Agent-Principal-ID": "spoofed",
            "X-Request-ID": "req-1",
            "Idempotency-Key": "idem-1",
            "Cookie": "session=caller",
        },
        decision,
        gateway_secret=harness.GATEWAY_SECRET,
        gateway_key_id=harness.GATEWAY_KEY_ID,
    )

    assert "Authorization" not in forwarded
    assert "X-Actor-ID" not in forwarded
    assert "Cookie" not in forwarded
    assert forwarded["X-Request-ID"] == "req-1"
    assert forwarded["Idempotency-Key"] == "idem-1"
    assert forwarded["X-API2Agent-Principal-ID"] == harness.HARNESS_PRINCIPAL_ID
    assert forwarded["X-API2Agent-Actor-ID"] == harness.HARNESS_ACTOR_ID
    assert forwarded["X-API2Agent-Project-ID"] == harness.HARNESS_PROJECT_ID
    assert forwarded["X-API2Agent-Gateway-Key-ID"] == harness.GATEWAY_KEY_ID
    assert harness.PERMISSION_REGISTRY_VALIDATE in forwarded["X-API2Agent-Permissions"]
    assert forwarded["X-API2Agent-Permission-Source"] == harness.HOSTED_PERMISSION_STORE_SOURCE
    assert forwarded["X-API2Agent-Policy-Version"] == harness.HOSTED_POLICY_VERSION
    assert forwarded["X-API2Agent-Policy-Fingerprint"] == harness.HOSTED_POLICY_FINGERPRINT
    assert forwarded["X-API2Agent-Permission-Decision-ID"] == decision.decision_id


def test_read_model_permission_source_maps_helper_payload_and_fail_closed() -> None:
    harness = load_harness_module()

    class FakeResult:
        stdout = """
{
  "allowed": true,
  "status": 200,
  "error_type": "",
  "deny_reason": "",
  "subject_id": "gateway-harness-principal",
  "actor_id": "gateway-harness-actor",
  "project_id": "gateway-harness-project",
  "organization_id": "gateway-harness-org",
  "token_id": "gateway-harness-token-admin",
  "roles": ["dogfood", "project_admin"],
  "permissions": ["control_plane.registry.validate"],
  "required_permission": "control_plane.registry.validate",
  "policy_source": "hosted-permission-store-fixture",
  "policy_version": "hosted-policy-v1",
  "policy_fingerprint": "sha256:hosted-permission-store-fixture-v1",
  "decision_id": "decision-readmodel",
  "permission_source": "hosted-permission-store-fixture",
  "resolved_at": "2026-06-01T00:00:00Z"
}
"""

    calls = []
    original_run = harness.run

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return FakeResult()

    harness.run = fake_run
    try:
        source = harness.HostedReadModelPermissionSource(
            postgres_dsn="postgres://api2agent:secret@127.0.0.1:5432/api2agent?sslmode=disable",
            lookup_binary=harness.Path("lookup"),
        )
        decision = harness.resolve_gateway_admin_principal(
            {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
            harness.PERMISSION_REGISTRY_VALIDATE,
            permission_source=source,
        )
    finally:
        harness.run = original_run

    assert decision.allowed
    assert decision.decision_id == "decision-readmodel"
    assert decision.actor_id == harness.HARNESS_ACTOR_ID
    assert harness.PERMISSION_REGISTRY_VALIDATE in decision.permissions
    assert calls
    assert "--external-subject-ref" in calls[0]
    assert "dogfood/idp/admin" in calls[0]
    assert harness.PUBLIC_ADMIN_TOKEN not in calls[0]

    def failing_run(cmd, **kwargs):
        raise RuntimeError("lookup failed")

    harness.run = failing_run
    try:
        source = harness.HostedReadModelPermissionSource(
            postgres_dsn="postgres://api2agent:secret@127.0.0.1:5432/api2agent?sslmode=disable",
            lookup_binary=harness.Path("lookup"),
        )
        failed = harness.resolve_gateway_admin_principal(
            {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
            harness.PERMISSION_REGISTRY_VALIDATE,
            permission_source=source,
        )
    finally:
        harness.run = original_run

    assert not failed.allowed
    assert failed.status == 503
    assert failed.error_type == "PERMISSION_SOURCE_UNAVAILABLE"


def test_hosted_permission_decision_persistence_writes_secret_safe_sql() -> None:
    harness = load_harness_module()
    captured_sql = []
    original_execute_postgres = harness.execute_postgres
    original_query_postgres_json = harness.query_postgres_json

    def fake_execute_postgres(container, sql):
        captured_sql.append(sql)

    def fake_query_postgres_json(container, sql):
        return []

    decision = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}", "X-Request-ID": "req-persist-1"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    harness.execute_postgres = fake_execute_postgres
    harness.query_postgres_json = fake_query_postgres_json
    try:
        persistence = harness.HostedPermissionDecisionPersistence("container")
        persistence.persist(
            decision,
            method="POST",
            path="/v1/admin/registry/validate",
            headers={"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}", "X-Request-ID": "req-persist-1"},
            gateway_key_id=harness.GATEWAY_KEY_ID,
        )
    finally:
        harness.execute_postgres = original_execute_postgres
        harness.query_postgres_json = original_query_postgres_json

    assert captured_sql
    sql = captured_sql[0]
    assert "INSERT INTO hosted_permission_decisions" in sql
    assert "evidence_fingerprint" in sql
    metadata = {
        "decision_status": decision.status,
        "permission_source": decision.permission_source,
        "persistence_version": harness.HOSTED_PERMISSION_DECISION_PERSISTENCE_VERSION,
        "production_boundary_version": harness.HOSTED_PERMISSION_DECISION_PRODUCTION_BOUNDARY_VERSION,
        "persistence_timeout_ms": 2000,
        "persistence_retry_budget": 2,
        "retention_policy_version": harness.HOSTED_PERMISSION_DECISION_RETENTION_POLICY_VERSION,
        "retention_class": "security",
        "retain_until": harness.rfc3339_add_days(decision.resolved_at, harness.HOSTED_PERMISSION_DECISION_RETENTION_DAYS),
        "history_visibility": harness.HOSTED_PERMISSION_DECISION_HISTORY_VISIBILITY,
        "redaction_policy_version": harness.HOSTED_PERMISSION_DECISION_REDACTION_POLICY_VERSION,
        "legal_hold": False,
        "request_id": "req-persist-1",
        "method": "POST",
        "path": "/v1/admin/registry/validate",
        "gateway_key_id": harness.GATEWAY_KEY_ID,
    }
    expected_fingerprint = harness.permission_decision_evidence_fingerprint(
        harness.canonical_permission_decision_evidence(decision, metadata)
    )
    assert expected_fingerprint in sql
    assert '"request_id": "req-persist-1"' in sql
    assert harness.HOSTED_PERMISSION_DECISION_PRODUCTION_BOUNDARY_VERSION in sql
    assert harness.HOSTED_PERMISSION_DECISION_PERSISTENCE_VERSION in sql
    assert harness.HOSTED_PERMISSION_DECISION_RETENTION_POLICY_VERSION in sql
    assert harness.HOSTED_PERMISSION_DECISION_REDACTION_POLICY_VERSION in sql
    assert '"history_visibility": "tenant_visible_candidate"' in sql
    assert '"retention_class": "security"' in sql
    assert harness.HOSTED_POLICY_FINGERPRINT in sql
    assert harness.PUBLIC_ADMIN_TOKEN not in sql
    assert harness.GATEWAY_SECRET not in sql
    assert "Authorization" not in sql


def test_hosted_permission_decision_persistence_accepts_equivalent_duplicate() -> None:
    harness = load_harness_module()
    captured_sql = []
    original_execute_postgres = harness.execute_postgres
    original_query_postgres_json = harness.query_postgres_json

    def fake_execute_postgres(container, sql):
        captured_sql.append(sql)

    decision = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}", "X-Request-ID": "req-duplicate"},
        harness.PERMISSION_REGISTRY_VALIDATE,
        resolved_at="2026-06-02T00:00:00.000000Z",
    )

    def fake_query_postgres_json(container, sql):
        if not captured_sql:
            return []
        metadata = {
            "decision_status": decision.status,
            "permission_source": decision.permission_source,
            "persistence_version": harness.HOSTED_PERMISSION_DECISION_PERSISTENCE_VERSION,
            "production_boundary_version": harness.HOSTED_PERMISSION_DECISION_PRODUCTION_BOUNDARY_VERSION,
            "persistence_timeout_ms": 2000,
            "persistence_retry_budget": 2,
            "retention_policy_version": harness.HOSTED_PERMISSION_DECISION_RETENTION_POLICY_VERSION,
            "retention_class": "security",
            "retain_until": harness.rfc3339_add_days(decision.resolved_at, harness.HOSTED_PERMISSION_DECISION_RETENTION_DAYS),
            "history_visibility": harness.HOSTED_PERMISSION_DECISION_HISTORY_VISIBILITY,
            "redaction_policy_version": harness.HOSTED_PERMISSION_DECISION_REDACTION_POLICY_VERSION,
            "legal_hold": False,
            "request_id": "req-duplicate",
            "method": "POST",
            "path": "/v1/admin/registry/validate",
            "gateway_key_id": harness.GATEWAY_KEY_ID,
        }
        return [
            {
                "subject_id": decision.subject_id,
                "actor_id": decision.actor_id,
                "project_id": decision.project_id,
                "organization_id": decision.organization_id,
                "token_id": decision.token_id,
                "required_permission": decision.required_permission,
                "allowed": decision.allowed,
                "deny_reason": decision.deny_reason,
                "roles": list(decision.roles),
                "permissions": list(decision.permissions),
                "policy_source": decision.policy_source,
                "policy_version": decision.policy_version,
                "policy_fingerprint": decision.policy_fingerprint,
                "resolved_at": "2026-06-02T00:00:00.000000Z",
                "metadata": metadata,
            }
        ]

    harness.execute_postgres = fake_execute_postgres
    harness.query_postgres_json = fake_query_postgres_json
    try:
        persistence = harness.HostedPermissionDecisionPersistence("container")
        persistence.persist(
            decision,
            method="POST",
            path="/v1/admin/registry/validate",
            headers={"X-Request-ID": "req-duplicate"},
            gateway_key_id=harness.GATEWAY_KEY_ID,
        )
        persistence.persist(
            decision,
            method="POST",
            path="/v1/admin/registry/validate",
            headers={"X-Request-ID": "req-duplicate"},
            gateway_key_id=harness.GATEWAY_KEY_ID,
        )
    finally:
        harness.execute_postgres = original_execute_postgres
        harness.query_postgres_json = original_query_postgres_json

    assert len(captured_sql) == 1
    assert persistence.duplicate_equivalent_count == 1


def test_hosted_permission_decision_persistence_rejects_conflicting_duplicate() -> None:
    harness = load_harness_module()
    original_query_postgres_json = harness.query_postgres_json

    decision = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
        resolved_at="2026-06-02T00:00:00.000000Z",
    )

    def fake_query_postgres_json(container, sql):
        metadata = {
            "decision_status": decision.status,
            "permission_source": decision.permission_source,
            "persistence_version": harness.HOSTED_PERMISSION_DECISION_PERSISTENCE_VERSION,
            "production_boundary_version": harness.HOSTED_PERMISSION_DECISION_PRODUCTION_BOUNDARY_VERSION,
            "persistence_timeout_ms": 2000,
            "persistence_retry_budget": 2,
            "retention_policy_version": harness.HOSTED_PERMISSION_DECISION_RETENTION_POLICY_VERSION,
            "retention_class": "security",
            "retain_until": harness.rfc3339_add_days(decision.resolved_at, harness.HOSTED_PERMISSION_DECISION_RETENTION_DAYS),
            "history_visibility": harness.HOSTED_PERMISSION_DECISION_HISTORY_VISIBILITY,
            "redaction_policy_version": harness.HOSTED_PERMISSION_DECISION_REDACTION_POLICY_VERSION,
            "legal_hold": False,
            "method": "POST",
            "path": "/v1/admin/registry/validate",
            "gateway_key_id": harness.GATEWAY_KEY_ID,
        }
        return [
            {
                "subject_id": decision.subject_id,
                "actor_id": decision.actor_id,
                "project_id": decision.project_id,
                "organization_id": decision.organization_id,
                "token_id": decision.token_id,
                "required_permission": decision.required_permission,
                "allowed": decision.allowed,
                "deny_reason": "conflicting evidence",
                "roles": list(decision.roles),
                "permissions": list(decision.permissions),
                "policy_source": decision.policy_source,
                "policy_version": decision.policy_version,
                "policy_fingerprint": decision.policy_fingerprint,
                "resolved_at": "2026-06-02T00:00:00.000000Z",
                "metadata": metadata,
            }
        ]

    harness.query_postgres_json = fake_query_postgres_json
    try:
        persistence = harness.HostedPermissionDecisionPersistence("container")
        try:
            persistence.persist(
                decision,
                method="POST",
                path="/v1/admin/registry/validate",
                headers={},
                gateway_key_id=harness.GATEWAY_KEY_ID,
            )
        except RuntimeError as exc:
            assert str(exc) == harness.PERMISSION_DECISION_INTEGRITY_CONFLICT
        else:
            raise AssertionError("expected integrity conflict")
    finally:
        harness.query_postgres_json = original_query_postgres_json

    assert persistence.integrity_conflict_count == 1


def test_hosted_permission_decision_persistence_retries_transient_write() -> None:
    harness = load_harness_module()
    captured_sql = []
    original_execute_postgres = harness.execute_postgres
    original_query_postgres_json = harness.query_postgres_json

    def fake_execute_postgres(container, sql):
        captured_sql.append(sql)

    def fake_query_postgres_json(container, sql):
        return []

    decision = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}", "X-Request-ID": "req-transient"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    harness.execute_postgres = fake_execute_postgres
    harness.query_postgres_json = fake_query_postgres_json
    try:
        persistence = harness.HostedPermissionDecisionPersistence("container", retry_backoff_seconds=0)
        persistence.transient_failures_before_success = 1
        persistence.persist(
            decision,
            method="POST",
            path="/v1/admin/registry/validate",
            headers={"X-Request-ID": "req-transient"},
            gateway_key_id=harness.GATEWAY_KEY_ID,
        )
    finally:
        harness.execute_postgres = original_execute_postgres
        harness.query_postgres_json = original_query_postgres_json

    assert len(captured_sql) == 1
    assert persistence.write_attempt_count == 2
    assert persistence.retry_count == 1
    assert persistence.rows_written_count == 1


def test_hosted_permission_decision_persistence_timeout_fails_closed() -> None:
    harness = load_harness_module()
    captured_sql = []
    original_execute_postgres = harness.execute_postgres
    original_query_postgres_json = harness.query_postgres_json

    def fake_execute_postgres(container, sql):
        captured_sql.append(sql)

    def fake_query_postgres_json(container, sql):
        return []

    decision = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}", "X-Request-ID": "req-timeout"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    harness.execute_postgres = fake_execute_postgres
    harness.query_postgres_json = fake_query_postgres_json
    try:
        persistence = harness.HostedPermissionDecisionPersistence("container")
        persistence.force_write_timeout = True
        try:
            persistence.persist(
                decision,
                method="POST",
                path="/v1/admin/registry/validate",
                headers={"X-Request-ID": "req-timeout"},
                gateway_key_id=harness.GATEWAY_KEY_ID,
            )
        except RuntimeError as exc:
            assert "timed out" in str(exc)
        else:
            raise AssertionError("expected persistence timeout")
    finally:
        harness.execute_postgres = original_execute_postgres
        harness.query_postgres_json = original_query_postgres_json

    assert captured_sql == []
    assert persistence.timeout_count == 1
    assert persistence.rows_written_count == 0


def test_hosted_permission_decision_persistence_rejects_allowed_sentinel_evidence() -> None:
    harness = load_harness_module()
    decision = harness.GatewayPermissionDecision(
        allowed=True,
        status=200,
        error_type="",
        deny_reason="",
        subject_id="",
        actor_id="",
        project_id=harness.HARNESS_PROJECT_ID,
        organization_id="",
        token_id="token",
        roles=("role",),
        permissions=(harness.PERMISSION_REGISTRY_VALIDATE,),
        required_permission=harness.PERMISSION_REGISTRY_VALIDATE,
        policy_source=harness.HOSTED_PERMISSION_STORE_SOURCE,
        policy_version=harness.HOSTED_POLICY_VERSION,
        policy_fingerprint=harness.HOSTED_POLICY_FINGERPRINT,
        decision_id="decision-allowed-sentinel",
        permission_source=harness.HOSTED_PERMISSION_STORE_SOURCE,
        resolved_at="2026-06-02T00:00:00.000000Z",
    )
    persistence = harness.HostedPermissionDecisionPersistence("container")

    try:
        persistence.persist(
            decision,
            method="POST",
            path="/v1/admin/registry/validate",
            headers={},
            gateway_key_id=harness.GATEWAY_KEY_ID,
        )
    except RuntimeError as exc:
        assert "allowed hosted permission decisions must not use sentinel evidence" in str(exc)
    else:
        raise AssertionError("expected allowed sentinel evidence rejection")


def test_hosted_permission_decision_persistence_normalizes_unavailable_decision() -> None:
    harness = load_harness_module()
    captured_sql = []
    original_execute_postgres = harness.execute_postgres
    original_query_postgres_json = harness.query_postgres_json

    def fake_execute_postgres(container, sql):
        captured_sql.append(sql)

    def fake_query_postgres_json(container, sql):
        return []

    decision = harness.GatewayPermissionDecision(
        allowed=False,
        status=503,
        error_type="PERMISSION_SOURCE_UNAVAILABLE",
        deny_reason="hosted permission read model is unavailable",
        subject_id="",
        actor_id="",
        project_id="",
        organization_id="",
        token_id="",
        roles=(),
        permissions=(),
        required_permission=harness.PERMISSION_REGISTRY_VALIDATE,
        policy_source="",
        policy_version="",
        policy_fingerprint="",
        decision_id="",
        permission_source="",
        resolved_at="2026-06-02T00:00:00.000000Z",
    )
    harness.execute_postgres = fake_execute_postgres
    harness.query_postgres_json = fake_query_postgres_json
    try:
        persistence = harness.HostedPermissionDecisionPersistence("container")
        persistence.persist(
            decision,
            method="POST",
            path="/v1/admin/registry/validate",
            headers={"X-Request-ID": "req-unavailable"},
            gateway_key_id=harness.GATEWAY_KEY_ID,
        )
    finally:
        harness.execute_postgres = original_execute_postgres
        harness.query_postgres_json = original_query_postgres_json

    assert captured_sql
    sql = captured_sql[0]
    assert "'unknown-subject'" in sql
    assert "'unknown-actor'" in sql
    assert harness.HOSTED_PERMISSION_SENTINEL_POLICY_SOURCE in sql
    assert harness.HOSTED_PERMISSION_SENTINEL_POLICY_VERSION in sql
    assert harness.HOSTED_PERMISSION_SENTINEL_POLICY_FINGERPRINT in sql
    assert "decision-" in sql


def test_hosted_permission_decision_persistence_skips_auth_failures_only() -> None:
    harness = load_harness_module()

    missing = harness.resolve_gateway_admin_principal({}, harness.PERMISSION_REGISTRY_VALIDATE)
    invalid = harness.resolve_gateway_admin_principal(
        {"Authorization": "Bearer unknown-public-token"},
        harness.PERMISSION_REGISTRY_VALIDATE,
    )
    unavailable_after_auth = harness.resolve_gateway_admin_principal(
        {"Authorization": f"Bearer {harness.PUBLIC_ADMIN_TOKEN}"},
        harness.PERMISSION_REGISTRY_VALIDATE,
        permission_source_available=False,
    )

    assert not harness.should_persist_hosted_permission_decision(missing)
    assert not harness.should_persist_hosted_permission_decision(invalid)
    assert harness.should_persist_hosted_permission_decision(unavailable_after_auth)


def test_hosted_permission_decision_history_redacts_sensitive_fields() -> None:
    harness = load_harness_module()
    row = {
        "id": "decision-history-1",
        "subject_id": harness.HARNESS_PRINCIPAL_ID,
        "actor_id": harness.HARNESS_ACTOR_ID,
        "project_id": harness.HARNESS_PROJECT_ID,
        "organization_id": harness.HARNESS_ORGANIZATION_ID,
        "required_permission": harness.PERMISSION_REGISTRY_VALIDATE,
        "allowed": True,
        "deny_reason": "",
        "policy_version": harness.HOSTED_POLICY_VERSION,
        "policy_fingerprint": harness.HOSTED_POLICY_FINGERPRINT,
        "evidence_fingerprint": "sha256:history",
        "resolved_at": "2026-06-02T00:00:00.000000Z",
        "decision_status": "200",
        "error_type": "",
        "request_id": "req-history",
        "method": "POST",
        "path": "/v1/admin/registry/validate",
        "retention_policy_version": harness.HOSTED_PERMISSION_DECISION_RETENTION_POLICY_VERSION,
        "retention_class": "security",
        "retain_until": "2026-08-31T00:00:00.000000Z",
        "history_visibility": harness.HOSTED_PERMISSION_DECISION_HISTORY_VISIBILITY,
        "redaction_policy_version": harness.HOSTED_PERMISSION_DECISION_REDACTION_POLICY_VERSION,
        "legal_hold": False,
    }

    redacted = harness.redact_hosted_permission_decision_history_row(row)

    assert redacted["subject_ref"].startswith("sha256:")
    assert redacted["actor_ref"].startswith("sha256:")
    assert harness.HARNESS_PRINCIPAL_ID not in redacted.values()
    assert harness.HARNESS_ACTOR_ID not in redacted.values()
    assert "token_id" not in redacted
    assert redacted["result_family"] == "allowed"
    assert redacted["history_visibility"] == harness.HOSTED_PERMISSION_DECISION_HISTORY_VISIBILITY


def test_hosted_permission_decision_history_requires_project_scope_and_bounds() -> None:
    harness = load_harness_module()

    try:
        harness.hosted_permission_decision_history(
            "container",
            project_id="",
            start="2026-06-02T00:00:00.000000Z",
            end="2026-06-03T00:00:00.000000Z",
        )
    except ValueError as exc:
        assert "project_id is required" in str(exc)
    else:
        raise AssertionError("expected project scope requirement")

    try:
        harness.hosted_permission_decision_history(
            "container",
            project_id=harness.HARNESS_PROJECT_ID,
            start="2026-06-02T00:00:00.000000Z",
            end="2026-06-03T00:00:00.000000Z",
            limit=101,
        )
    except ValueError as exc:
        assert "between 1 and 100" in str(exc)
    else:
        raise AssertionError("expected bounded limit requirement")


def test_hosted_permission_decision_history_audit_is_secret_safe() -> None:
    harness = load_harness_module()
    captured_sql = []
    original_execute_postgres = harness.execute_postgres

    def fake_execute_postgres(container, sql):
        captured_sql.append(sql)

    harness.execute_postgres = fake_execute_postgres
    try:
        harness.audit_hosted_permission_decision_history_query(
            "container",
            operator_id="support-operator",
            project_id=harness.HARNESS_PROJECT_ID,
            organization_id=harness.HARNESS_ORGANIZATION_ID,
            request_id="req-history-audit",
            access_reason="support_case",
            ticket_id="case-123",
            start="2026-06-02T00:00:00.000000Z",
            end="2026-06-03T00:00:00.000000Z",
            result_count=7,
        )
    finally:
        harness.execute_postgres = original_execute_postgres

    assert captured_sql
    sql = captured_sql[0]
    assert "hosted_permission_decision_history.query" in sql
    assert harness.HOSTED_PERMISSION_DECISION_REDACTION_POLICY_VERSION in sql
    assert "1-10" in sql
    assert harness.PUBLIC_ADMIN_TOKEN not in sql
    assert harness.GATEWAY_SECRET not in sql


def test_endpoint_permission_map_covers_hosted_admin_gateway_routes() -> None:
    harness = load_harness_module()

    assert harness.endpoint_permission("POST", "/v1/admin/registry/validate") == harness.PERMISSION_REGISTRY_VALIDATE
    assert (
        harness.endpoint_permission("POST", "/v1/admin/registry/import-replace")
        == harness.PERMISSION_REGISTRY_IMPORT_REPLACE
    )
    assert (
        harness.endpoint_permission("POST", "/v1/admin/registry/project-partition/replace")
        == harness.PERMISSION_REGISTRY_PROJECT_PARTITION_REPLACE
    )
    assert (
        harness.endpoint_permission("POST", "/v1/admin/snapshots/export-artifact")
        == harness.PERMISSION_SNAPSHOT_EXPORT_ARTIFACT
    )
    assert (
        harness.endpoint_permission("GET", "/v1/admin/distribution/current")
        == harness.PERMISSION_DISTRIBUTION_READ_CURRENT
    )
    assert (
        harness.endpoint_permission("POST", "/v1/admin/distribution/publish")
        == harness.PERMISSION_DISTRIBUTION_PUBLISH
    )
