#!/usr/bin/env python3
"""CRM-CLIENT-001R annex B2.3, B5, B6: the real-browser runner (journeys J1-J5).

Runs only inside the hardened runner container as uid 65534 (never on the host, never
as root). It contacts only the CRM base URL given in CRM_BROWSER_BASE_URL / --base-url;
the credentials of the synthetic test user come from the environment only
(CRM_BROWSER_USERNAME, CRM_BROWSER_PASSWORD) and never appear in argv or evidence.

Importing this module needs no Playwright: only run_journeys() imports it, so the
evidence layout (write_journey_files) and the identity logic can be unit-tested offline.

Operator control channel (the deploys happen outside the container, between journeys,
so that ONE browser context, and with it the HTTP cache, lives through D1-D3):
  <out>/.control/ready-<step>  written by the runner: the previous step is finished
  <out>/.control/go-<step>     written by the operator once the deploy for <step> is done;
                               JSON {"app_timestamp": <int read in crm-app>}
steps: start (a0), J1 (a1), J2 (a2), J3 (a3), J4 (a4), J5 (a5). The operator removes
.control/ before sealing the package. A step that is not released in time fails loudly.

Evidence layout under <out> (exactly annex B6):
  identity.json   timestamps.json
  journeys/<J>/result.json requests.jsonl console.jsonl csp.jsonl trace.zip *.png
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from urllib.parse import parse_qs, urlparse

PLAYWRIGHT_VERSION = "1.65.1"
GREENLET_VERSION = "3.5.6"
PYDEPS = "/tmp/pydeps"
CFT_VERSION = "157.0.8103.78"
CFT_REVISION = "1717349"
# kind -> (path, sha256 of the binary), annex B2a. The headless shell is the one allowed fallback.
BROWSERS = {
    "chrome": ("/opt/cft/chrome-linux64/chrome",
               "f60cb86024464df9740504a1584b605c2b3cf107625ff11e1da22c875c1627e8"),
    "headless-shell": ("/opt/cft/chrome-headless-shell-linux64/chrome-headless-shell",
                       "8e4c5db8c070059cb570a05c171dfcaec022d46334722ec3a16376614d687a96"),
}
NODE_DRIVER = PYDEPS + "/playwright/driver/node"
REQUIRED_LIBRARY = "libatomic.so.1"
BUNDLED_BROWSERS_PREFIX = "/ms-playwright"
WHEELS_DIR = "/wheels"

CANARY_MODULE = "custom:crm/release-canary"
CANARY_PATH = "/client/custom/src/crm/release-canary.js"
JOURNEYS = ("J1", "J2", "J3", "J4", "J5")
CONTRACT = {"J1": 1, "J2": 2, "J3": 1, "J4": 1}  # J5: absent
SCREENS = ("login", "account-list", "account-detail", "enquiry-list", "enquiry-detail", "stream")
JOURNEY_FILES = ("result.json", "requests.jsonl", "console.jsonl", "csp.jsonl", "trace.zip")
STEPS = ("start",) + JOURNEYS
STEP_TIMEOUT = int(os.environ.get("CRM_BROWSER_STEP_TIMEOUT", "1800"))


class RunnerError(Exception):
    pass


# --------------------------------------------------------------------------- evidence
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def journey_dir(out, jid):
    path = os.path.join(out, "journeys", jid)
    os.makedirs(path, exist_ok=True)
    return path


def write_journey_files(out, jid, requests, console, csp, assertions, extra=None):
    """The JSON files of one journey (the trace and the screenshots are written by
    Playwright into the same directory). Returns the directory."""
    path = journey_dir(out, jid)
    result = {"journey": jid, "assertions": assertions}
    result.update(extra or {})
    write_json(os.path.join(path, "result.json"), result)
    write_jsonl(os.path.join(path, "requests.jsonl"), requests)
    write_jsonl(os.path.join(path, "console.jsonl"), console)
    write_jsonl(os.path.join(path, "csp.jsonl"), csp)
    return path


def assertion(aid, ac, expected, observed, passed):
    return {"id": aid, "ac": ac, "expected": expected, "observed": observed, "pass": bool(passed)}


def canary_requests(requests):
    return [r for r in requests if urlparse(r.get("url", "")).path.endswith(CANARY_PATH)]


def canary_r(url):
    """The integer r= query value of a canary URL, or None."""
    values = parse_qs(urlparse(url).query).get("r", [])
    return int(values[0]) if len(values) == 1 and re.fullmatch(r"\d+", values[0]) else None


# --------------------------------------------------------------------------- identity
def collect_identity(kind="chrome", pydeps=PYDEPS, wheels_dir=WHEELS_DIR):
    """Runner-side identity (annex B2.3): versions through importlib.metadata (the 1.65.1
    wheel has no module version attribute), a single playwright distribution under pydeps,
    the wheel and browser-binary hashes. The operator adds its own keys later."""
    from importlib import metadata
    dists = [d for d in metadata.distributions()
             if (d.metadata["Name"] or "").lower() == "playwright"]
    import playwright  # noqa: F401  (located, not version-checked, through __file__)
    path, want_sha = BROWSERS[kind]
    ident = {
        "python": {
            "playwright_version": metadata.version("playwright"),
            "playwright_dist_count": len(dists),
            "playwright_under_pydeps": bool(dists) and all(
                str(d.locate_file("")).startswith(pydeps) for d in dists)
                and os.path.realpath(playwright.__file__).startswith(pydeps),
            "greenlet_version": metadata.version("greenlet"),
        },
        "wheels": {},
        "browser": {"kind": kind, "path": path, "expected_version": CFT_VERSION,
                    "revision": CFT_REVISION,
                    "binary_sha256": sha256_file(path) if os.path.isfile(path) else None,
                    "expected_binary_sha256": want_sha},
    }
    if os.path.isdir(wheels_dir):
        for name in sorted(os.listdir(wheels_dir)):
            if name.endswith(".whl"):
                ident["wheels"][name.split("-")[0]] = sha256_file(os.path.join(wheels_dir, name))
    return ident


def ldd_output(path):
    import subprocess
    res = subprocess.run(["ldd", path], capture_output=True, text=True, timeout=60)
    return res.stdout


def ldd_missing(path, output=ldd_output):
    return sum(1 for line in output(path).splitlines() if "not found" in line)


def library_resolved(path, library, output=ldd_output):
    return any(line.strip().startswith(library + " =>") and "not found" not in line
               for line in output(path).splitlines())


def prelaunch(kind="chrome", pydeps=PYDEPS, wheels_dir=WHEELS_DIR, node=NODE_DRIVER,
              ldd=None, identity=None):
    """Annex B2.3 pre-launch gate (R4). Everything here is read-only inspection: no Playwright
    driver (Node) and no browser process has started. Returns (identity, problems); any
    problem means the run is BLOCKED before anything is launched."""
    ldd = ldd or ldd_output
    ident = (identity or collect_identity)(kind, pydeps, wheels_dir)
    path = ident["browser"]["path"]
    ident["browser"]["ldd_missing"] = ldd_missing(path, ldd)
    ident["driver"] = {"path": node, "ldd_missing": ldd_missing(node, ldd),
                       "required_library": REQUIRED_LIBRARY,
                       "required_library_resolved": library_resolved(node, REQUIRED_LIBRARY, ldd)}
    problems = []
    if ident["browser"]["binary_sha256"] != ident["browser"]["expected_binary_sha256"]:
        problems.append("browser binary sha256")
    if ident["browser"]["ldd_missing"]:
        problems.append("browser binary libraries missing")
    if ident["driver"]["ldd_missing"]:
        problems.append("node driver libraries missing")
    if not ident["driver"]["required_library_resolved"]:
        problems.append(f"{REQUIRED_LIBRARY} not resolved")
    return ident, problems


def process_survey(pinned_path):
    """(processes whose executable is the pinned binary, processes running from the
    bundled /ms-playwright browsers) from /proc."""
    pinned = bundled = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            exe = os.readlink(f"/proc/{entry}/exe")
        except OSError:
            continue
        pinned += exe == pinned_path
        bundled += exe.startswith(BUNDLED_BROWSERS_PREFIX)
    return pinned, bundled


def check_identity(ident):
    """Raises RunnerError for any mismatch with annex B2.3 (the verifier recomputes it)."""
    py, br = ident["python"], ident["browser"]
    problems = []
    if py["playwright_version"] != PLAYWRIGHT_VERSION:
        problems.append("playwright distribution version")
    if py["playwright_dist_count"] != 1 or not py["playwright_under_pydeps"]:
        problems.append("playwright distribution location")
    if py["greenlet_version"] != GREENLET_VERSION:
        problems.append("greenlet version")
    if br["binary_sha256"] != br["expected_binary_sha256"]:
        problems.append("browser binary sha256")
    if br.get("running_version") not in (None, CFT_VERSION):
        problems.append("running browser version")
    if br.get("ms_playwright_processes"):
        problems.append("bundled browser executed")
    if problems:
        raise RunnerError("identity check failed: " + ", ".join(problems))


# --------------------------------------------------------------------------- control channel
def control_dir(out):
    path = os.path.join(out, ".control")
    os.makedirs(path, exist_ok=True)
    return path


def signal_ready(out, step):
    path = os.path.join(control_dir(out), f"ready-{step}")
    with open(path + ".tmp", "w") as fh:
        fh.write("ready\n")
    os.replace(path + ".tmp", path)


def wait_go(out, step, timeout=STEP_TIMEOUT, interval=1.0):
    """The operator's go-<step> JSON; raises RunnerError on timeout or a bad value."""
    path = os.path.join(control_dir(out), f"go-{step}")
    deadline = time.monotonic() + timeout
    while not os.path.exists(path):
        if time.monotonic() > deadline:
            raise RunnerError(f"timed out waiting for the operator: go-{step}")
        time.sleep(interval)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    value = data.get("app_timestamp")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RunnerError(f"go-{step}: app_timestamp must be a positive integer")
    return value


# --------------------------------------------------------------------------- recording
class Recorder:
    """Collects requests, console messages and CSP violations of every page attached."""

    def __init__(self):
        self.requests, self.console, self.csp = [], [], []
        self.phase = "page"
        self._cached_urls = set()
        self._request_urls = {}

    def reset(self):
        self.requests, self.console, self.csp = [], [], []
        self._cached_urls, self._request_urls = set(), {}

    def on_csp(self, payload):
        self.csp.append(json.loads(payload) if isinstance(payload, str) else payload)

    def attach(self, context, page):
        page.on("console", lambda m: self.console.append(
            {"type": m.type, "text": m.text, "url": m.location.get("url", ""), "phase": self.phase}))
        page.on("pageerror", lambda e: self.console.append(
            {"type": "pageerror", "text": str(e), "url": "", "phase": self.phase}))
        page.on("response", self._on_response)
        page.on("requestfailed", lambda r: self.requests.append(
            {"url": r.url, "method": r.method, "status": 0, "from_cache": False,
             "response_sha256": None, "resource_type": r.resource_type,
             "failure": r.failure or "failed"}))
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.on("Network.requestWillBeSent",
               lambda p: self._request_urls.__setitem__(p["requestId"], p["request"]["url"]))
        cdp.on("Network.responseReceived", self._on_cdp_response)
        cdp.on("Network.requestServedFromCache",
               lambda p: self._cached_urls.add(self._request_urls.get(p["requestId"], "")))

    def _on_cdp_response(self, p):
        resp = p["response"]
        if resp.get("fromDiskCache") or resp.get("fromPrefetchCache"):
            self._cached_urls.add(resp.get("url", ""))

    def _on_response(self, response):
        digest = None
        if "/client/custom/" in response.url and response.status < 400:
            try:
                digest = hashlib.sha256(response.body()).hexdigest()
            except Exception:  # the verifier treats a missing digest as a FAIL
                digest = None
        self.requests.append({"url": response.url, "method": response.request.method,
                              "status": response.status, "from_cache": False,
                              "response_sha256": digest,
                              "resource_type": response.request.resource_type})

    def finish(self):
        """Marks the requests the browser served from its cache, from the CDP events."""
        for r in self.requests:
            r["from_cache"] = r["url"] in self._cached_urls
        return self.requests


CSP_INIT_SCRIPT = """
document.addEventListener('securitypolicyviolation', function (e) {
  try { window.crmReportCsp(JSON.stringify({blocked_uri: e.blockedURI,
    violated_directive: e.violatedDirective, effective_directive: e.effectiveDirective,
    source_file: e.sourceFile || ''})); } catch (err) {}
});
"""
LOAD_CANARY_JS = """async (moduleId) => {
  try {
    const m = await Espo.loader.requirePromise(moduleId);
    return {ok: true, name: m.name, contract: m.contract, describe: m.describe()};
  } catch (e) { return {ok: false, error: String((e && e.message) || e)}; }
}"""
SIGNATURE_JS = """() => {
  const sel = '#main h1, #main h2, #main h3, #main .panel-title, #main th, .navbar-nav a';
  const heads = Array.from(document.querySelectorAll(sel)).map(e => e.textContent.trim()).filter(Boolean);
  return {heads: heads, rows: document.querySelectorAll('#main .list-row').length};
}"""
SCREEN_ROUTES = {"account-list": "#Account", "enquiry-list": "#Opportunity", "stream": "#Stream"}


def signature(page):
    sig = page.evaluate(SIGNATURE_JS)
    digest = hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()
    return {"signature": digest, "headings": len(sig["heads"]), "rows": sig["rows"]}


def login(page, base_url, username, password):
    page.goto(base_url)
    form = page.locator("#field-userName, input[data-name=username], input[name=username]").first
    if form.count():
        form.fill(username)
        page.locator("#field-password, input[data-name=password], input[name=password]").first.fill(password)
        page.locator("#btn-login, button[type=submit]").first.click()
    page.wait_for_selector(".navbar, #navbar", timeout=60000)


def capture_screens(page, base_url, out_dir, rec):
    """Screenshots and structural signatures of the regression screens (AC6b)."""
    shots = {}

    def shot(name):
        page.wait_for_load_state("networkidle")
        page.screenshot(path=os.path.join(out_dir, f"{name}.png"))
        shots[name] = signature(page)

    for name in ("account-list", "enquiry-list", "stream"):
        page.goto(base_url + "/" + SCREEN_ROUTES[name])
        page.wait_for_selector("#main", timeout=60000)
        shot(name)
        if name != "stream":
            page.locator("#main .list-row a.link, #main .list-row a").first.click()
            page.wait_for_selector("#main .record, #main .detail", timeout=60000)
            shot(name.replace("-list", "-detail"))
    return shots


def login_screen(browser, base_url, rec, out_dir):
    """The login page, in a throw-away context without a session."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.expose_function("crmReportCsp", rec.on_csp)
    ctx.add_init_script(CSP_INIT_SCRIPT)
    page = ctx.new_page()
    rec.attach(ctx, page)
    page.goto(base_url)
    page.wait_for_selector("#field-userName, input[data-name=username], input[name=username]",
                           timeout=60000)
    page.wait_for_load_state("networkidle")
    page.screenshot(path=os.path.join(out_dir, "login.png"))
    sig = signature(page)
    ctx.close()
    return sig


def judge(jid, rec, canary, a_prev, a_now):
    """The recorder-side assertions written to result.json (the verifier recomputes the
    verdicts from the raw files and does not read these)."""
    out = []
    reqs = canary_requests(rec.requests)
    errors = [c for c in rec.console if c["type"] in ("error", "pageerror") and c["phase"] != "probe"]
    out.append(assertion("no-csp-violation", "AC6b", 0, len(rec.csp), not rec.csp))
    out.append(assertion("no-console-error", "AC6b", 0, len(errors), not errors))
    if jid in CONTRACT:
        r = canary_r(reqs[0]["url"]) if reqs else None
        out.append(assertion("canary-contract", "AC6b", CONTRACT[jid],
                             canary.get("contract"), canary.get("ok") and canary.get("contract") == CONTRACT[jid]))
        out.append(assertion("canary-url-r", "AC6b", a_now, r, r == a_now))
        out.append(assertion("r-advanced", "AC6b", f"> {a_prev}", a_now, a_now > a_prev))
        fresh = bool(reqs) and not any(x["from_cache"] for x in reqs) and any(x["status"] == 200 for x in reqs)
        out.append(assertion("new-network-fetch", "AC6b", True, fresh, fresh))
    else:
        present = any(x["status"] == 200 for x in reqs)
        out.append(assertion("canary-absent", "AC6b", True, not present and not canary.get("ok"),
                             not present and not canary.get("ok")))
        out.append(assertion("r-advanced", "AC6b", f"> {a_prev}", a_now, a_now > a_prev))
    return out


# --------------------------------------------------------------------------- the run
def run_journeys(base_url, out, kind="chrome"):
    """The whole run: identity, compatibility probe, then J1-J5 with the operator's deploys."""
    username = os.environ.get("CRM_BROWSER_USERNAME")
    password = os.environ.get("CRM_BROWSER_PASSWORD")
    if not (username and password):
        raise RunnerError("CRM_BROWSER_USERNAME and CRM_BROWSER_PASSWORD are required")
    # R4: the binary hash and the library checks complete, and are recorded, BEFORE any
    # Playwright driver or browser process starts (sync_playwright() starts the Node driver).
    ident, problems = prelaunch(kind)
    write_json(os.path.join(out, "identity.json"), ident)
    if problems:
        raise RunnerError("pre-launch check failed, nothing was launched: " + ", ".join(problems))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=ident["browser"]["path"], headless=True,
                                    chromium_sandbox=False)
        try:
            pinned, bundled = process_survey(ident["browser"]["path"])
            ident["browser"].update({"running_version": browser.version,
                                     "process_exe_is_pinned": pinned > 0,
                                     "ms_playwright_processes": bundled})
            ident["compat_probe"] = compat_probe(browser, base_url, out)
            write_json(os.path.join(out, "identity.json"), ident)
            check_identity(ident)
            if not ident["compat_probe"]["passed"]:
                raise RunnerError("compatibility probe failed: the run is BLOCKED")
            signal_ready(out, "start")
            a = {"a0": wait_go(out, "start")}
            observed = {}
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            rec = Recorder()
            context.expose_function("crmReportCsp", rec.on_csp)
            context.add_init_script(CSP_INIT_SCRIPT)
            page = context.new_page()
            rec.attach(context, page)
            first = True
            baseline = {}
            for i, jid in enumerate(JOURNEYS, start=1):
                signal_ready(out, jid)
                a[f"a{i}"] = wait_go(out, jid)
                rec.reset()
                jdir = journey_dir(out, jid)
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
                rec.phase = "page"
                if first:
                    login(page, base_url, username, password)
                    first = False
                page.goto(base_url)
                page.wait_for_selector(".navbar, #navbar", timeout=60000)
                rec.phase = "probe"
                canary = page.evaluate(LOAD_CANARY_JS, CANARY_MODULE)
                rec.phase = "page"
                shots = {}
                if jid in ("J1", "J5"):
                    shots = capture_screens(page, base_url, jdir, rec)
                    shots["login"] = login_screen(browser, base_url, rec, jdir)
                    if jid == "J1":
                        baseline = shots
                context.tracing.stop(path=os.path.join(jdir, "trace.zip"))
                reqs = rec.finish()
                canary_reqs = canary_requests(reqs)
                if canary_reqs and canary_r(canary_reqs[0]["url"]) is not None:
                    observed[jid] = canary_r(canary_reqs[0]["url"])
                asserts = judge(jid, rec, canary, a[f"a{i - 1}"], a[f"a{i}"])
                for name in SCREENS if shots else ():
                    sig = shots.get(name, {})
                    ok = bool(sig.get("headings")) and (jid == "J1" or sig == baseline.get(name))
                    asserts.append(assertion(f"screen:{name}", "AC6b",
                                             "rendered" if jid == "J1" else "equal to J1 (D0)", sig, ok))
                write_journey_files(out, jid, reqs, rec.console, rec.csp, asserts,
                                    {"canary": canary, "contract_expected": CONTRACT.get(jid)})
                write_json(os.path.join(out, "timestamps.json"), {**a, "observed_r": observed})
                _, bundled = process_survey(ident["browser"]["path"])
                if bundled:
                    raise RunnerError("a bundled browser was executed")
            context.close()
        finally:
            browser.close()
    open(os.path.join(control_dir(out), "done"), "w").close()


def compat_probe(browser, base_url, out):
    """Annex B2.3: every Playwright feature the journeys use, against crm-app only."""
    steps = {}
    context = browser.new_context()
    seen = {"response": False, "console": False}
    try:
        context.expose_function("crmReportCsp", lambda payload: None)
        context.add_init_script(CSP_INIT_SCRIPT)
        steps["new_context"] = True
        page = context.new_page()
        steps["new_page"] = True
        page.on("response", lambda r: seen.__setitem__("response", True))
        page.on("console", lambda m: seen.__setitem__("console", True))
        page.on("pageerror", lambda e: None)
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")
        steps["cdp_session"] = True
        context.tracing.start(screenshots=True, snapshots=True)
        page.goto(base_url)
        page.wait_for_selector("#field-userName, input[data-name=username], .navbar", timeout=60000)
        steps["navigate_login_page"] = True
        steps["events"] = seen["response"]
        trace = os.path.join(control_dir(out), "compat-trace.zip")
        context.tracing.stop(path=trace)
        steps["tracing"] = os.path.getsize(trace) > 0
        shot = os.path.join(control_dir(out), "compat.png")
        page.screenshot(path=shot)
        steps["screenshot"] = os.path.getsize(shot) > 0
    except Exception as exc:  # recorded, not swallowed: the run is BLOCKED by the caller
        steps["error"] = type(exc).__name__
    finally:
        context.close()
    return {"steps": steps, "passed": bool(steps) and "error" not in steps and all(steps.values())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=os.environ.get("CRM_BROWSER_BASE_URL"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--browser-kind", choices=sorted(BROWSERS), default="chrome")
    args = ap.parse_args(argv)
    if not args.base_url:
        print("journeys: CRM_BROWSER_BASE_URL (or --base-url) is required", file=sys.stderr)
        return 2
    try:
        run_journeys(args.base_url, args.out, args.browser_kind)
    except RunnerError as exc:
        print(f"journeys: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
