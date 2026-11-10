"""OAuth 2.0 client credentials, and nothing else.

There is no username/password flow, no refresh token, no JWT bearer, and no SOAP
``login()``. The token response's ``instance_url`` must equal the configured origin
exactly, otherwise the run aborts. The access token is held in memory only.
"""

from urllib.parse import urlencode

from .errors import ConfigError, OriginError, ProtocolError, RefusedRequest
from .messages import Request

GRANT_TYPE = "client_credentials"
TOKEN_PATH = "/services/oauth2/token"


def build_token_request(origin, client_id, client_secret, grant_type=GRANT_TYPE):
    if grant_type != GRANT_TYPE:
        raise RefusedRequest("grant_type_refused", detail="only client_credentials is permitted")
    for value in (client_id, client_secret):
        if not isinstance(value, str) or not value or any(c in value for c in "\r\n\x00"):
            raise ConfigError("credentials_invalid", detail="client id and secret must be non-empty single-line values")
    body = urlencode([("grant_type", GRANT_TYPE), ("client_id", client_id), ("client_secret", client_secret)])
    return Request(
        method="POST",
        url=origin + TOKEN_PATH,
        headers=(("Accept", "application/json"), ("Content-Type", "application/x-www-form-urlencoded")),
        body=body.encode("ascii"),
    )


def parse_token_response(doc, origin):
    if not isinstance(doc, dict):
        raise ProtocolError("token_response", detail="not an object")
    token = doc.get("access_token")
    if not isinstance(token, str) or not token or any(c in token for c in "\r\n "):
        raise ProtocolError("token_response", detail="no access token")
    if doc.get("instance_url") != origin:
        raise OriginError("instance_url_mismatch", detail="token instance_url differs from the configured origin")
    token_type = doc.get("token_type", "Bearer")
    if token_type != "Bearer":
        raise ProtocolError("token_response", detail="token_type must be Bearer")
    return token
