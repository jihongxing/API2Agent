from enum import StrEnum


class StandardErrorType(StrEnum):
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    AUTH_ERROR = "AUTH_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NORMALIZATION_ERROR = "NORMALIZATION_ERROR"
    UNKNOWN = "UNKNOWN"


def error_type_for_status(status_code: int | None) -> StandardErrorType:
    if status_code is None:
        return StandardErrorType.UNKNOWN
    if status_code in {401, 403}:
        return StandardErrorType.AUTH_ERROR
    if status_code == 404:
        return StandardErrorType.NOT_FOUND
    if status_code == 408:
        return StandardErrorType.TIMEOUT
    if status_code == 429:
        return StandardErrorType.RATE_LIMIT
    if 400 <= status_code < 500:
        return StandardErrorType.INVALID_REQUEST
    if status_code >= 500:
        return StandardErrorType.PROVIDER_ERROR
    return StandardErrorType.UNKNOWN
