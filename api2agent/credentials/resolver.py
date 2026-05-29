import os
from typing import Iterable

from api2agent.credentials.models import (
    CredentialDefinition,
    CredentialInjectionPatch,
    CredentialResolutionRequest,
    ResolvedCredential,
)


class CredentialResolutionError(ValueError):
    pass


CREDENTIAL_PRECEDENCE = ("inline", "config", "request")


class LocalCredentialResolver:
    def __init__(self, config_credentials: Iterable[CredentialDefinition] | None = None) -> None:
        self.config_credentials = list(config_credentials or [])

    def resolve(self, request: CredentialResolutionRequest) -> ResolvedCredential:
        candidates = [
            request.inline_credential,
            self._find_config_credential(request),
            request.credential,
        ]
        if (request.auth_type == "none" or request.injection_mode == "none") and not any(candidates):
            return ResolvedCredential(
                resolved=True,
                credential_reference="none",
                redacted_metadata={"source": "none", "provider_id": request.provider_id},
            )

        for credential in candidates:
            if credential is None:
                continue
            if credential.provider_id != request.provider_id:
                continue
            if not self._scope_allows(credential, request):
                return self._scope_denied(credential, request)
            secret = self._secret_for(credential)
            if secret is None:
                return self._missing_secret(credential)
            return ResolvedCredential(
                resolved=True,
                credential_reference=self._credential_reference(credential),
                injection_patch=self._injection_patch(credential, secret),
                redacted_metadata=self._redacted_metadata(credential),
            )

        return ResolvedCredential(
            resolved=False,
            credential_reference="missing",
            error_type="missing_credential",
            error_message=f"No credential configured for provider: {request.provider_id}",
        )

    def _find_config_credential(self, request: CredentialResolutionRequest) -> CredentialDefinition | None:
        matches = [
            credential
            for credential in self.config_credentials
            if credential.provider_id == request.provider_id
        ]
        if not matches:
            return None

        for credential in matches:
            if credential.owner_id == request.project_id:
                return credential

        for credential in matches:
            if credential.owner_type == "project" and credential.owner_id == "local":
                return credential

        return matches[0]

    def _secret_for(self, credential: CredentialDefinition) -> str | None:
        if credential.source == "none" or credential.auth_type == "none":
            return ""
        if credential.source == "env":
            return os.getenv(str(credential.secret_ref))
        if credential.secret_value is not None:
            return credential.secret_value
        if credential.secret_ref:
            return os.getenv(credential.secret_ref)
        return None

    def _credential_reference(self, credential: CredentialDefinition) -> str:
        if credential.source == "env":
            return f"env:{credential.secret_ref}"
        if credential.source == "config":
            return f"config:{credential.credential_id}"
        if credential.source == "inline":
            return f"inline:{credential.credential_id}"
        return "none"

    def _injection_patch(self, credential: CredentialDefinition, secret: str) -> CredentialInjectionPatch:
        value = self._formatted_secret(credential, secret)
        name = credential.injection_name or self._default_injection_name(credential)
        if credential.injection_mode == "header":
            return CredentialInjectionPatch(headers={name: value})
        if credential.injection_mode == "query":
            return CredentialInjectionPatch(query={name: value})
        if credential.injection_mode == "body":
            return CredentialInjectionPatch(body={name: value})
        return CredentialInjectionPatch()

    def _formatted_secret(self, credential: CredentialDefinition, secret: str) -> str:
        if credential.auth_type == "bearer":
            if secret.lower().startswith("bearer "):
                return secret
            return f"Bearer {secret}"
        if credential.auth_type == "basic":
            if secret.lower().startswith("basic "):
                return secret
            return f"Basic {secret}"
        return secret

    def _default_injection_name(self, credential: CredentialDefinition) -> str:
        if credential.auth_type in {"bearer", "basic"}:
            return "Authorization"
        return "X-API-Key"

    def _redacted_metadata(self, credential: CredentialDefinition) -> dict[str, str | list[str] | None]:
        return {
            "credential_id": credential.credential_id,
            "owner_type": credential.owner_type,
            "owner_id": credential.owner_id,
            "provider_id": credential.provider_id,
            "auth_type": credential.auth_type,
            "injection_mode": credential.injection_mode,
            "injection_name": credential.injection_name,
            "source": credential.source,
            "secret_ref": credential.secret_ref,
            "scope": credential.scope,
        }

    def _scope_allows(self, credential: CredentialDefinition, request: CredentialResolutionRequest) -> bool:
        if not credential.scope:
            return True

        allowed = set(credential.scope)
        return bool(
            "*:*" in allowed
            or "*" in allowed
            or f"provider:{request.provider_id}" in allowed
            or f"capability:{request.capability_id}" in allowed
            or f"tool:{request.tool_id}" in allowed
            or request.capability_id in allowed
            or request.tool_id in allowed
        )

    def _scope_denied(
        self,
        credential: CredentialDefinition,
        request: CredentialResolutionRequest,
    ) -> ResolvedCredential:
        return ResolvedCredential(
            resolved=False,
            credential_reference=self._credential_reference(credential),
            redacted_metadata=self._redacted_metadata(credential),
            error_type="credential_scope_denied",
            error_message=(
                "Credential scope does not allow "
                f"capability={request.capability_id}, tool={request.tool_id}."
            ),
        )

    def _missing_secret(self, credential: CredentialDefinition) -> ResolvedCredential:
        return ResolvedCredential(
            resolved=False,
            credential_reference=self._credential_reference(credential),
            redacted_metadata=self._redacted_metadata(credential),
            error_type="missing_credential_secret",
            error_message=f"Credential secret is unavailable: {self._credential_reference(credential)}",
        )
