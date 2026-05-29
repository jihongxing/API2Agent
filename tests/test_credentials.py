from api2agent.credentials.models import CredentialDefinition, CredentialResolutionRequest
from api2agent.credentials.resolver import LocalCredentialResolver


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
