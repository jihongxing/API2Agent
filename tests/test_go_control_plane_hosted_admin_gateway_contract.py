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
    assert admin.policy_source == harness.STATIC_POLICY_SOURCE
    assert admin.policy_version == harness.STATIC_POLICY_VERSION

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
