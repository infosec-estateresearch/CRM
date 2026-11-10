"""Beta-safe acceptance suite for crm-beta (CRM-007). Read-only: GET requests only.

Run against a live crm-beta, as root, from the unpacked release:

    export CRM_BASE_URL=http://127.0.0.1:<CRM_BETA_APP_PORT>
    export CRM_BETA_SAFE_KEY_FILE=/root/crm-beta-import-key.env
    python3 -m unittest discover -s tests/acceptance -p test_beta_safe.py -v

The module is skipped unless both are set. The API key is read from the file
named by CRM_BETA_SAFE_KEY_FILE, never from the command line or the
environment: a regular file (not a symlink) with no group or other permission
bits, holding NAME=value lines with exactly one of CRM_IMPORT_API_KEY (the file
scripts/provision_access.py writes) or CRM_LOAD_API_KEY (load.env). The key is
sent as X-Api-Key and is never printed.

It checks that:
- the API answers (GET App/user);
- every role in config/access/roles.json exists (GET Role, by name);
- phoneNumberInternational is the JSON boolean false (GET Settings);
- siteUrl uses https (GET Settings);
- no Account name contains the synthetic seed marker (a count only; no name
  is fetched or printed).

Every request goes through ReadOnlyClient, which can only send GET.
tests/unit/test_beta.py runs this module in-process against a fake EspoCRM and
fails if any other method is sent.
"""

import json
import os
import stat
import sys
import unittest
import urllib.parse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import crm_api  # noqa: E402

ENV_KEY_FILE = "CRM_BETA_SAFE_KEY_FILE"
KEY_NAMES = ("CRM_IMPORT_API_KEY", "CRM_LOAD_API_KEY")
ROLES_PATH = os.path.join(REPO, "config", "access", "roles.json")
SEED_MARKER = "SENTINEL-7f3a"

# Unit tests replace this with an in-memory fake; None = the real HTTP transport.
TRANSPORT = None
CLIENT = None


class BetaSafeError(RuntimeError):
    """Configuration or a read that the suite cannot use."""


def read_key(path):
    """The API key from a private NAME=value file. Never echoes the value."""
    try:
        st = os.lstat(path)
    except OSError as err:
        raise BetaSafeError(f"key file not readable: {type(err).__name__}") from None
    if not stat.S_ISREG(st.st_mode):
        raise BetaSafeError("key file must be a regular file (not a symlink)")
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise BetaSafeError("key file must not be accessible to group or others (use 0600)")
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    found = []
    for line in lines:
        name, sep, value = line.partition("=")
        if sep and name.strip() in KEY_NAMES and value.strip():
            found.append(value.strip())
    if len(found) != 1:
        raise BetaSafeError(f"key file must hold exactly one non-empty {' or '.join(KEY_NAMES)}")
    return found[0]


class ReadOnlyClient:
    """EspoCRM REST reads with an API key. It has no way to send anything but GET."""

    METHOD = "GET"

    def __init__(self, base_url, api_key, transport=None):
        self.base_url = crm_api.validate_base_url(base_url)
        self._headers = {"X-Api-Key": api_key, "Accept": "application/json"}
        self.transport = transport or crm_api.UrllibTransport()

    def get(self, path, params=None):
        if self.METHOD != "GET":
            raise BetaSafeError("the beta-safe client sends GET only")
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        status, raw = self.transport.request("GET", url, dict(self._headers), None)
        if not 200 <= status < 300:
            raise crm_api.ApiError("GET", path, status, b"")  # the body is never kept
        return json.loads(raw.decode("utf-8")) if raw else None

    def count(self, entity, conditions):
        """Total matching records; fetches at most one id, never names."""
        params = crm_api.where_params(conditions)
        params.update({"select": "id", "maxSize": 1, "offset": 0})
        page = self.get(entity, params)
        total = page.get("total") if isinstance(page, dict) else None
        if not isinstance(total, int) or total < 0:
            raise BetaSafeError(f"{entity} list returned no usable total")
        return total


def client_from_env(environ=None, transport=None):
    environ = os.environ if environ is None else environ
    base_url = environ.get(crm_api.ENV_BASE_URL, "")
    key_file = environ.get(ENV_KEY_FILE, "")
    if not base_url or not key_file:
        raise BetaSafeError(f"{crm_api.ENV_BASE_URL} and {ENV_KEY_FILE} must be set")
    return ReadOnlyClient(base_url, read_key(key_file), transport)


def role_names(path=ROLES_PATH):
    with open(path, encoding="utf-8") as fh:
        return [r["name"] for r in json.load(fh)["roles"]]


def setUpModule():
    global CLIENT
    if not (os.environ.get(crm_api.ENV_BASE_URL) and os.environ.get(ENV_KEY_FILE)):
        raise unittest.SkipTest(f"beta-safe suite: set {crm_api.ENV_BASE_URL} and {ENV_KEY_FILE}")
    CLIENT = client_from_env(transport=TRANSPORT)


class TestBetaSafe(unittest.TestCase):
    """Read-only checks of a live crm-beta."""

    settings = None

    @classmethod
    def setUpClass(cls):
        cls.settings = CLIENT.get("Settings")

    def test_api_answers(self):
        me = CLIENT.get("App/user")
        self.assertIsInstance(me, dict)
        self.assertIsInstance(me.get("user"), dict, "App/user returned no user")

    def test_roles_from_config_exist(self):
        missing = []
        for name in role_names():
            try:
                n = CLIENT.count("Role", [("equals", "name", name)])
            except crm_api.ApiError as err:
                self.fail(f"cannot read roles (HTTP {err.status}); the key's user needs read "
                          "access to Role")
            if n < 1:
                missing.append(name)
        self.assertEqual(missing, [], "roles from config/access/roles.json missing in crm-beta")

    def test_phone_number_international_is_false(self):
        self.assertIn("phoneNumberInternational", self.settings)
        # Exactly the JSON boolean false: the string "false", 0 or null fail.
        self.assertIs(self.settings["phoneNumberInternational"], False)

    def test_site_url_uses_https(self):
        url = self.settings.get("siteUrl")
        self.assertIsInstance(url, str, "siteUrl is not set")
        parts = urllib.parse.urlsplit(url)
        self.assertEqual(parts.scheme, "https", "siteUrl does not use https")
        self.assertTrue(parts.hostname, "siteUrl has no host")

    def test_no_synthetic_seed_marker(self):
        n = CLIENT.count("Account", [("contains", "name", SEED_MARKER)])
        self.assertEqual(n, 0, f"{n} Account record(s) carry the synthetic seed marker")


if __name__ == "__main__":
    unittest.main()
