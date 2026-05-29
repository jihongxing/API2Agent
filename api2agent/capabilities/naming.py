import re


CAPABILITY_ID_RULE = "<domain>.<resource>.<action>"
_CAPABILITY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def is_alpha_capability_id(value: str) -> bool:
    return bool(_CAPABILITY_ID_PATTERN.fullmatch(value.strip()))


def capability_id_rule_message(value: str) -> str:
    return f"capability_id '{value}' does not match v0.1-alpha naming rule {CAPABILITY_ID_RULE}"
