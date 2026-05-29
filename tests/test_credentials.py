from api2agent.credentials.config import load_credential_config
from api2agent.credentials.models import CredentialDefinition, CredentialResolutionRequest
from api2agent.credentials.resolver import CREDENTIAL_PRECEDENCE, LocalCredentialResolver


def test_resolver_reads_env_credential(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_TOKEN", "secret-token")
    resolver = LocalCredentialResolver()

    result = resolver.resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="bearer",
            injection_mode="header",
            credential=CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="bearer",
                injection_mode="header",
                injection_name="Authorization",
                source="env",
                secret_ref="TEST_API_TOKEN",
            ),
        )
    )

    assert result.resolved is True
    assert result.credential_reference == "env:TEST_API_TOKEN"
    assert result.injection_patch.headers == {"Authorization": "Bearer secret-token"}
    assert "secret-token" not in str(result.redacted_metadata)


def test_resolver_reads_config_credential() -> None:
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="config-secret",
            )
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="query",
        )
    )

    assert result.resolved is True
    assert result.credential_reference == "config:cred_demo"
    assert result.injection_patch.query == {"api_key": "config-secret"}


def test_resolver_reads_config_credential_without_auth_hint() -> None:
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="config-secret",
            )
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="none",
            injection_mode="none",
        )
    )

    assert result.resolved is True
    assert result.credential_reference == "config:cred_demo"
    assert result.injection_patch.query == {"api_key": "config-secret"}


def test_load_credential_config_reads_yaml_object(tmp_path) -> None:
    config = tmp_path / "credentials.yaml"
    config.write_text(
        """
credentials:
  - credential_id: cred_demo
    provider_id: demo
    auth_type: api_key
    injection_mode: header
    injection_name: X-API-Key
    source: config
    secret_value: config-secret
""",
        encoding="utf-8",
    )

    credentials = load_credential_config(config)

    assert len(credentials) == 1
    assert credentials[0].credential_id == "cred_demo"
    assert credentials[0].provider_id == "demo"


def test_inline_credential_override_wins(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_TOKEN", "env-secret")
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_config",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="config",
                secret_value="config-secret",
            )
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="header",
            inline_credential=CredentialDefinition(
                credential_id="cred_inline",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="inline",
                secret_value="inline-secret",
            ),
            credential=CredentialDefinition(
                credential_id="cred_env",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="env",
                secret_ref="TEST_API_TOKEN",
            ),
        )
    )

    assert result.credential_reference == "inline:cred_inline"
    assert result.injection_patch.headers == {"X-Token": "inline-secret"}


def test_config_credential_precedes_request_credential(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_TOKEN", "env-secret")
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_config",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="config",
                secret_value="config-secret",
            )
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="header",
            credential=CredentialDefinition(
                credential_id="cred_request",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="env",
                secret_ref="TEST_API_TOKEN",
            ),
        )
    )

    assert CREDENTIAL_PRECEDENCE == ("inline", "config", "request")
    assert result.credential_reference == "config:cred_config"
    assert result.injection_patch.headers == {"X-Token": "config-secret"}


def test_config_credential_owner_match_wins_for_project() -> None:
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_local",
                owner_id="local",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="local-secret",
            ),
            CredentialDefinition(
                credential_id="cred_project_a",
                owner_id="project_a",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="project-secret",
            ),
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            project_id="project_a",
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="none",
            injection_mode="none",
        )
    )

    assert result.credential_reference == "config:cred_project_a"
    assert result.injection_patch.query == {"api_key": "project-secret"}
    assert result.redacted_metadata["owner_id"] == "project_a"


def test_config_credential_falls_back_to_local_owner() -> None:
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_other",
                owner_id="other_project",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="other-secret",
            ),
            CredentialDefinition(
                credential_id="cred_local",
                owner_id="local",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="query",
                injection_name="api_key",
                source="config",
                secret_value="local-secret",
            ),
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            project_id="project_a",
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="none",
            injection_mode="none",
        )
    )

    assert result.credential_reference == "config:cred_local"
    assert result.injection_patch.query == {"api_key": "local-secret"}


def test_credential_scope_allows_matching_capability() -> None:
    result = LocalCredentialResolver().resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="header",
            credential=CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="inline",
                secret_value="inline-secret",
                scope=["capability:demo.get"],
            ),
        )
    )

    assert result.resolved is True
    assert result.credential_reference == "inline:cred_demo"
    assert result.injection_patch.headers == {"X-Token": "inline-secret"}


def test_credential_scope_allows_matching_tool() -> None:
    result = LocalCredentialResolver().resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="header",
            credential=CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="inline",
                secret_value="inline-secret",
                scope=["tool:get"],
            ),
        )
    )

    assert result.resolved is True
    assert result.injection_patch.headers == {"X-Token": "inline-secret"}


def test_credential_scope_denies_out_of_scope_credential() -> None:
    result = LocalCredentialResolver().resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="header",
            credential=CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                source="inline",
                secret_value="inline-secret",
                scope=["capability:demo.create"],
            ),
        )
    )

    assert result.resolved is False
    assert result.credential_reference == "inline:cred_demo"
    assert result.error_type == "credential_scope_denied"
    assert result.redacted_metadata["scope"] == ["capability:demo.create"]
    assert "inline-secret" not in str(result.model_dump(mode="json"))


def test_out_of_scope_inline_credential_does_not_fall_back_to_config() -> None:
    resolver = LocalCredentialResolver(
        [
            CredentialDefinition(
                credential_id="cred_config",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                injection_name="X-Token",
                source="config",
                secret_value="config-secret",
            )
        ]
    )

    result = resolver.resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="api_key",
            injection_mode="header",
            inline_credential=CredentialDefinition(
                credential_id="cred_inline",
                provider_id="demo",
                auth_type="api_key",
                injection_mode="header",
                source="inline",
                secret_value="inline-secret",
                scope=["capability:demo.create"],
            ),
        )
    )

    assert result.resolved is False
    assert result.credential_reference == "inline:cred_inline"
    assert result.error_type == "credential_scope_denied"


def test_auth_type_none_skips_credentials() -> None:
    result = LocalCredentialResolver().resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="none",
            injection_mode="none",
        )
    )

    assert result.resolved is True
    assert result.credential_reference == "none"
    assert result.injection_patch.headers == {}


def test_missing_env_secret_returns_redacted_error(monkeypatch) -> None:
    monkeypatch.delenv("TEST_API_TOKEN", raising=False)

    result = LocalCredentialResolver().resolve(
        CredentialResolutionRequest(
            capability_id="demo.get",
            provider_id="demo",
            tool_id="get",
            auth_type="bearer",
            injection_mode="header",
            credential=CredentialDefinition(
                credential_id="cred_demo",
                provider_id="demo",
                auth_type="bearer",
                injection_mode="header",
                source="env",
                secret_ref="TEST_API_TOKEN",
            ),
        )
    )

    assert result.resolved is False
    assert result.credential_reference == "env:TEST_API_TOKEN"
    assert result.error_type == "missing_credential_secret"
    assert "secret-token" not in str(result.model_dump(mode="json"))
