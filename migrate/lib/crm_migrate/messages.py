"""HTTP request and response values shared by the client, the policy and transports."""

from dataclasses import dataclass, field
from typing import Optional, Protocol
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Request:
    method: str
    url: str                      # absolute: origin + path [+ "?" + query]
    headers: tuple = ()           # ((name, value), ...)
    body: Optional[bytes] = None

    def __repr__(self):
        """Method and path only: never the query, headers or body (session ids, passwords)."""
        try:
            path = urlsplit(self.url).path if isinstance(self.url, str) else "<invalid>"
        except ValueError:
            path = "<invalid>"
        return f"Request(method={self.method!r}, path={path!r}, headers=<redacted>, body=<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict = field(default_factory=dict)   # lower-case names
    body: bytes = b""


class Transport(Protocol):
    """Sends one already-checked request and returns the raw response.

    Implementations must not follow redirects, use proxies, or log bodies.
    """

    def send(self, request: Request) -> Response:  # pragma: no cover - protocol
        ...
