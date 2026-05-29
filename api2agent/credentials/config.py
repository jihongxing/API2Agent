import json
from pathlib import Path
from typing import Any

import yaml

from api2agent.credentials.models import CredentialDefinition


def load_credential_config(path: Path) -> list[CredentialDefinition]:
    if not path.exists():
        raise ValueError(f"Credential config not found: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid credential config: {path}") from exc

    items = _credential_items(payload)
    credentials: list[CredentialDefinition] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Credential config item #{index + 1} must be an object.")
        try:
            credentials.append(CredentialDefinition.model_validate(item))
        except ValueError as exc:
            raise ValueError(f"Invalid credential config item #{index + 1}: {exc}") from exc
    return credentials


def _credential_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("credentials")
        if isinstance(items, list):
            return items
    raise ValueError("Credential config must be a list or an object with a credentials list.")
