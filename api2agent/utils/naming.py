import re


def snake_name(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = value.lower()
    return value or "api"


def env_name(value: str) -> str:
    return snake_name(value).upper()

