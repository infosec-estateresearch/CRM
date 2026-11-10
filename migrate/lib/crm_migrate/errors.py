"""Exceptions whose text is safe to print.

An exception message never contains a record value, a response body, a token or a
secret. It is built only from a fixed code, an HTTP status, a Salesforce ``errorCode``
from the fixed ``SF_ERROR_CODES`` set (anything else is ``UNKNOWN``) and an optional detail that must match a conservative character set
(contract object and field names, counts).
"""

import re

_DETAIL_RE = re.compile(r"\A[A-Za-z0-9_.,:=/ ()<>\[\]-]{0,400}\Z")
_SF_ERROR_RE = re.compile(r"\A[A-Z][A-Z0-9_]{0,63}\Z")

# Salesforce REST ``errorCode`` / OAuth ``error`` (upper-cased) / SOAP ``exceptionCode`` values
# that may be printed. Server-supplied text is never echoed: anything else is ``UNKNOWN``.
SF_ERROR_CODES = frozenset((
    # REST API
    "UNKNOWN_EXCEPTION", "INVALID_SESSION_ID", "NOT_FOUND", "MALFORMED_QUERY", "INVALID_FIELD",
    "INVALID_TYPE", "INVALID_QUERY_LOCATOR", "INVALID_QUERY_FILTER_OPERATOR", "QUERY_TIMEOUT",
    "INVALID_REPLICATION_DATE", "INVALID_REPLICATION_OBJECT", "REQUEST_LIMIT_EXCEEDED",
    "API_DISABLED_FOR_ORG", "API_CURRENTLY_DISABLED", "INSUFFICIENT_ACCESS", "INSUFFICIENT_ACCESS_OR_READONLY",
    "FUNCTIONALITY_NOT_ENABLED", "METHOD_NOT_ALLOWED", "NOT_ACCEPTABLE", "UNSUPPORTED_MEDIA_TYPE",
    "JSON_PARSER_ERROR", "SERVER_UNAVAILABLE", "INVALID_OPERATION", "INVALID_CROSS_REFERENCE_KEY",
    "OPERATION_TOO_LARGE", "EXCEEDED_ID_LIMIT",
    # OAuth (``error``, upper-cased by the client)
    "INVALID_CLIENT", "INVALID_CLIENT_ID", "INVALID_GRANT", "INVALID_REQUEST", "UNSUPPORTED_GRANT_TYPE",
    "INVALID_SCOPE", "UNAUTHORIZED_CLIENT",
    # SOAP login fault exceptionCode
    "INVALID_LOGIN", "LOGIN_MUST_USE_SECURITY_TOKEN", "PASSWORD_LOCKOUT",
    "INVALID_OPERATION_WITH_EXPIRED_PASSWORD", "LOGIN_RATE_EXCEEDED",
    "UNKNOWN",
))


def safe_sf_error_code(value):
    """Return a Salesforce errorCode if it is in the fixed ``SF_ERROR_CODES`` set, else ``UNKNOWN``."""
    if isinstance(value, str) and _SF_ERROR_RE.fullmatch(value) and value in SF_ERROR_CODES:
        return value
    return "UNKNOWN"


class MigrateError(Exception):
    """Base error. ``code`` is a fixed identifier from this package."""

    code = "error"
    exit_code = 1

    def __init__(self, code=None, *, detail=None, status=None, sf_error=None):
        self.code = code or type(self).code
        self.status = status if isinstance(status, int) else None
        self.sf_error = safe_sf_error_code(sf_error) if sf_error is not None else None
        if detail is not None and not (isinstance(detail, str) and _DETAIL_RE.fullmatch(detail)):
            detail = "<redacted>"
        self.detail = detail
        super().__init__(self.safe_message())

    def safe_message(self):
        parts = [f"code={self.code}"]
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.sf_error is not None:
            parts.append(f"sf_error={self.sf_error}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        return " ".join(parts)


class ConfigError(MigrateError):
    code = "config_error"
    exit_code = 2


class ContractError(MigrateError):
    code = "contract_error"
    exit_code = 2


class RefusedRequest(MigrateError):
    """A request outside the read-only allowlist. Raised before any transport call."""

    code = "request_refused"
    exit_code = 4


class OriginError(MigrateError):
    code = "origin_refused"
    exit_code = 4


class RedirectRefused(MigrateError):
    code = "redirect_refused"
    exit_code = 4


class ResponseTooLarge(MigrateError):
    code = "response_too_large"
    exit_code = 4


class HttpError(MigrateError):
    code = "http_error"
    exit_code = 4


class ProtocolError(MigrateError):
    code = "protocol_error"
    exit_code = 4


class GateFailed(MigrateError):
    code = "metadata_gate_failed"
    exit_code = 3


class OutputError(MigrateError):
    code = "output_error"
    exit_code = 2


class SnapshotError(MigrateError):
    code = "snapshot_error"
    exit_code = 5
