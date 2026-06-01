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
