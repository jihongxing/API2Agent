from api2agent.ir.models import SafetyLevel


def classify_method(method: str) -> SafetyLevel:
    normalized = method.upper()
    if normalized in {"GET", "HEAD", "OPTIONS"}:
        return SafetyLevel.READ
    if normalized in {"POST", "PUT", "PATCH"}:
        return SafetyLevel.WRITE
    if normalized == "DELETE":
        return SafetyLevel.DELETE
    return SafetyLevel.UNKNOWN

