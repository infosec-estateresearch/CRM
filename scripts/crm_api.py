"""Minimal EspoCRM REST API client (Python standard library only).

HTTP goes through an injectable transport so callers can be unit-tested with
no network. Credentials are read from the environment by callers and are never
written anywhere by this module.
"""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ENV_BASE_URL = "CRM_BASE_URL"
ENV_USERNAME = "CRM_ADMIN_USERNAME"
ENV_PASSWORD = "CRM_ADMIN_PASSWORD"

PAGE_SIZE = 200  # EspoCRM's default recordListMaxSizeLimit


class ConfigError(RuntimeError):
    """Required configuration is missing or invalid."""


class ApiError(RuntimeError):
    def __init__(self, method, path, status, body):
        self.method = method
        self.path = path
        self.status = status
        self.body = body
        super().__init__(f"{method} {path} -> HTTP {status}")


class UrllibTransport:
    """Real transport. Returns (status, body_bytes) for any HTTP status."""

    def __init__(self, timeout=30):
        self.timeout = timeout

    def request(self, method, url, headers, body):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()


def credentials_from_env(environ=None):
    environ = os.environ if environ is None else environ
    username = environ.get(ENV_USERNAME, "")
    password = environ.get(ENV_PASSWORD, "")
    if not username or not password:
        raise ConfigError(
            f"{ENV_USERNAME} and {ENV_PASSWORD} must be set in the environment"
        )
    return username, password


def validate_base_url(base_url):
    if not base_url:
        raise ConfigError(f"a base URL is required (--base-url or {ENV_BASE_URL})")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigError(f"base URL must be http(s)://host[:port], got {base_url!r}")
    return base_url.rstrip("/")


class EspoClient:
    def __init__(self, base_url, username, password, transport=None):
        self.base_url = validate_base_url(base_url)
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        self._headers = {
            "Espo-Authorization": token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.transport = transport or UrllibTransport()

    def call(self, method, path, params=None, data=None, extra_headers=None):
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = dict(self._headers)
        if extra_headers:
            headers.update(extra_headers)
        body = None if data is None else json.dumps(data).encode("utf-8")
        status, raw = self.transport.request(method, url, headers, body)
        if not 200 <= status < 300:
            raise ApiError(method, path, status, raw[:500] if raw else b"")
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def create(self, entity_type, data, extra_headers=None):
        return self.call("POST", entity_type, data=data, extra_headers=extra_headers)

    def delete(self, entity_type, record_id):
        return self.call("DELETE", f"{entity_type}/{record_id}")

    def list_page(self, path, params=None, offset=0, max_size=PAGE_SIZE):
        query = dict(params or {})
        query.update({"offset": offset, "maxSize": max_size})
        return self.call("GET", path, params=query)

    def list_all(self, path, params=None):
        """Every record of a list endpoint, paged by id; fails if incomplete."""
        query = {"orderBy": "id", "order": "asc"}
        query.update(params or {})
        seen = {}
        offset = 0
        total = None
        while True:
            page = self.list_page(path, query, offset=offset)
            total = page.get("total", total)
            rows = page.get("list", [])
            for row in rows:
                seen[row["id"]] = row
            offset += len(rows)
            if not rows or (isinstance(total, int) and total >= 0 and offset >= total):
                break
        records = list(seen.values())
        if isinstance(total, int) and total >= 0 and len(records) != total:
            raise ApiError("GET", path, 0, f"paged {len(records)} of {total}".encode())
        return records


def where_params(conditions):
    """Encode [(type, attribute, value), ...] as EspoCRM where[] query params."""
    params = {}
    for i, (kind, attribute, value) in enumerate(conditions):
        params[f"where[{i}][type]"] = kind
        params[f"where[{i}][attribute]"] = attribute
        if value is not None:
            params[f"where[{i}][value]"] = value
    return params
