"""Domain errors mapped to consistent HTTP error responses."""

from __future__ import annotations


class BusinessRuleError(Exception):
    """A documented business rule was violated (HTTP 409 by default)."""

    status_code = 409
    code = "BUSINESS_RULE_VIOLATION"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None,
                 status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.details = details or {}
        if status_code:
            self.status_code = status_code


class NotFoundError(BusinessRuleError):
    status_code = 404
    code = "NOT_FOUND"


class ValidationError(BusinessRuleError):
    status_code = 422
    code = "VALIDATION_ERROR"


class PermissionDeniedError(BusinessRuleError):
    status_code = 403
    code = "PERMISSION_DENIED"


class ConflictError(BusinessRuleError):
    status_code = 409
    code = "CONFLICT"
