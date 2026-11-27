"""Pure logic of the browser assurance run (CRM-BROWSER-001): data loading, the
step verdict, the target proof, the evidence manifest. Standard library only; no
Docker, no network. Used by browser_assurance.py (host) and
browser_assurance_runner.py (runner container)."""

import hashlib
import json
import os
import re

TESTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "browser")
RESULTS = ("performed", "not offered", "refused")
VERDICTS = ("passed", "failed")
MANIFEST = "manifest.json"
ID = r"[0-9a-f]{17}"  # an EspoCRM record id


class DataError(ValueError):
    pass


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_accounts(path=None):
    doc = _load(path or os.path.join(TESTS_DIR, "accounts.json"))
    kinds = [k["kind"] for k in doc["kinds"]]
    if len(set(kinds)) != len(kinds) or not kinds:
        raise DataError("account kinds must be unique and not empty")
    return doc["kinds"]


def load_expectations(kinds, path=None):
    """Validate the declared expectations: every step declares every kind."""
    doc = _load(path or os.path.join(TESTS_DIR, "expectations.json"))
    for jid, journey in doc["journeys"].items():
        ids = [s["id"] for s in journey["steps"]]
        if len(set(ids)) != len(ids):
            raise DataError(f"{jid}: duplicate step id")
        for step in journey["steps"]:
            if set(step["expect"]) != set(kinds):
                raise DataError(f"{jid}/{step['id']}: expectation must be declared for exactly {sorted(kinds)}")
            for kind, result in step["expect"].items():
                if result not in RESULTS:
                    raise DataError(f"{jid}/{step['id']}/{kind}: unknown result {result!r}")
            decls = step.get("declarations", {})
            if not isinstance(decls, dict) or not set(decls) <= set(kinds):
                raise DataError(f"{jid}/{step['id']}: declarations are a mapping from account kind to a list")
            for lst in decls.values():
                for decl in lst:
                    check_declaration(decl)
    return doc


def declarations_for(step, kind):
    """The declarations of one step for one account kind (none unless declared)."""
    return step.get("declarations", {}).get(kind, [])


def check_declaration(decl):
    """Only the two declarations of WO section 3.4 exist."""
    kind = decl.get("type")
    if kind == "server-refusal":
        need = {"type", "method", "status", "path_template", "console", "pageerrors"}
        if set(decl) != need or not isinstance(decl["status"], int) or decl["status"] < 400:
            raise DataError(f"server-refusal needs exactly {sorted(need)} and a status >= 400")
    elif kind == "client-access-denied":
        if set(decl) != {"type", "console"}:
            raise DataError("client-access-denied needs exactly type and console")
    else:
        raise DataError(f"unknown declaration type {kind!r}")
    if not all(isinstance(x, str) for x in decl["console"]):
        raise DataError("console lines must be strings")


# --- verdict (WO section 3.4) --------------------------------------------------------

def _path_matches(template, path):
    pattern = "^" + re.escape(template).replace(re.escape("{id}"), ID) + "$"
    return re.match(pattern, path) is not None


def undeclared_events(events, declarations):
    """Events not accounted for by a declaration, plus declared events that did not occur.
    An event: {"kind": "pageerror"|"console"|"response"|"requestfailed", ...}.
    console/pageerror carry "text"; response carries "method", "status", "path"."""
    rest = list(events)
    missing = []

    def take(predicate, what):
        for i, ev in enumerate(rest):
            if predicate(ev):
                del rest[i]
                return
        missing.append(what)

    for d in declarations:
        if d["type"] == "server-refusal":
            take(lambda e, d=d: e["kind"] == "response" and e["method"] == d["method"]
                 and e["status"] == d["status"] and _path_matches(d["path_template"], e["path"]),
                 f"{d['method']} {d['path_template']} -> {d['status']}")
            for text in d["pageerrors"]:
                take(lambda e, t=text: e["kind"] == "pageerror" and e["text"] == t, f"pageerror {text}")
        for text in d["console"]:
            take(lambda e, t=text: e["kind"] == "console" and e["text"] == t, f"console {text}")
    return rest, missing


def judge(expected, observed, readback_ok, events, declarations=()):
    """A step passes only if the observed result equals the declared one, the stored data
    read back by API agrees and nothing undeclared happened. Returns (verdict, reasons)."""
    reasons = []
    if expected not in RESULTS:
        reasons.append(f"no valid declared expectation ({expected!r})")
    if observed != expected:
        reasons.append(f"observed {observed!r}, declared {expected!r}")
    if readback_ok is not True:
        reasons.append("data read back by API does not agree")
    extra, missing = undeclared_events(events, declarations)
    for ev in extra:
        reasons.append(f"undeclared {ev['kind']}: {ev.get('text') or ev.get('method', '') + ' ' + ev.get('path', '') + ' ' + str(ev.get('status', ''))}")
    for what in missing:
        reasons.append(f"declared but absent: {what}")
    return ("failed" if reasons else "passed"), reasons


# --- target proof --------------------------------------------------------------------

def target_proof(observed_text, expected_sha256):
    """True only if the text served by the application is the run's own proof value."""
    if not isinstance(observed_text, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""):
        return False
    return hashlib.sha256(observed_text.encode("utf-8")).hexdigest() == expected_sha256


# --- evidence and manifest -----------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def evidence_files(out_dir):
    """Relative paths of every regular file under out_dir except the manifest."""
    found = []
    for root, _dirs, files in os.walk(out_dir):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), out_dir)
            if rel != MANIFEST:
                found.append(rel)
    return sorted(found)


def build_manifest(out_dir, commit, images, packages, browser, results, expectations, fault=None):
    """commit is a 40-hex string or None (uncommitted). results: {journey: {kind: {step: record}}}."""
    files = {rel: sha256_file(os.path.join(out_dir, rel)) for rel in evidence_files(out_dir)}
    steps = {}
    for jid, per_kind in results.items():
        for kind, per_step in per_kind.items():
            for sid, rec in per_step.items():
                steps[f"{jid}/{kind}/{sid}"] = {"verdict": rec["verdict"], "observed": rec["observed"],
                                                "expected": rec["expected"], "reasons": rec["reasons"]}
    return {
        "version": 1,
        "commit": commit if commit else "uncommitted",
        "images": images,
        "packages": packages,
        "browser": browser,
        "fault": fault,
        "journeys": sorted(results),
        "steps": steps,
        "files": files,
    }


def write_manifest(out_dir, manifest):
    with open(os.path.join(out_dir, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")


def package_hashes(lock_path):
    """{name==version: sha256} from the hash-locked requirements file."""
    with open(lock_path, encoding="utf-8") as fh:
        text = fh.read().replace("\\\n", " ")
    found = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+==[0-9.]+)\s+--hash=sha256:([0-9a-f]{64})\s*$", line.strip())
        if m:
            found[m.group(1)] = m.group(2)
    return found


# --- verify ----------------------------------------------------------------------------

def verify_evidence(out_dir, commit, expectations, kinds):
    """Problems found (empty list = accepted): the evidence is intact (no file removed, added,
    changed or substituted), complete for the full declared journey set and every account
    kind, every step passed as declared, no fault run, and made from commit `commit`."""
    problems = []
    try:
        manifest = _load(os.path.join(out_dir, MANIFEST))
    except (OSError, ValueError) as err:
        return [f"manifest unreadable: {type(err).__name__}"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        problems.append("the commit to check must be a full 40-character SHA")
    if manifest.get("commit") != commit:
        problems.append(f"evidence was made from {manifest.get('commit')!r}, not {commit!r}")
    if manifest.get("fault"):
        problems.append("evidence comes from a fault run")
    recorded = manifest.get("files", {})
    actual = set(evidence_files(out_dir))
    for rel in sorted(set(recorded) - actual):
        problems.append(f"removed: {rel}")
    for rel in sorted(actual - set(recorded)):
        problems.append(f"added: {rel}")
    for rel in sorted(set(recorded) & actual):
        if sha256_file(os.path.join(out_dir, rel)) != recorded[rel]:
            problems.append(f"changed: {rel}")
    if sorted(manifest.get("journeys", [])) != sorted(expectations["journeys"]):
        problems.append("the journey set is not the full declared set")
    steps = manifest.get("steps", {})
    wanted = set()
    for jid, journey in expectations["journeys"].items():
        for step in journey["steps"]:
            for kind in kinds:
                key = f"{jid}/{kind}/{step['id']}"
                wanted.add(key)
                rec = steps.get(key)
                if rec is None:
                    problems.append(f"missing step {key}")
                    continue
                if rec.get("verdict") != "passed":
                    problems.append(f"step not passed: {key}")
                if rec.get("expected") != step["expect"][kind] or rec.get("observed") != step["expect"][kind]:
                    problems.append(f"step {key} does not match the declared expectation")
                rel = key + ".json"
                try:
                    if _load(os.path.join(out_dir, rel)).get("verdict") != "passed":
                        problems.append(f"step record not passed: {rel}")
                except (OSError, ValueError):
                    problems.append(f"step record unreadable: {rel}")
    for key in sorted(set(steps) - wanted):
        problems.append(f"unexpected step {key}")
    return problems
