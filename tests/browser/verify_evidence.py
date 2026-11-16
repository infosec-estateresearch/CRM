#!/usr/bin/env python3
"""CRM-CLIENT-001R2 annex B6: offline verifier of a real-browser evidence package.

It only reads files: no network, no Docker, no Git, no subprocess. It recomputes every
AC6b and AC12 verdict from the raw files of the package (SHA256SUMS, identity.json,
isolation.json, timestamps.json, the per-journey requests/console/csp records, the
screenshots and cleanup.json) and never trusts a pass/fail flag written by the runner.
The only value read from a journey's result.json is the structural signature of each
regression screen, which is data, not a verdict.

Usage:
  verify_evidence.py <package-dir> [--candidate-root <dir>] [--expect-candidate <sha>]
                     [--run <id>] [--public-summary <out-dir>]

Exit status: 0 PASS, 1 FAIL (causes on stdout, one per line), 2 usage error,
4 the public summary was REFUSED by the sanitiser (item class named; nothing written).

--public-summary writes public-summary.json and EVIDENCE.md, deterministically, holding
only the public-safe fields of annex B6 (AC6c). Raw evidence never leaves the restricted
store; reviewers cite it by relative path and sha256 only. The run's browser credential
may be given through the environment (CRM_BROWSER_USERNAME, CRM_BROWSER_PASSWORD, never
argv): the summary is refused, item class "credential", if it would contain either value.
"""
import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
import zipfile
from urllib.parse import parse_qs, urlparse

# ---- constants of the approved identity (annex B1, B2, B2a) -------------------------
PLAYWRIGHT_VERSION = "1.65.1"
GREENLET_VERSION = "3.5.6"
WHEEL_SHA256 = {
    "playwright": "5660e0b050a5bd5672bf8e366ed2580288a3d3640ff9444436ed2d890d3dc442",
    "greenlet": "975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1",
}
CFT_VERSION = "157.0.8103.78"
CFT_REVISION = "1717349"
CFT_BINARY_SHA256 = {
    "chrome": "f60cb86024464df9740504a1584b605c2b3cf107625ff11e1da22c875c1627e8",
    "headless-shell": "8e4c5db8c070059cb570a05c171dfcaec022d46334722ec3a16376614d687a96",
}
IMAGE_INDEX_DIGEST = "sha256:0ab41a37431309d72b7a26f40ef1fdb464a62740196b2143965a2f59dc090409"
IMAGE_AMD64_DIGEST = "sha256:ce84a3d75a47e81657d2ec2c0a949e6e0ef790abdc32ce6819220a3df987ff9a"
IMAGE_CONFIG_ID = "sha256:eccd588fcb91db7fbc8db45ba5e8aa3afb31a13a57d445c3f65be10f0b692261"
# Superseded pin (finding I1): rejected explicitly so the failure names the cause.
PREVIOUS_IMAGE_PINS = {
    "index_digest": "sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031",
    "amd64_digest": "sha256:7d030ac0638b279ecc72493f8b6706fecef80a893679a23b02f912905c4915c0",
    "config_id": "sha256:b6862d3036a770b5c0e8a0987e9546dc1844f10ba70925f746e7a44ca84660c0",
}

JOURNEYS = ("J1", "J2", "J3", "J4", "J5")
CONTRACT_JOURNEYS = {"J1": 1, "J2": 2, "J3": 1, "J4": 1}
CANARY_PATH = "/client/custom/src/crm/release-canary.js"
SCREENS = ("login", "account-list", "account-detail", "enquiry-list", "enquiry-detail", "stream")
JOURNEY_FILES = ("result.json", "requests.jsonl", "console.jsonl", "csp.jsonl", "trace.zip")
TOP_FILES = ("invocation.txt", "identity.json", "isolation.json", "timestamps.json",
             "beta-before.json", "beta-after.json", "crmdev-before.json", "cleanup.json",
             "scan/db-status.json", "scan/image.json", "scan/wheels.json", "scan/cft.json",
             "scan/osv.json", "scan/triage.json")
ISOLATION_IDS = ("app-http", "db-3306", "app-crmnet", "host-dev-8180", "host-dev-8290",
                 "loopback-8280", "beta-gateway", "beta-app", "public-443", "dns-public")
CLEANUP_LABELS = ("env_file_identical", "no_client001r2_objects", "crm_app_on_crm_net_only",
                  "stack_running_healthy_same_images", "root_status_unchanged",
                  "client_custom_tree_equals_d0", "beta_unchanged")
TIME_LIMIT = 3.0
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class Report:
    def __init__(self):
        self.failures = []  # (group, cause, journey)

    def fail(self, group, cause, journey=None):
        self.failures.append((group, cause, journey))

    def failed(self, group=None, journey=None):
        return [f for f in self.failures
                if (group is None or f[0] == group) and (journey is None or f[2] == journey)]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(pkg, rel, rep, group):
    try:
        with open(os.path.join(pkg, rel), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        rep.fail(group, f"unreadable: {rel}")
        return None


def load_jsonl(pkg, rel, rep, group, journey=None):
    rows = []
    try:
        with open(os.path.join(pkg, rel), encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
    except (OSError, ValueError):
        rep.fail(group, f"unreadable: {rel}", journey)
        return None
    return rows


# ---- files and SHA256SUMS -------------------------------------------------------------
def package_files(pkg):
    found = {}
    for root, dirs, files in os.walk(pkg, followlinks=False):
        for name in dirs + files:
            path = os.path.join(root, name)
            if os.path.islink(path):
                found[os.path.relpath(path, pkg)] = "symlink"
        for name in files:
            path = os.path.join(root, name)
            if not os.path.islink(path):
                found[os.path.relpath(path, pkg)] = "file"
    return found


def required_files():
    req = list(TOP_FILES) + ["SHA256SUMS"]
    for j in JOURNEYS:
        req += [f"journeys/{j}/{f}" for f in JOURNEY_FILES]
    for j in ("J1", "J5"):
        req += [f"journeys/{j}/{s}.png" for s in SCREENS]
    return req


def check_files(pkg, rep):
    present = package_files(pkg)
    for rel, kind in sorted(present.items()):
        if kind == "symlink":
            rep.fail("files", f"symlink-in-package: {rel}")
    for rel in required_files():
        if present.get(rel) != "file":
            rep.fail("files", f"missing-file: {rel}")
    sums = {}
    path = os.path.join(pkg, "SHA256SUMS")
    if present.get("SHA256SUMS") == "file":
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.fullmatch(r"([0-9a-f]{64})  (\S.*)\n?", line)
                if not m:
                    rep.fail("files", "sha256sums-malformed-line")
                    continue
                sums[m.group(2)] = m.group(1)
    for rel, want in sorted(sums.items()):
        full = os.path.join(pkg, rel)
        if os.path.islink(full) or not os.path.isfile(full):
            rep.fail("files", f"missing-file: {rel}")
        elif sha256_file(full) != want:
            rep.fail("files", f"sha256-mismatch: {rel}")
    for rel, kind in sorted(present.items()):
        if kind == "file" and rel != "SHA256SUMS" and rel not in sums:
            rep.fail("files", f"unlisted-file: {rel}")
    return sums


# ---- identity -------------------------------------------------------------------------
def check_identity(pkg, rep, expect_candidate):
    ident = load_json(pkg, "identity.json", rep, "identity")
    if not isinstance(ident, dict):
        return
    g = "identity"

    def get(*keys):
        cur = ident
        for k in keys:
            cur = cur.get(k) if isinstance(cur, dict) else None
        return cur

    cand = get("candidate")
    if not (isinstance(cand, str) and re.fullmatch(r"[0-9a-f]{40}", cand)):
        rep.fail(g, "candidate-identity-mismatch: not a commit id")
    elif expect_candidate and cand != expect_candidate:
        rep.fail(g, "candidate-identity-mismatch: differs from the expected candidate")
    for key in ("transition_manifest_sha256", "snapshot_manifest_sha256"):
        v = get(key)
        if not (isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)):
            rep.fail(g, f"candidate-identity-mismatch: {key}")
    if get("python", "playwright_version") != PLAYWRIGHT_VERSION:
        rep.fail(g, "wrong-playwright-version")
    if get("python", "playwright_dist_count") != 1 or get("python", "playwright_under_pydeps") is not True:
        rep.fail(g, "playwright-distribution-location")
    if get("python", "greenlet_version") != GREENLET_VERSION:
        rep.fail(g, "wrong-greenlet-version")
    wheels = get("wheels")
    for name, want in WHEEL_SHA256.items():
        if not isinstance(wheels, dict) or wheels.get(name) != want:
            rep.fail(g, f"wheel-identity-mismatch: {name}")
    kind = get("browser", "kind")
    if kind not in CFT_BINARY_SHA256 or get("browser", "binary_sha256") != CFT_BINARY_SHA256.get(kind):
        rep.fail(g, "wrong-browser-binary")
    if get("browser", "running_version") != CFT_VERSION:
        rep.fail(g, "wrong-browser-version")
    if get("browser", "revision") != CFT_REVISION:
        rep.fail(g, "wrong-browser-revision")
    if get("browser", "process_exe_is_pinned") is not True:
        rep.fail(g, "browser-process-not-the-pinned-binary")
    if get("browser", "ms_playwright_processes") != 0:
        rep.fail(g, "bundled-browser-executed")
    if get("browser", "ldd_missing") != 0:
        rep.fail(g, "browser-libraries-missing")
    if get("driver", "ldd_missing") != 0:
        rep.fail(g, "node-driver-libraries-missing")
    if get("driver", "required_library_resolved") is not True:
        rep.fail(g, "node-driver-required-library-unresolved")
    probe = get("compat_probe")
    if not (isinstance(probe, dict) and probe.get("passed") is True
            and isinstance(probe.get("steps"), dict) and probe["steps"]
            and all(v is True for v in probe["steps"].values())):
        rep.fail(g, "compatibility-probe-not-passed")
    image = get("image") if isinstance(get("image"), dict) else {}
    for key, want in (("index_digest", IMAGE_INDEX_DIGEST), ("amd64_digest", IMAGE_AMD64_DIGEST),
                      ("config_id", IMAGE_CONFIG_ID)):
        if image.get(key) != want:
            if image.get(key) == PREVIOUS_IMAGE_PINS[key]:
                rep.fail(g, f"image-identity-mismatch: {key} (previous pin rejected)")
            else:
                rep.fail(g, f"image-identity-mismatch: {key}")
    repo_digest = image.get("repo_digest")
    if not (isinstance(repo_digest, str) and repo_digest.endswith("@" + IMAGE_AMD64_DIGEST)):
        rep.fail(g, "image-identity-mismatch: repo_digest")
    # container hardening (annex B3)
    c = get("container") if isinstance(get("container"), dict) else {}
    if "ALL" not in (c.get("CapDrop") or []):
        rep.fail(g, "container-hardening: capabilities not all dropped")
    if c.get("ReadonlyRootfs") is not True:
        rep.fail(g, "container-hardening: rootfs not read-only")
    if c.get("Privileged") is not False:
        rep.fail(g, "container-hardening: privileged")
    if c.get("User") != "65534:65534":
        rep.fail(g, "container-hardening: not uid 65534")
    if c.get("NetworkMode") in (None, "host"):
        rep.fail(g, "container-hardening: host or unknown network mode")
    if not any(str(o).startswith("no-new-privileges") for o in (c.get("SecurityOpt") or [])):
        rep.fail(g, "container-hardening: no-new-privileges missing")
    if any("docker.sock" in json.dumps(m) for m in (c.get("Mounts") or [])):
        rep.fail(g, "container-hardening: docker socket mounted")


# ---- isolation ------------------------------------------------------------------------
def check_isolation(pkg, rep):
    iso = load_json(pkg, "isolation.json", rep, "isolation")
    if not isinstance(iso, dict):
        return
    g = "isolation"
    routes = []
    for line in str(iso.get("route_table", "")).splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 8:
            routes.append((cols[1], cols[7]))
    if ("00000000", "00000000") in routes:
        rep.fail(g, "route-table-has-a-default-route")
    if len(routes) != 1:
        rep.fail(g, "route-table-not-a-single-network")
    seen = {}
    for t in iso.get("targets") or []:
        if isinstance(t, dict) and isinstance(t.get("id"), str):
            seen[t["id"]] = t
    for tid in ISOLATION_IDS:
        t = seen.get(tid)
        if t is None:
            rep.fail(g, f"isolation-target-missing: {tid}")
            continue
        want = "success" if tid == "app-http" else "fail"
        if t.get("expected") != want:
            rep.fail(g, f"isolation-expectation-wrong: {tid}")
        if want == "fail" and t.get("actual") != "fail":
            rep.fail(g, f"unexpected-isolation-success: {tid}")
        if want == "success" and t.get("actual") != "success":
            rep.fail(g, f"isolation-target-unreachable: {tid}")
        if want == "fail" and not (isinstance(t.get("elapsed"), (int, float))
                                   and t["elapsed"] <= TIME_LIMIT + 1.0):
            rep.fail(g, f"isolation-probe-too-slow: {tid}")


# ---- timestamps and journeys ----------------------------------------------------------
def png_ok(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(33)
    except OSError:
        return False
    return head[:8] == PNG_MAGIC and head[12:16] == b"IHDR" and len(head) >= 24 \
        and int.from_bytes(head[16:20], "big") > 0 and int.from_bytes(head[20:24], "big") > 0


def canary_requests(rows):
    return [r for r in rows if isinstance(r, dict)
            and urlparse(str(r.get("url", ""))).path.endswith(CANARY_PATH)]


def r_value(url):
    values = parse_qs(urlparse(url).query).get("r", [])
    return int(values[0]) if len(values) == 1 and re.fullmatch(r"\d+", values[0]) else None


def read_canary_hashes(root, rep):
    out = {}
    paths = {1: os.path.join(root, "client", "custom", "src", "crm", "release-canary.js"),
             2: os.path.join(root, "tests", "browser", "fixtures", "canary-transition", "v2",
                             "crm", "release-canary.js")}
    for contract, path in paths.items():
        try:
            out[contract] = sha256_file(path)
        except OSError:
            rep.fail("journeys", f"candidate-canary-unreadable: contract {contract}")
    return out


def check_journeys(pkg, rep, candidate_root):
    ts = load_json(pkg, "timestamps.json", rep, "timestamps")
    a = {}
    if isinstance(ts, dict):
        for i in range(6):
            v = ts.get(f"a{i}")
            if isinstance(v, int) and not isinstance(v, bool) and v > 0:
                a[i] = v
            else:
                rep.fail("timestamps", f"timestamp-missing: a{i}")
        for i in range(1, 6):
            if i in a and i - 1 in a and a[i] <= a[i - 1]:
                rep.fail("timestamps", f"timestamp-not-advancing: a{i} <= a{i - 1}")
    hashes = read_canary_hashes(candidate_root, rep)
    last_r = None
    shots = {}
    for n, j in enumerate(JOURNEYS, start=1):
        base = f"journeys/{j}"
        reqs = load_jsonl(pkg, f"{base}/requests.jsonl", rep, "journeys", j)
        console = load_jsonl(pkg, f"{base}/console.jsonl", rep, "journeys", j)
        csp = load_jsonl(pkg, f"{base}/csp.jsonl", rep, "journeys", j)
        trace = os.path.join(pkg, base, "trace.zip")
        if not (os.path.isfile(trace) and zipfile.is_zipfile(trace)):
            rep.fail("journeys", "trace-invalid", j)
        if csp:
            rep.fail("journeys", "csp-violation", j)
        for c in console or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") in ("error", "pageerror") and (c.get("phase") != "probe" or j in CONTRACT_JOURNEYS):
                rep.fail("journeys", "canary-console-error", j)
                break
        if reqs is None:
            continue
        cr = canary_requests(reqs)
        if j in CONTRACT_JOURNEYS:
            ok = [r for r in cr if r.get("status") == 200 and r.get("from_cache") is False]
            if not ok:
                rep.fail("journeys", "cached-or-absent-fetch", j)
                continue
            rs = {r_value(str(r.get("url"))) for r in ok}
            if len(rs) != 1 or None in rs:
                rep.fail("journeys", "canary-url-without-a-single-r", j)
                continue
            r = rs.pop()
            if n in a and r != a[n]:
                rep.fail("journeys", "r-differs-from-the-crm-app-timestamp", j)
            if last_r is not None and r <= last_r:
                rep.fail("journeys", "r-not-advancing", j)
            last_r = r
            want = hashes.get(CONTRACT_JOURNEYS[j])
            if want and any(x.get("response_sha256") != want for x in ok):
                rep.fail("journeys", f"wrong-canary-contract: expected {CONTRACT_JOURNEYS[j]}", j)
        else:
            if any(r.get("status") == 200 for r in cr):
                rep.fail("journeys", "canary-present-after-restore", j)
        if j in ("J1", "J5"):
            result = load_json(pkg, f"{base}/result.json", rep, "journeys") or {}
            sigs = {}
            for item in result.get("assertions", []) if isinstance(result, dict) else []:
                if isinstance(item, dict) and str(item.get("id", "")).startswith("screen:"):
                    obs = item.get("observed")
                    if isinstance(obs, dict) and isinstance(obs.get("signature"), str) and obs.get("headings"):
                        sigs[item["id"][7:]] = obs["signature"]
            for s in SCREENS:
                if not png_ok(os.path.join(pkg, base, f"{s}.png")):
                    rep.fail("journeys", f"screenshot-invalid: {s}", j)
                if s not in sigs:
                    rep.fail("journeys", f"regression-screen-not-rendered: {s}", j)
            shots[j] = sigs
    if "J1" in shots and "J5" in shots:
        for s in SCREENS:
            if shots["J1"].get(s) != shots["J5"].get(s):
                rep.fail("journeys", f"regression-screen-mismatch: {s}", "J5")


# ---- scan and cleanup -----------------------------------------------------------------
def check_scan(pkg, rep):
    tri = load_json(pkg, "scan/triage.json", rep, "scan")
    if not isinstance(tri, dict) or not isinstance(tri.get("findings"), list):
        if tri is not None:
            rep.fail("scan", "triage-malformed")
        return
    for f in tri["findings"]:
        if isinstance(f, dict) and f.get("material") is True and f.get("resolution") in (None, "none"):
            rep.fail("scan", "unresolved-material-finding")
            break


def check_cleanup(pkg, rep):
    cl = load_json(pkg, "cleanup.json", rep, "cleanup")
    if isinstance(cl, dict):
        for label in CLEANUP_LABELS:
            if cl.get(label) is not True:
                rep.fail("cleanup", f"cleanup-failure: {label}")
        for label, value in cl.items():
            if not isinstance(value, bool):
                rep.fail("cleanup", f"cleanup-record-not-boolean: {label}")
            elif value is False and label not in CLEANUP_LABELS:
                rep.fail("cleanup", f"cleanup-failure: {label}")
    before = load_json(pkg, "beta-before.json", rep, "cleanup")
    after = load_json(pkg, "beta-after.json", rep, "cleanup")
    if before is not None and after is not None and before != after:
        rep.fail("cleanup", "beta-changed")


def verify(pkg, candidate_root=None, expect_candidate=None):
    candidate_root = candidate_root or os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    rep = Report()
    if os.path.islink(pkg) or not os.path.isdir(pkg):
        rep.fail("files", "package-not-a-real-directory")
        return rep, {}
    sums = check_files(pkg, rep)
    check_identity(pkg, rep, expect_candidate)
    check_isolation(pkg, rep)
    check_journeys(pkg, rep, candidate_root)
    check_scan(pkg, rep)
    check_cleanup(pkg, rep)
    return rep, sums


# ---- public summary (AC6c) ------------------------------------------------------------
class Refused(Exception):
    def __init__(self, item_class):
        super().__init__(item_class)
        self.item_class = item_class


MASKS = (
    (re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b"), "TS"),
    (re.compile(r"\bsha256:[0-9a-f]{64}\b"), "DIGEST"),
    (re.compile(r"\b[0-9a-f]{40}\b"), "COMMIT"),
)
PORT_RE = re.compile(r"(?i)\bport\b[ =:]*\d{2,5}\b|(?<=[A-Za-z0-9\]\)]):\d{2,5}(?![\d:A-Za-z])")
IPV4_RE = re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])")
IPV6_RE = re.compile(r"(?<![\w:])[0-9A-Fa-f:]*:[0-9A-Fa-f:.]*:[0-9A-Fa-f:.]*(?![\w:])")
URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://|\bwww\.")
EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
ENV_VALUE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*=\S")
ENV_NAME_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
PATH_RE = re.compile(r"(?<![\w.])/(?:[\w.-]+/)*[\w.-]+")
HOST_RE = re.compile(r"(?i)\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}\b")
ID_RE = re.compile(r"\b(?:[0-9a-f]{64}|[0-9a-f]{12})\b")
EMAIL_ALLOWED_DOMAIN = "example.test"


# The run's browser credential (the synthetic crm-dev login) is given to the sanitiser through
# the environment only, never through argv. Any string that contains one of its values is
# refused, whatever else it looks like. The values are never printed or stored.
CREDENTIAL_ENV = ("CRM_BROWSER_USERNAME", "CRM_BROWSER_PASSWORD")


def contains_credential(text):
    return any(v and v in text for v in (os.environ.get(n) for n in CREDENTIAL_ENV))


def classify(text, allow_hash=False):
    """The first forbidden item class found in a string, or None."""
    if contains_credential(text):
        return "credential"
    for rx, repl in MASKS:
        text = rx.sub(repl, text)
    if URL_RE.search(text):
        return "url"
    for m in EMAIL_RE.finditer(text):
        if m.group(1).lower() != EMAIL_ALLOWED_DOMAIN:
            return "email"
    text = EMAIL_RE.sub("EMAIL", text)
    for m in IPV4_RE.finditer(text):
        try:
            ipaddress.IPv4Address(m.group(0))
            return "ipv4"
        except ValueError:
            pass
    for m in IPV6_RE.finditer(text):
        try:
            ipaddress.IPv6Address(m.group(0))
            return "ipv6"
        except ValueError:
            pass
    if ENV_VALUE_RE.search(text):
        return "env-value"
    if ENV_NAME_RE.search(text):
        return "env-name"
    if PATH_RE.search(text):
        return "path"
    if PORT_RE.search(text):
        return "port"
    if HOST_RE.search(text):
        return "hostname"
    if not allow_hash and ID_RE.search(text):
        return "container-or-network-id"
    return None


TYPES = {
    "commit": re.compile(r"[0-9a-f]{40}"),
    "sha256": re.compile(r"[0-9a-f]{64}"),
    "digest": re.compile(r"sha256:[0-9a-f]{64}"),
    "hash": re.compile(r"(?:sha256:)?[0-9a-f]{64}"),
    "version": re.compile(r"v?\d+(?:\.\d+){1,3}"),
    "timestamp": re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"),
    "label": re.compile(r"[A-Za-z][A-Za-z0-9_:-]{0,63}"),
    "run": re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"),
    # a relative path inside the package: plain components, and an extension only from a
    # short allow-list (so a host name or an address cannot pass as a file name)
    "path": re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*(?:\.(?:json|jsonl|png|zip|txt|md))?"),
}
HASH_TYPES = ("commit", "sha256", "digest", "hash")


def safe_str(kind, value):
    """value if it matches its field type and carries no forbidden item; else Refused."""
    if not isinstance(value, str):
        raise Refused("free-text")
    if contains_credential(value):
        raise Refused("credential")
    if kind == "path":
        if not TYPES["path"].fullmatch(value) or len(value) > 200:
            raise Refused(classify(value) or "free-text")
        return value
    cls = classify(value, allow_hash=kind in HASH_TYPES)
    if cls:
        raise Refused(cls)
    if not TYPES[kind].fullmatch(value):
        raise Refused("free-text")
    return value


def safe_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Refused("free-text")
    return value


def verdict_name(rep, group=None, journey=None):
    return "FAIL" if rep.failed(group, journey) else "PASS"


def build_summary(pkg, rep, sums, run):
    """The public-safe summary (annex B6). Every string is type-checked; anything else
    raises Refused with the item class."""
    def jload(rel):
        try:
            with open(os.path.join(pkg, rel), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}
    ident, db, tri, cleanup = (jload("identity.json"), jload("scan/db-status.json"),
                               jload("scan/triage.json"), jload("cleanup.json"))
    get = lambda d, *ks: _dig(d, ks)  # noqa: E731
    summary = {
        "run": safe_str("run", run),
        "candidate": safe_str("commit", get(ident, "candidate")),
        "image": {"index_digest": safe_str("digest", get(ident, "image", "index_digest")),
                  "amd64_digest": safe_str("digest", get(ident, "image", "amd64_digest")),
                  "config_id": safe_str("digest", get(ident, "image", "config_id"))},
        "wheels": {safe_str("label", k): safe_str("sha256", v)
                   for k, v in sorted((get(ident, "wheels") or {}).items())},
        "chrome_for_testing": {"version": safe_str("version", get(ident, "browser", "running_version")),
                               "binary_sha256": safe_str("sha256", get(ident, "browser", "binary_sha256"))},
        "grype": {"version": safe_str("version", get(db, "grype_version")),
                  "db_built": safe_str("timestamp", get(db, "db_built")),
                  "db_checksum": safe_str("hash", get(db, "db_checksum"))},
        "findings": _counts(tri),
        "verdict": verdict_name(rep),
        "acs": {"AC6b": verdict_name_excluding(rep, "cleanup"), "AC12": verdict_name(rep, "cleanup")},
        "journeys": {j: {"verdict": verdict_name(rep, None, j),
                         "assertions": _assertion_ids(pkg, j, rep)} for j in JOURNEYS},
        "raw_file_sha256": {safe_str("path", k): safe_str("sha256", v) for k, v in sorted(sums.items())},
        "sha256sums_sha256": safe_str("sha256", sha256_file(os.path.join(pkg, "SHA256SUMS"))),
        "cleanup": {},
    }
    for label, value in sorted(cleanup.items()):
        if not isinstance(value, bool):
            raise Refused("free-text")
        summary["cleanup"][safe_str("label", label)] = value
    return summary


def _dig(d, keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def verdict_name_excluding(rep, group):
    return "FAIL" if [f for f in rep.failures if f[0] != group] else "PASS"


def _counts(tri):
    sev, cls = {}, {}
    for f in (tri.get("findings") or []) if isinstance(tri, dict) else []:
        if not isinstance(f, dict):
            raise Refused("free-text")
        s = safe_str("label", str(f.get("severity", "")).lower() or "unknown")
        c = safe_str("label", str(f.get("triage", "")) or "untriaged")
        sev[s] = sev.get(s, 0) + 1
        cls[c] = cls.get(c, 0) + 1
    return {"by_severity": dict(sorted(sev.items())), "by_triage_class": dict(sorted(cls.items()))}


def _assertion_ids(pkg, journey, rep):
    """Assertion ids with the verifier's own verdict per recomputed check family."""
    ids = ["no-csp-violation", "no-console-error"]
    ids += ["canary-contract", "canary-url-r", "r-advanced", "new-network-fetch"] if journey in CONTRACT_JOURNEYS \
        else ["canary-absent", "r-advanced"]
    if journey in ("J1", "J5"):
        ids += [f"screen:{s}" for s in SCREENS]
    failed = bool(rep.failed("journeys", journey))
    return {i: ("FAIL" if failed else "PASS") for i in ids}


def render_markdown(summary):
    lines = ["# CRM-CLIENT-001R2 evidence summary", "",
             f"- run: {summary['run']}", f"- candidate: {summary['candidate']}",
             f"- verdict: {summary['verdict']} (AC6b {summary['acs']['AC6b']}, AC12 {summary['acs']['AC12']})",
             f"- image index digest: {summary['image']['index_digest']}",
             f"- image amd64 digest: {summary['image']['amd64_digest']}",
             f"- Chrome for Testing: {summary['chrome_for_testing']['version']} "
             f"(binary sha256 {summary['chrome_for_testing']['binary_sha256']})",
             f"- grype: {summary['grype']['version']}, database built {summary['grype']['db_built']}, "
             f"checksum {summary['grype']['db_checksum']}",
             f"- SHA256SUMS sha256: {summary['sha256sums_sha256']}", "", "## Wheels", ""]
    lines += [f"- {k}: {v}" for k, v in summary["wheels"].items()]
    lines += ["", "## Findings", ""]
    lines += [f"- severity {k}: {v}" for k, v in summary["findings"]["by_severity"].items()]
    lines += [f"- triage {k}: {v}" for k, v in summary["findings"]["by_triage_class"].items()]
    lines += ["", "## Journeys", ""]
    for j, data in summary["journeys"].items():
        lines.append(f"- {j}: {data['verdict']}")
        lines += [f"  - {i}: {v}" for i, v in data["assertions"].items()]
    lines += ["", "## Cleanup", ""]
    lines += [f"- {k}: {'true' if v else 'false'}" for k, v in summary["cleanup"].items()]
    lines += ["", "## Raw files (sha256 by relative path)", ""]
    lines += [f"- {k}: {v}" for k, v in summary["raw_file_sha256"].items()]
    return "\n".join(lines) + "\n"


def final_scan(text):
    """The rendered markdown is scanned again, as a whole, for the structured classes."""
    if contains_credential(text):
        raise Refused("credential")
    for rx, repl in MASKS:
        text = rx.sub(repl, text)
    text = re.sub(r"(?m)^- (?:[A-Za-z0-9_][A-Za-z0-9_./-]*): [0-9a-f]{64}$", "- PATH: HASH", text)
    if URL_RE.search(text):
        raise Refused("url")
    for m in EMAIL_RE.finditer(text):
        if m.group(1).lower() != EMAIL_ALLOWED_DOMAIN:
            raise Refused("email")
    for m in IPV4_RE.finditer(text):
        try:
            ipaddress.IPv4Address(m.group(0))
            raise Refused("ipv4")
        except ValueError:
            pass
    if ENV_VALUE_RE.search(text):
        raise Refused("env-value")


def write_public_summary(pkg, rep, sums, run, outdir):
    summary = build_summary(pkg, rep, sums, run)
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    md = render_markdown(summary)
    if contains_credential(text):
        raise Refused("credential")
    final_scan(md)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "public-summary.json"), "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(outdir, "EVIDENCE.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("package")
    ap.add_argument("--candidate-root")
    ap.add_argument("--expect-candidate")
    ap.add_argument("--run")
    ap.add_argument("--public-summary", metavar="OUTDIR")
    args = ap.parse_args(argv)
    pkg = os.path.abspath(args.package)
    rep, sums = verify(pkg, args.candidate_root, args.expect_candidate)
    for group, cause, journey in rep.failures:
        print(f"FAIL [{group}{'/' + journey if journey else ''}] {cause}")
    if args.public_summary:
        run = args.run or os.path.basename(pkg.rstrip("/"))
        try:
            write_public_summary(pkg, rep, sums, run, args.public_summary)
        except Refused as exc:
            print(f"REFUSED: public summary not written; forbidden item class: {exc.item_class}",
                  file=sys.stderr)
            return 4
    print("VERDICT: " + verdict_name(rep))
    return 1 if rep.failures else 0


if __name__ == "__main__":
    sys.exit(main())
