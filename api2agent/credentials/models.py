from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


OwnerType = Literal["user", "project", "platform", "provider"]
AuthType = Literal["api_key", "bearer", "basic", "oauth", "none"]
InjectionMode = Literal["header", "query", "body", "none"]
CredentialSource = Literal["env", "config", "inline", "none"]
CredentialStatus = Literal["active", "disabled"]


class CredentialDefinition(BaseModel):
    credential_id: str
    owner_type: OwnerType = "project"
    owner_id: str = "local"
    provider_id: str
    auth_type: AuthType = "api_key"
    injection_mode: InjectionMode = "header"
    injection_name: str | None = None
    scope: list[str] = Field(default_factory=list)
    source: CredentialSource = "env"
    secret_ref: str | None = None
    secret_value: str | None = Field(default=None, repr=False, exclude=True)
    status: CredentialStatus = "active"
    expires_at: datetime | None = None
    rotation_hint: str | None = None

    @model_validator(mode="after")
    def validate_secret_source(self):
        if self.auth_type == "none" or self.injection_mode == "none" or self.source == "none":
            return self
        if self.source == "env" and not self.secret_ref:
            raise ValueError("env credentials require secret_ref")
        if self.source in {"config", "inline"} and not (self.secret_value or self.secret_ref):
            raise ValueError("config/inline credentials require secret_value or secret_ref")
        return self


class CredentialResolutionRequest(BaseModel):
    project_id: str = "local"
    agent_id: str | None = None
    capability_id: str
    provider_id: str
    tool_id: str
    auth_type: AuthType = "none"
    injection_mode: InjectionMode = "none"
    injection_name: str | None = None
    credential: CredentialDefinition | None = None
    inline_credential: CredentialDefinition | None = None


class CredentialInjectionPatch(BaseModel):
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    body: dict[str, str] = Field(default_factory=dict)


class ResolvedCredential(BaseModel):
    resolved: bool
    credential_reference: str = "none"
    injection_patch: CredentialInjectionPatch = Field(default_factory=CredentialInjectionPatch)
    redacted_metadata: dict[str, str | list[str] | None] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
