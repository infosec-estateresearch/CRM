"""CRM-WIP-LINK-001: the "Open WIP / Revenue" Account button.

No Node, browser or network here, so the handler is checked statically: the
metadata item, the client-code policy, the required elements, and a reference
model of the section 3.1 rules whose every rule must be visible in the handler
(a weakened handler is detected). JavaScript behaviour is NOT executed by this
suite; the operator's real-browser run asserts the behaviour table."""

import json
import os
import re
import shutil
import subprocess
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLIENTDEFS = os.path.join(REPO, "custom", "Espo", "Custom", "Resources", "metadata", "clientDefs", "Account.json")
HANDLER_REL = "client/custom/src/handlers/account-open-wip.js"
HANDLER = os.path.join(REPO, HANDLER_REL)
BASE = "6e1766980e24d781d498727d4fe5db43cdeadbb7"

# The base's relationshipPanels block, byte for byte.
BASE_RELATIONSHIP_PANELS = '''    "relationshipPanels": {
        "branches": {
            "layout": "listForBranches",
            "create": true,
            "select": true
        }
    }'''

ITEM_KEYS = {"name", "text", "handler", "actionFunction", "acl", "aclScope", "style"}
OPTIONAL_KEYS = {"iconClass"}
ALLOWED_PATHS = {
    "client/custom/src/handlers/account-open-wip.js",
    "custom/Espo/Custom/Resources/metadata/clientDefs/Account.json",
    "custom/Espo/Custom/Resources/i18n/en_US/Account.json",
    "scripts/deploy_custom.sh",
    "tests/unit/test_wip_link.py",
    "tests/unit/test_client_delivery.py",
    "tests/unit/test_scripts.py",
    "docs/BUILD.md",
    "docs/WIP-LINK.md",
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|(?<=[;{}\s])//[^\n]*$", "", js)


def check_metadata(doc, raw=None):
    """Problems with the Account clientDefs; [] when it is as the WO requires."""
    problems = []
    if raw is not None and BASE_RELATIONSHIP_PANELS not in raw:
        problems.append("relationshipPanels is not byte-identical to the base")
    if set(doc) != {"relationshipPanels", "menu"}:
        problems.append(f"top-level keys: {sorted(doc)}")
    menu = doc.get("menu")
    if not isinstance(menu, dict) or set(menu) != {"detail"}:
        return problems + ["menu must be exactly {detail}"]
    detail = menu["detail"]
    if not isinstance(detail, dict) or set(detail) != {"buttons"}:
        return problems + ["menu.detail must be exactly {buttons}"]
    buttons = detail["buttons"]
    if not isinstance(buttons, list) or len(buttons) != 1:
        return problems + ["menu.detail.buttons must hold exactly one item"]
    item = buttons[0]
    keys = set(item)
    if not ITEM_KEYS <= keys or not keys <= ITEM_KEYS | OPTIONAL_KEYS:
        problems.append(f"item keys: {sorted(keys)}")
    for key, value in {"name": "openWip", "text": "Open WIP / Revenue", "actionFunction": "openWip",
                       "acl": "read", "aclScope": "Account", "style": "default",
                       "handler": "custom:handlers/account-open-wip"}.items():
        if item.get(key) != value:
            problems.append(f"item {key} is {item.get(key)!r}")
    for key in ("link", "url", "data"):
        if key in item:
            problems.append(f"item carries {key}")
    return problems


def handler_path_for(handler):
    """EspoCRM's rule: custom:<path> is client/custom/src/<path>.js."""
    assert handler.startswith("custom:")
    return os.path.join(REPO, "client", "custom", "src", handler[len("custom:"):] + ".js")


# ---- reference model of WO section 3.1 (checked statically against the handler) ----
ID_PATTERN = "^[A-Za-z0-9]+$"


def model_base(value):
    """The base the handler must accept (without trailing '/'), or None."""
    from urllib.parse import urlsplit
    if not isinstance(value, str) or not value:
        return None
    if "?" in value or "#" in value or "@" in value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    return value[:-1] if value.endswith("/") else value


def model_target(base, ident):
    from urllib.parse import quote
    b = model_base(base)
    if b is None or not isinstance(ident, str) or not re.match(ID_PATTERN, ident):
        return None
    return f"{b}/crm/firm/{quote(ident, safe='')}"


BEHAVIOUR_TABLE = [
    ("http://wip.example:8310", "ID1", "http://wip.example:8310/crm/firm/ID1"),
    ("https://wip.example/app/", "ID1", "https://wip.example/app/crm/firm/ID1"),
    (None, "ID1", None), ("", "ID1", None), (42, "ID1", None),
    ("javascript:alert(1)", "ID1", None), ("data:text/html,x", "ID1", None), ("ftp://wip.example", "ID1", None),
    ("http://user:pass@wip.example", "ID1", None), ("http://wip.example?x=1", "ID1", None),
    ("http://wip.example/#x", "ID1", None),
    ("http://wip.example", "", None), ("http://wip.example", "a/b", None), ("http://wip.example", "a b", None),
    ("http://wip.example", "../x", None),
]

# Every rule of the model and the handler text that implements it.
HANDLER_RULES = {
    "protocol http": r"url\.protocol\s*!==\s*'http:'",
    "protocol https": r"url\.protocol\s*!==\s*'https:'",
    "protocol is a conjunction (both required)": r"!==\s*'http:'\s*&&\s*url\.protocol\s*!==\s*'https:'",
    "host required": r"!url\.host",
    "user-info username": r"url\.username\s*!==\s*''",
    "user-info password": r"url\.password\s*!==\s*''",
    "query": r"url\.search\s*!==\s*''",
    "fragment": r"url\.hash\s*!==\s*''",
    "raw query/fragment text": r"value\.indexOf\('\?'\)\s*!==\s*-1\s*\|\|\s*value\.indexOf\('#'\)\s*!==\s*-1",
    "raw user-info text": r"value\.indexOf\('@'\)\s*!==\s*-1",
    "string base only": r"typeof value !== 'string'",
    "empty base": r"value === ''",
    "trailing slash stripped once": r"value\.charAt\(value\.length - 1\) === '/'",
    "id pattern": r"ID_PATTERN\s*=\s*/\^\[A-Za-z0-9\]\+\$/",
    "id tested": r"ID_PATTERN\.test\(id\)",
    "id string only": r"typeof id !== 'string'",
    "target path": r"base \+ '/crm/firm/' \+ encodeURIComponent\(id\)",
    "new tab, noopener, noreferrer": r"window\.open\(target, '_blank', 'noopener,noreferrer'\)",
    "not configured warning": r"The WIP link is not configured\.",
    "invalid base stops": r"if \(base === null\) \{\s*this\.warn\(NOT_CONFIGURED\);\s*return;",
    "invalid id stops": r"if \(id === null\) \{\s*this\.warn\(BAD_ID\);\s*return;",
    "failure isolated": r"\} catch \(e\) \{\s*this\.warn\(FAILED\);",
    "inputs": r"this\.view\.model\.id.*?this\.view\.getConfig\(\)\.get\('wipBaseUrl'\)",
}

POLICY = {
    "remote URL literal": r"""['"`]\s*(?:[a-z][a-z0-9+.-]*:)?//""",
    "any http(s) URL text": r"https?://",
    "eval": r"\beval\s*\(",
    "new Function": r"\bnew\s+Function\b",
    "document.write": r"document\s*\.\s*write",
    "innerHTML assignment": r"\b(?:inner|outer)HTML\b|insertAdjacentHTML",
    "network API": r"\bfetch\s*\(|XMLHttpRequest|\$\.ajax|Espo\.Ajax|sendBeacon|WebSocket|EventSource|importScripts",
    "storage API": r"localStorage|sessionStorage|indexedDB|document\s*\.\s*cookie|\.cookie\b|\bcaches\b",
    "import/export": r"(?m)^\s*(?:import|export)\b",
    "location navigation": r"\blocation\s*(?:\.|=)",
}
REQUIRED = {
    "AMD define": r"^define\(\[",
    "encodeURIComponent": r"encodeURIComponent",
    "http protocol check": r"'http:'",
    "https protocol check": r"'https:'",
    "noopener": r"noopener",
    "noreferrer": r"noreferrer",
    "openWip": r"prototype\.openWip\s*=\s*function",
    "returns the class": r"return Handler;",
}


def handler_problems(js):
    code = strip_comments(js)
    problems = []
    for name, pattern in POLICY.items():
        if re.search(pattern, code):
            problems.append(f"policy: {name}")
    for name, pattern in REQUIRED.items():
        if not re.search(pattern, code, flags=re.M):
            problems.append(f"required element missing: {name}")
    for name, pattern in HANDLER_RULES.items():
        if not re.search(pattern, code, flags=re.S):
            problems.append(f"rule not implemented: {name}")
    opens = re.findall(r"window\.open\(([^)]*)\)", code)
    if opens != ["target, '_blank', 'noopener,noreferrer'"]:
        problems.append(f"window.open calls: {opens}")
    if len(re.findall(r"'/crm/firm/'", code)) != 1:
        problems.append("the route literal must appear exactly once")
    literals = re.findall(r"""'([^'\n]*)'""", code)
    if [x for x in literals if x.startswith("/") and x not in ("/", "/crm/firm/")]:
        problems.append("a path literal other than /crm/firm/")
    return problems


class TestClientDefs(unittest.TestCase):
    def test_metadata_is_as_required(self):
        raw = read(CLIENTDEFS)
        self.assertEqual(check_metadata(json.loads(raw), raw), [])

    def test_relationship_panels_is_byte_identical(self):
        self.assertIn(BASE_RELATIONSHIP_PANELS, read(CLIENTDEFS))
        if shutil.which("git"):
            res = subprocess.run(["git", "-C", REPO, "show",
                                  f"{BASE}:custom/Espo/Custom/Resources/metadata/clientDefs/Account.json"],
                                 capture_output=True, text=True)
            if res.returncode == 0:  # the base commit is present in this checkout
                self.assertIn(BASE_RELATIONSHIP_PANELS, res.stdout)
                self.assertEqual(json.loads(res.stdout)["relationshipPanels"],
                                 json.loads(read(CLIENTDEFS))["relationshipPanels"])

    def test_handler_resolves_to_the_new_file(self):
        item = json.loads(read(CLIENTDEFS))["menu"]["detail"]["buttons"][0]
        self.assertEqual(handler_path_for(item["handler"]), HANDLER)
        self.assertTrue(os.path.isfile(HANDLER))

    def test_item_carries_no_url(self):
        text = read(CLIENTDEFS)
        self.assertNotRegex(text, r"https?:|//")

    # non-vacuity of the metadata check (e)
    def test_removing_the_item_is_detected(self):
        doc = json.loads(read(CLIENTDEFS))
        del doc["menu"]
        self.assertNotEqual(check_metadata(doc), [])
        doc = json.loads(read(CLIENTDEFS))
        doc["menu"]["detail"]["buttons"] = []
        self.assertNotEqual(check_metadata(doc), [])

    def test_a_changed_or_extended_item_is_detected(self):
        for mutate in (lambda i: i.update(link="x"), lambda i: i.update(url="x"),
                       lambda i: i.update(acl="edit"), lambda i: i.update(aclScope="Contact"),
                       lambda i: i.update(handler="custom:handlers/other"),
                       lambda i: i.update(data={"url": "x"}), lambda i: i.pop("acl"),
                       lambda i: i.update(actionFunction="other")):
            doc = json.loads(read(CLIENTDEFS))
            mutate(doc["menu"]["detail"]["buttons"][0])
            self.assertNotEqual(check_metadata(doc), [], mutate)
        doc = json.loads(read(CLIENTDEFS))
        doc["menu"]["detail"]["buttons"].append(dict(doc["menu"]["detail"]["buttons"][0]))
        self.assertNotEqual(check_metadata(doc), [])

    def test_a_changed_relationship_panels_text_is_detected(self):
        raw = read(CLIENTDEFS).replace('"select": true', '"select": false')
        self.assertNotEqual(check_metadata(json.loads(raw), raw), [])


class TestDiffScope(unittest.TestCase):
    def changed_paths(self):
        if not shutil.which("git"):
            return None
        tracked = subprocess.run(["git", "-C", REPO, "diff", "--name-only", BASE],
                                 capture_output=True, text=True)
        if tracked.returncode != 0:
            return None
        untracked = subprocess.run(["git", "-C", REPO, "ls-files", "-o", "--exclude-standard"],
                                   capture_output=True, text=True)
        return set(tracked.stdout.split()) | set(untracked.stdout.split())

    def test_only_allowlisted_paths_changed_and_no_php_added(self):
        paths = self.changed_paths()
        if paths is None:  # no Git metadata (an export): the PHP check below still runs
            paths = set()
        self.assertEqual(sorted(paths - ALLOWED_PATHS), [])
        self.assertFalse([p for p in paths if p.endswith(".php")])

    def test_no_php_or_other_asset_under_client(self):
        found = []
        for root, _, files in os.walk(os.path.join(REPO, "client")):
            found += [os.path.relpath(os.path.join(root, f), REPO) for f in files]
        self.assertEqual(found, [HANDLER_REL])

    def test_the_allowlist_check_detects_a_stray_file(self):
        self.assertNotEqual(sorted({"custom/Espo/Custom/Hooks/X.php"} - ALLOWED_PATHS), [])


class TestHandlerPolicy(unittest.TestCase):
    def test_handler_meets_policy_and_rules(self):
        self.assertEqual(handler_problems(read(HANDLER)), [])

    def test_handler_is_amd_without_import_export(self):
        js = read(HANDLER)
        self.assertTrue(js.lstrip().startswith("define(["))
        self.assertNotRegex(js, r"(?m)^\s*(import|export)\b")

    def test_no_url_or_host_anywhere_in_the_new_files(self):
        for path in (HANDLER, CLIENTDEFS):
            self.assertNotRegex(read(path), r"https?://|\b\d{1,3}(?:\.\d{1,3}){3}\b", path)

    MUTATIONS = {
        "drop the protocol check": lambda s: s.replace("url.protocol !== 'http:' && url.protocol !== 'https:'", "false"),
        "allow any protocol via ||": lambda s: s.replace("url.protocol !== 'http:' && url.protocol", "url.protocol !== 'http:' || url.protocol"),
        "drop the user-info check": lambda s: s.replace("url.username !== '' || url.password !== ''", "false"),
        "drop the password check": lambda s: s.replace(" || url.password !== ''", ""),
        "drop the query check": lambda s: s.replace("url.search !== '' || url.hash !== ''", "url.hash !== ''"),
        "drop the fragment check": lambda s: s.replace("url.search !== '' || url.hash !== ''", "url.search !== ''"),
        "drop the raw query/fragment check": lambda s: s.replace("value.indexOf('?') !== -1 || value.indexOf('#') !== -1", "false"),
        "drop encodeURIComponent": lambda s: s.replace("encodeURIComponent(id)", "id"),
        "drop noopener": lambda s: s.replace("'noopener,noreferrer'", "''"),
        "drop noreferrer": lambda s: s.replace("noopener,noreferrer", "noopener"),
        "hard-code a host": lambda s: s.replace("var target = base +", "var target = 'wip.example' +"),
        "fallback host": lambda s: s.replace("if (base === null) {\n                this.warn(NOT_CONFIGURED);\n\n                return;\n            }",
                                            "if (base === null) {\n                base = 'wip.example';\n            }"),
        "drop the id check": lambda s: s.replace("!ID_PATTERN.test(id)", "false"),
        "loosen the id pattern": lambda s: s.replace("/^[A-Za-z0-9]+$/", "/^.+$/"),
        "drop the host check": lambda s: s.replace("!url.host || !url.hostname", "false"),
        "no longer isolate failures": lambda s: s.replace("this.warn(FAILED);", "throw e;"),
        "remote URL literal": lambda s: s.replace("var ID_PATTERN", "var X = 'https://x.example';\n    var ID_PATTERN"),
        "network request": lambda s: s.replace("var target =", "fetch('x'); var target ="),
        "storage": lambda s: s.replace("var target =", "localStorage.setItem('a', id); var target ="),
        "innerHTML": lambda s: s.replace("var target =", "document.body.innerHTML = id; var target ="),
        "eval": lambda s: s.replace("var target =", "eval(id); var target ="),
        "second window.open": lambda s: s.replace("var target =", "window.open(id); var target ="),
        "second route literal": lambda s: s.replace("encodeURIComponent(id);", "encodeURIComponent(id) + '/crm/firm/';"),
    }

    def test_every_mutation_of_the_handler_is_detected(self):
        original = read(HANDLER)
        self.assertEqual(handler_problems(original), [])
        for name, mutate in self.MUTATIONS.items():
            with self.subTest(mutation=name):
                mutated = mutate(original)
                self.assertNotEqual(mutated, original, "the mutation did not apply")
                self.assertNotEqual(handler_problems(mutated), [], f"not detected: {name}")


class TestReferenceModel(unittest.TestCase):
    def test_behaviour_table(self):
        for base, ident, want in BEHAVIOUR_TABLE:
            with self.subTest(base=base, ident=ident):
                self.assertEqual(model_target(base, ident), want)

    def test_encoding_of_an_id_cannot_inject_a_path(self):
        self.assertIsNone(model_target("http://wip.example", "a/b"))
        self.assertIsNone(model_target("http://wip.example", "a?b"))

    def test_the_handler_id_pattern_is_the_models(self):
        m = re.search(r"ID_PATTERN\s*=\s*/(.*)/;", read(HANDLER))
        self.assertEqual(m.group(1), ID_PATTERN)

    def test_the_handler_names_every_row_of_the_behaviour_table_rule(self):
        # Each rejection class of the table maps to a rule that the handler carries.
        needed = {"javascript:/data:/ftp:": "protocol is a conjunction (both required)",
                  "user:pass@": "user-info username", "?x=1": "query", "#x": "fragment",
                  "missing/empty/non-string": "string base only", "empty id": "id pattern"}
        code = strip_comments(read(HANDLER))
        for row, rule in needed.items():
            with self.subTest(row=row):
                self.assertRegex(code, HANDLER_RULES[rule])


if __name__ == "__main__":
    unittest.main()
