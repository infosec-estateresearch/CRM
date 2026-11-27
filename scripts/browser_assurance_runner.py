#!/usr/bin/env python3
"""Runs INSIDE the runner container (never on the host): waits for the run's own stack,
provisions it with the repository's access configuration, proves the target, drives the
journeys with the bundled Chromium and writes the evidence. Configuration comes from the
file the host wrote (--config); a missing value fails loudly. Synthetic data only.

Platform facts relied on (reference: /srv/CRM/wo/CRM-BROWSER-001/reference/espocrm):
  client/res/templates/login.tpl (#field-userName, #field-password); routes #<Entity>/create,
  #<Entity>/view/<id>; client/src/views/record/detail.js (button[data-action=save],
  .detail-button-container); the REST API under /api/v1 (Espo-Authorization header)."""

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import browser_assurance_core as core  # noqa: E402
import crm_api  # noqa: E402
import provision_access  # noqa: E402
import browser_assurance_journeys as journeys  # noqa: E402

READY_TIMEOUT = 900
STEP_TIMEOUT_MS = 20000


def log(msg):
    print(f"[runner] {msg}", file=sys.stderr, flush=True)


def wait_ready(client):
    deadline = time.time() + READY_TIMEOUT
    while time.time() < deadline:
        try:
            client.call("GET", "App/user")
            return
        except Exception:  # not up yet: connection refused, 5xx, 401 before install finishes
            time.sleep(5)
    raise RuntimeError("the application did not become ready")


def provision(client, accounts):
    """The repository's own roles, teams and settings (provision_access functions against this
    run's stack), then one user per non-administrator account kind. Returns {kind: password}."""
    config = provision_access.load_config()
    config["settings"] = provision_access.load_settings()
    provision_access.provision(client, config, "/tmp/er-import-key")
    team_ids = provision_access.name_ids(client, "Team", sorted({t for a in accounts for t in a["teams"]}))
    role_ids = provision_access.name_ids(client, "Role", sorted({r for a in accounts for r in a["roles"]}))
    passwords = {}
    for acct in accounts:
        if not acct["roles"]:
            continue
        pw = secrets.token_urlsafe(24)
        client.create("User", {"userName": acct["userName"], "firstName": "Browser", "lastName": acct["kind"],
                               "password": pw, "passwordConfirm": pw, "type": "regular",
                               "rolesIds": [role_ids[r] for r in acct["roles"]],
                               "teamsIds": [team_ids[t] for t in acct["teams"]]})
        passwords[acct["kind"]] = pw
    return passwords


class Recorder:
    """Collects script errors, console errors, failed responses and requests of one step."""

    def __init__(self, page, base):
        self.events, self.requests, self.base = [], [], base
        page.on("console", lambda m: self.events.append({"kind": "console", "text": m.text}) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.events.append({"kind": "pageerror", "text": str(e)}))
        page.on("requestfailed", lambda r: self.events.append(
            {"kind": "requestfailed", "text": f"{r.method} {urllib.parse.urlparse(r.url).path}"}))
        page.on("response", self._response)

    def _response(self, r):
        path = urllib.parse.urlparse(r.url).path
        path = path[len("/api/v1/"):] if path.startswith("/api/v1/") else path
        self.requests.append({"method": r.request.method, "path": path, "status": r.status})
        if r.status >= 400:
            self.events.append({"kind": "response", "method": r.request.method, "status": r.status, "path": path})

    def reset(self):
        self.events.clear()
        self.requests.clear()


def sign_in(page, base, user, password):
    page.goto(base + "/#", wait_until="load")
    page.fill("#field-userName", user)
    page.fill("#field-password", password)
    page.press("#field-password", "Enter")
    page.wait_for_selector("#field-userName", state="detached", timeout=60000)


JOURNEY_STEPS = journeys.JOURNEY_STEPS


def read_back(admin, entity, rid, stored):
    """The stored data, read by API as administrator, agrees with what the step declared
    (a declared list must be contained in the stored list)."""
    if stored is None:
        return True  # nothing was created or changed: the step declares no stored data
    if not rid:
        return False
    rec = admin.call("GET", f"{entity}/{rid}")
    for k, v in stored.items():
        got = rec.get(k)
        if isinstance(v, list):
            if not isinstance(got, list) or not set(v) <= set(got):
                return False
        elif got != v:
            return False
    return True


def early_proof(base, url, sha256):
    """The target proof, before any credential is sent: only this run's own stack serves the value."""
    deadline = time.time() + READY_TIMEOUT
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + url, timeout=10) as resp:
                return core.target_proof(resp.read().decode("utf-8", "replace"), sha256)
        except (urllib.error.URLError, OSError):
            time.sleep(5)
    return False


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")


def run_journeys(cfg, out, accounts, expectations, passwords, admin):
    from playwright.sync_api import sync_playwright
    base = cfg["base_url"]
    results = {j: {} for j in cfg["journeys"]}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        version = browser.version
        ctx = browser.new_context()
        text = ctx.new_page().goto(base + cfg["proof_url"]).text()
        proof_ok = core.target_proof(text, cfg["proof_sha256"])
        ctx.close()
        write_json(os.path.join(out, "target-proof.json"), {"proof_sha256": cfg["proof_sha256"], "matched": proof_ok})
        if not proof_ok:
            raise RuntimeError("target proof failed: the application reached is not this run's stack")
        tag = secrets.token_hex(3)
        for acct in accounts:
            kind = acct["kind"]
            password = cfg["admin_password"] if not acct["roles"] else passwords[kind]
            bctx = browser.new_context()
            page = bctx.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            rec = Recorder(page, base)
            c = journeys.Ctx(page, base, tag, kind, acct["userName"], admin)
            try:
                sign_in(page, base, acct["userName"], password)
                login_error = None
            except Exception as err:
                login_error = f"sign-in failed: {type(err).__name__}"
            for jid in cfg["journeys"]:
                results[jid][kind] = {}
                for step in expectations["journeys"][jid]["steps"]:
                    sid = step["id"]
                    try:  # every step starts from a blank page: no earlier screen, form or error carries over
                        page.goto("about:blank")
                    except Exception:
                        pass
                    rec.reset()
                    observed, readback, error = "error", False, login_error
                    entity = rid = None
                    if error is None:
                        try:
                            observed, entity, rid, stored = JOURNEY_STEPS[jid][sid](c)
                            readback = read_back(admin, entity, rid, stored)
                        except Exception as err:
                            error = f"{type(err).__name__}: {str(err)[:200]}"
                    shot = f"{jid}/{kind}/{sid}.png"
                    try:
                        os.makedirs(os.path.join(out, jid, kind), exist_ok=True)
                        page.screenshot(path=os.path.join(out, shot))
                    except Exception:
                        shot = None
                    verdict, reasons = core.judge(step["expect"][kind], observed, readback, rec.events,
                                                  core.declarations_for(step, kind))
                    if error:
                        verdict, reasons = "failed", reasons + [error]
                    results[jid][kind][sid] = {"verdict": verdict, "observed": observed,
                                               "expected": step["expect"][kind], "reasons": reasons}
                    write_json(os.path.join(out, jid, kind, f"{sid}.json"),
                               {"step": sid, "events": rec.events, "requests": rec.requests,
                                "screenshot": shot, "verdict": verdict, "reasons": reasons})
                    log(f"{jid}/{kind}/{sid}: {verdict}")
            bctx.close()
        browser.close()
    return results, version


def apply_fault(fault, expectations, accounts, journey_ids):
    """wrong-expectation: one declared expectation is altered for this run only."""
    if fault == "wrong-expectation":
        step = expectations["journeys"][journey_ids[0]]["steps"][0]
        kind = accounts[0]["kind"]
        step["expect"][kind] = "refused" if step["expect"][kind] != "refused" else "performed"
        step["declarations"] = {}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for key in ("base_url", "admin_user", "admin_password", "proof_url", "proof_sha256", "journeys"):
        if not cfg.get(key):
            print(f"runner: missing required configuration {key}", file=sys.stderr)
            return 2
    accounts = core.load_accounts()
    expectations = core.load_expectations([a["kind"] for a in accounts])
    apply_fault(cfg.get("fault"), expectations, accounts, cfg["journeys"])
    admin = crm_api.EspoClient(cfg["base_url"], cfg["admin_user"], cfg["admin_password"])
    results, browser, failure = {}, None, None
    try:
        if not early_proof(cfg["base_url"], cfg["proof_url"], cfg["proof_sha256"]):
            raise RuntimeError("target proof failed before sign-in: not this run's stack")
        wait_ready(admin)
        passwords = provision(admin, accounts)
        results, browser = run_journeys(cfg, args.out, accounts, expectations, passwords, admin)
    except Exception as err:
        failure = f"{type(err).__name__}: {str(err)[:300]}"
        log(f"FAILED: {failure}")
    write_json(os.path.join(args.out, "results.json"), {"browser": browser, "results": results, "error": failure})
    bad = [f"{j}/{k}/{s}" for j, pk in results.items() for k, ps in pk.items() for s, r in ps.items() if r["verdict"] != "passed"]
    expected_count = sum(len(expectations["journeys"][j]["steps"]) for j in cfg["journeys"]) * len(accounts)
    done = sum(len(ps) for pk in results.values() for ps in pk.values())
    if failure or bad or done != expected_count:
        log(f"failed steps: {bad or 'incomplete run'}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
