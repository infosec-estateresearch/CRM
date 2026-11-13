"""HTTP request and response values shared by the client, the policy and transports."""

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass(frozen=True)
class Request:
    method: str
    url: str                      # absolute: origin + path [+ "?" + query]
    headers: tuple = ()           # ((name, value), ...)
    body: Optional[bytes] = None


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
