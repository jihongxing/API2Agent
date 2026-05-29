from pathlib import Path
import json
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator

from api2agent.capabilities.models import ProviderCandidate


PROVIDER_REGISTRY_CONTRACT_VERSION = "provider_registry.v0.1"


class ProviderRegistry(BaseModel):
    contract_version: str = PROVIDER_REGISTRY_CONTRACT_VERSION
    providers: list[ProviderCandidate]

    @field_validator("contract_version")
    @classmethod
    def validate_contract_version(cls, value: str) -> str:
        if value != PROVIDER_REGISTRY_CONTRACT_VERSION:
            raise ValueError(f"Unsupported provider registry contract_version: {value}")
        return value


class RegistryWarning(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    provider_id: str
    message: str


def load_provider_registry(path: Path) -> ProviderRegistry:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Registry file cannot be read: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Registry must be valid JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Registry must be a JSON object.")

    try:
        return ProviderRegistry.model_validate(payload)
    except ValidationError as exc:
        for error in exc.errors():
            if tuple(error.get("loc", ())) == ("contract_version",):
                message = error.get("msg", "")
                if "Unsupported provider registry contract_version" in message:
                    raise ValueError(message.replace("Value error, ", "")) from exc
        raise ValueError(f"Registry schema is invalid: {exc.errors()}") from exc


def provider_package_warnings(providers: list[ProviderCandidate]) -> list[RegistryWarning]:
    warnings: list[RegistryWarning] = []
    for provider in providers:
        package_dir = provider.metadata.get("package_dir")
        if not package_dir:
            warnings.append(
                RegistryWarning(
                    severity="error",
                    code="missing_package_dir",
                    provider_id=provider.provider_id,
                    message="missing metadata.package_dir",
                )
            )
            continue

        runner_path = Path(str(package_dir)) / "runner.py"
        if not runner_path.exists():
            warnings.append(
                RegistryWarning(
                    severity="error",
                    code="missing_runner",
                    provider_id=provider.provider_id,
                    message=f"runner not found at {runner_path}",
                )
            )
    return warnings
