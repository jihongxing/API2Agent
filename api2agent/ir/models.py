from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SafetyLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    UNKNOWN = "unknown"


class AuthConfig(BaseModel):
    type: Literal["none", "api_key", "bearer", "unknown"] = "none"
    env: str | None = None
    header: str | None = None
    description: str | None = None
    location: Literal["header", "query", "cookie", "authorization", "unknown"] | None = None
    name: str | None = None
    scheme_name: str | None = None
    scopes: list[str] = Field(default_factory=list)
    source: Literal["openapi", "curl", "manual"] | None = None
    unsupported_reason: str | None = None
    credentials: list[dict[str, Any]] = Field(default_factory=list)


class SecurityAlternative(BaseModel):
    schemes: list[AuthConfig] = Field(default_factory=list)
    anonymous: bool = False


class SecurityRequirements(BaseModel):
    alternatives: list[SecurityAlternative] = Field(default_factory=list)


class Parameter(BaseModel):
    name: str
    location: Literal["path", "query", "header"]
    required: bool = False
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")
    description: str | None = None
    example: Any | None = None
    examples: list[Any] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class RequestBody(BaseModel):
    required: bool = False
    content_type: str = "application/json"
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")
    example: Any | None = None
    examples: list[Any] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ResponseShape(BaseModel):
    status_code: str
    description: str | None = None
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")

    model_config = {"populate_by_name": True}


class Tool(BaseModel):
    name: str
    operation_id: str | None = None
    method: str
    path: str
    base_url: str | None = None
    description: str
    tags: list[str] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    request_body: RequestBody | None = None
    responses: list[ResponseShape] = Field(default_factory=list)
    safety: SafetyLevel = SafetyLevel.UNKNOWN
    auth: AuthConfig | None = None
    security_requirements: SecurityRequirements | None = None


class Capability(BaseModel):
    name: str
    version: str = "0.1.0"
    base_url: str = ""
    auth: AuthConfig = Field(default_factory=AuthConfig)
    security_requirements: SecurityRequirements | None = None
    tools: list[Tool] = Field(default_factory=list)
    provider_region: str | None = None
    provider_regions: list[str] = Field(default_factory=list)
    source: str | None = None
