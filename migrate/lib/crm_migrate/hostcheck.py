"""Host guard decisions for ``scripts/migrate.sh``.

The ``check_*`` functions are pure: they take ``os.stat_result``-like values (anything with
``st_mode``, ``st_uid``, ``st_gid``), strings and mappings, and return a list of refusal
reasons (empty means allowed). They are unit-tested without root. ``main`` is the thin
I/O wrapper the script calls as ``crm-migrate.py hostcheck <check> ...``; it prints only
reasons and variable names, never a value.
"""

import hashlib
import json
import os
import re
import stat
import sys

from .manifest import MANIFEST, verify_tree

TARGET = "migrate"
RUNTIME = "/srv/CRM/runtime/migrate"
SNAPSHOTS = RUNTIME + "/snapshots"
ENV_FILE = RUNTIME + "/env"
RUN_UID = 64021
RUN_GID = 64021
RUN_MODES = ("selftest", "contract-check", "count", "extract", "reconcile")
RUN_ID_RE = re.compile(r"\A\d{8}T\d{6}Z-(?:" + "|".join(re.escape(m) for m in RUN_MODES) + r")\Z")
_NAME_RE = re.compile(r"\A[A-Z][A-Z0-9_]*\Z")
WAIVER_FILE = RUNTIME + "/waiver.json"

# CRM-002-S (temporary): the existing ELT env file holding the legacy credential. Its path is
# never committed: it is ``CRM_LEGACY_ENV_FILE`` in the root-only runtime env (ENV_FILE), empty
# by default, so the legacy commands refuse ("not configured") until the operator sets it.
LEGACY_PATH_NAME = "CRM_LEGACY_ENV_FILE"
LEGACY_USER = "NIF_SRC_SALESFORCE_USER"
LEGACY_PASS = "NIF_SRC_SALESFORCE_PASS"
LEGACY_NAMES = (LEGACY_USER, LEGACY_PASS)
MAX_LEGACY_ENV_BYTES = 1024 * 1024
_ASSIGN_RE = re.compile(r"\A(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\Z", re.S)
_UNQUOTED_RE = re.compile(r"\A[^\s'\"\\`$;&|<>()]+\Z")
_DQ_INNER_RE = re.compile(r"\A[^\"\\`$]+\Z")
_SQ_INNER_RE = re.compile(r"\A[^']+\Z")
_CTL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def _mode(st):
    return stat.S_IMODE(st.st_mode)


def check_target(target):
    return [] if target == TARGET else ["target must be 'migrate'"]


def check_runtime_path(path, expected=RUNTIME, realpath=os.path.realpath):
    """``path`` is the runtime path the caller was given; it must be ``expected`` and resolve
    to itself (no symlinked component)."""
    if path != expected:
        return [f"runtime must be {expected}"]
    if realpath(path) != expected:
        return [f"runtime {expected} must not resolve through a symlink"]
    return []


def check_root_private_dir(st, label):
    if st is None:
        return [f"{label} does not exist"]
    errors = []
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        errors.append(f"{label} must be a real directory")
    if st.st_uid != 0 or st.st_gid != 0:
        errors.append(f"{label} must be owned root:root")
    if _mode(st) != 0o700:
        errors.append(f"{label} must be mode 0700")
    return errors


def check_env_file_stat(st):
    if st is None:
        return ["env file does not exist (run: migrate.sh credentials)"]
    errors = []
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        errors.append("env file must be a regular file")
    if st.st_uid != 0 or st.st_gid != 0:
        errors.append("env file must be owned root:root")
    if _mode(st) != 0o600:
        errors.append("env file must be mode 0600")
    return errors


def parse_env_names(text):
    """Variable names from env.example. Refuses any line that carries a value."""
    names, errors = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not _NAME_RE.fullmatch(name) or (sep and value):
            errors.append("env.example must hold names only")
            continue
        names.append(name)
    if not names:
        errors.append("env.example holds no names")
    return names, errors


def parse_env_keys(text):
    """Keys of ``KEY=VALUE`` lines. Values are read and discarded, never returned."""
    keys = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, _ = line.partition("=")
        keys.append(key.strip() if sep else "<malformed>")
    return keys


def check_env_keys(keys, names):
    errors = []
    if "<malformed>" in keys:
        errors.append("env file has a malformed line")
    if len(keys) != len(set(keys)):
        errors.append("env file repeats a variable")
    missing = sorted(set(names) - set(keys))
    extra = sorted(set(keys) - set(names) - {"<malformed>"})
    if missing:
        errors.append("env file is missing: " + ",".join(missing))
    if extra:
        errors.append("env file has unexpected names: " + ",".join(n if _NAME_RE.fullmatch(n) else "<invalid>"
                                                                    for n in extra))
    return errors


def check_no_exported(environ, names):
    present = sorted(n for n in names if n in environ)
    return [f"refusing: {n} is exported in the calling shell" for n in present]


def parse_legacy_env(text):
    """Pure strict parser for the ELT env file: returns ``(creds or None, errors)``.

    Only ``NIF_SRC_SALESFORCE_USER`` and ``NIF_SRC_SALESFORCE_PASS`` are extracted; every
    other name is ignored, but every non-blank, non-comment line must be ``[export ]NAME=...``.
    The two values may be unquoted (no whitespace, quotes, backslash, backtick or any of
    ``;&|<>()$``), double-quoted (no ``"``, backslash, backtick or ``$`` inside) or
    single-quoted; a quoted value must be closed, with nothing after the closing quote. A
    duplicate, missing, empty or ambiguous value is refused. Errors carry line numbers and
    names only, never a value."""
    found, errors = {}, []
    if not isinstance(text, str):
        return None, ["legacy env file is not text"]
    for number, line in enumerate(text.split("\n"), 1):
        if line.endswith("\r"):
            line = line[:-1]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _ASSIGN_RE.fullmatch(line)
        if not m:
            errors.append(f"legacy env file line {number} is not NAME=value")
            continue
        name, raw = m.group(1), m.group(2)
        if name not in LEGACY_NAMES:
            continue                                  # unrelated names are ignored
        if name in found:
            errors.append(f"legacy env file repeats {name}")
            continue
        value = None
        if _CTL_RE.search(raw):
            value = None
        elif len(raw) >= 2 and raw[0] == raw[-1] == '"' and _DQ_INNER_RE.fullmatch(raw[1:-1]):
            value = raw[1:-1]
        elif len(raw) >= 2 and raw[0] == raw[-1] == "'" and _SQ_INNER_RE.fullmatch(raw[1:-1]):
            value = raw[1:-1]
        elif _UNQUOTED_RE.fullmatch(raw):
            value = raw
        if value is None:
            errors.append(f"legacy env file value of {name} is empty or ambiguous")
            found[name] = None
            continue
        found[name] = value
    for name in LEGACY_NAMES:
        if name not in found:
            errors.append(f"legacy env file is missing {name}")
    if errors:
        return None, errors
    return {"username": found[LEGACY_USER], "password": found[LEGACY_PASS]}, []


def legacy_credentials_json(creds):
    return json.dumps({"username": creds["username"], "password": creds["password"]}, ensure_ascii=True)


def fingerprint(raw, st):
    """sha256 of the content plus mtime (ns), size and inode: evidence the file was not modified."""
    return f"{hashlib.sha256(raw).hexdigest()} {st.st_mtime_ns} {st.st_size} {st.st_ino}"


def check_unchanged(before, after):
    return [] if before == after else ["legacy env file changed during the run (sha256 or mtime)"]


def check_legacy_env_stat(st, owner_uid=0):
    """Regular file, owned by root (``owner_uid``), not group- or world-writable."""
    if st is None:
        return ["legacy env file does not exist"]
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return ["legacy env file must be a regular file"]
    errors = []
    if st.st_uid != owner_uid:
        errors.append("legacy env file must be owned by root")
    if _mode(st) & 0o022:
        errors.append("legacy env file must not be group- or world-writable")
    return errors


def check_legacy_env_path(path, realpath=os.path.realpath):
    """``CRM_LEGACY_ENV_FILE``: set, absolute, and no symlinked component (realpath == path)."""
    if not isinstance(path, str) or not path:
        return [f"{LEGACY_PATH_NAME} is not configured (set it in {ENV_FILE})"]
    if re.search(r"[\x00-\x1f\x7f]", path) or not os.path.isabs(path):
        return [f"{LEGACY_PATH_NAME} must be an absolute path"]
    if realpath(path) != path:
        return [f"{LEGACY_PATH_NAME} must not resolve through a symlink or be non-canonical"]
    return []


def parse_legacy_path(text):
    """Value of ``CRM_LEGACY_ENV_FILE`` in the runtime env text: ``(path or "", errors)``.

    Only that one value is returned; every other value is discarded. Missing or empty means
    not configured."""
    found, errors = [], []
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep and key == LEGACY_PATH_NAME:
            found.append(value)
    if len(found) > 1:
        errors.append(f"runtime env repeats {LEGACY_PATH_NAME}")
    return (found[0] if found and not errors else ""), errors


def check_waiver_file_stat(st):
    if st is None:
        return []                                     # absent: the gate decides (write flags fail)
    errors = []
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        errors.append("waiver must be a regular file")
    if st.st_uid != 0 or st.st_gid != 0:
        errors.append("waiver must be owned root:root")
    if _mode(st) != 0o600:
        errors.append("waiver must be mode 0600")
    return errors


def check_uid_free(passwd_entry, group_entry, uid=RUN_UID, gid=RUN_GID):
    errors = []
    if passwd_entry.strip():
        errors.append(f"UID {uid} belongs to an existing host account")
    if group_entry.strip():
        errors.append(f"GID {gid} belongs to an existing host group")
    return errors


def check_run_id(run_id):
    return [] if isinstance(run_id, str) and RUN_ID_RE.fullmatch(run_id) else ["invalid run id"]


def check_run_dir_absent(st):
    return [] if st is None else ["run directory already exists"]


def check_run_dir_prepared(st, entries):
    errors = []
    if st is None or stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        return ["run directory must be a real directory"]
    if st.st_uid != RUN_UID or st.st_gid != RUN_GID:
        errors.append(f"run directory must be owned {RUN_UID}:{RUN_GID}")
    if _mode(st) != 0o700:
        errors.append("run directory must be mode 0700")
    if entries:
        errors.append("run directory must be empty")
    return errors


def check_sealed(entries):
    """``entries``: iterable of (relative path, lstat result), including the root as ''."""
    errors = set()
    seen_root = False
    for rel, st in entries:
        if rel == "":
            seen_root = True
        if st.st_uid != 0 or st.st_gid != 0:
            errors.add("unsealed: entry not owned root:root")
        if stat.S_ISDIR(st.st_mode):
            if _mode(st) != 0o700:
                errors.add("unsealed: directory not mode 0700")
        elif stat.S_ISREG(st.st_mode):
            if _mode(st) != 0o400:
                errors.add("unsealed: file not mode 0400")
        else:
            errors.add("unsealed: entry is neither a regular file nor a directory")
    if not seen_root:
        errors.add("unsealed: run directory missing")
    return sorted(errors)


def check_manifest_problems(problems):
    return [f"manifest verification failed: {p}" for p in sorted(set(problems))]


# ---------------------------------------------------------------- I/O wrapper

def _lstat(path):
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None


def _walk(root):
    st = _lstat(root)
    if st is None:
        return []
    out = [("", st)]
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            out.append((os.path.relpath(full, root), os.lstat(full)))
    return out


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_legacy(path, owner_uid=0, realpath=os.path.realpath):
    """Validate the path, open read-only, no symlink follow; return (raw, fingerprint, errors)."""
    errors = check_legacy_env_path(path, realpath)
    if errors:
        return None, None, errors
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        st = os.fstat(fd)
        errors = check_legacy_env_stat(st, owner_uid)
        if errors:
            return None, None, errors
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_LEGACY_ENV_BYTES:
                return None, None, ["legacy env file is too large"]
            chunks.append(chunk)
        raw = b"".join(chunks)
        return raw, fingerprint(raw, st), []
    finally:
        os.close(fd)


def configured_legacy_path(env_file=ENV_FILE):
    """``CRM_LEGACY_ENV_FILE`` from the root-only runtime env, after checking that file."""
    errors = check_env_file_stat(_lstat(env_file))
    if errors:
        return "", errors
    return parse_legacy_path(_read(env_file))


def legacy_main(check, path, out, err, *, owner_uid=0, realpath=os.path.realpath):
    """``legacy-fingerprint`` prints the fingerprint; ``legacy-credentials`` prints the JSON
    for the container's stdin. Errors go to ``err`` only, never into the pipe."""
    try:
        raw, fp, errors = _read_legacy(path, owner_uid, realpath)
        if not errors and check == "legacy-fingerprint":
            print(fp, file=out)
            return 0
        if not errors:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text, errors = None, ["legacy env file is not UTF-8"]
            if text is not None:
                creds, errors = parse_legacy_env(text)
                if not errors:
                    out.write(legacy_credentials_json(creds))
                    out.flush()
                    return 0
    except Exception as exc:  # class only
        errors = [f"legacy check failed ({type(exc).__name__})"]
    for e in errors:
        print(f"hostcheck: refused: {e}", file=err)
    return 1


def main(argv, environ=None, out=None):
    out = out or sys.stdout
    environ = os.environ if environ is None else environ
    if not argv:
        print("hostcheck: refused: no check given", file=out)
        return 2
    check, args = argv[0], argv[1:]
    errors = []
    try:
        if check == "target" and len(args) == 1:
            errors = check_target(args[0])
        elif check == "runtime-dirs" and len(args) <= 1:
            given = args[0] if args else RUNTIME
            errors = check_runtime_path(given)
            if not errors:
                errors += check_root_private_dir(_lstat(given), "runtime directory")
                errors += check_root_private_dir(_lstat(given + "/snapshots"), "snapshots directory")
        elif check in ("legacy-fingerprint", "legacy-credentials") and len(args) == 0:
            try:
                path, errors = configured_legacy_path()
            except Exception as exc:  # class only
                path, errors = "", [f"legacy check failed ({type(exc).__name__})"]
            if errors:
                for e in errors:
                    print(f"hostcheck: refused: {e}", file=sys.stderr)
                return 1
            return legacy_main(check, path, out, sys.stderr)
        elif check == "waiver-file" and len(args) == 0:
            errors = check_waiver_file_stat(_lstat(WAIVER_FILE))
        elif check == "env-names" and len(args) == 1:
            names, errors = parse_env_names(_read(args[0]))
            if not errors:
                for name in names:
                    print(name, file=out)
                return 0
        elif check == "env-clean" and len(args) == 1:
            names, errors = parse_env_names(_read(args[0]))
            errors += check_no_exported(environ, names)
        elif check == "env-file" and len(args) == 1:
            names, errors = parse_env_names(_read(args[0]))
            st = _lstat(ENV_FILE)
            errors += check_env_file_stat(st)
            if not errors:
                errors += check_env_keys(parse_env_keys(_read(ENV_FILE)), names)
        elif check == "uid-free" and len(args) == 2:
            errors = check_uid_free(args[0], args[1])
        elif check == "run-id" and len(args) == 1:
            errors = check_run_id(args[0])
        elif check == "run-dir-absent" and len(args) == 1:
            errors = check_run_dir_absent(_lstat(args[0]))
        elif check == "run-dir-prepared" and len(args) == 1:
            st = _lstat(args[0])
            entries = os.listdir(args[0]) if st is not None and stat.S_ISDIR(st.st_mode) else []
            errors = check_run_dir_prepared(st, entries)
        elif check == "sealed" and len(args) == 1:
            errors = check_sealed(_walk(args[0]))
        elif check == "verify-manifest" and len(args) == 1:
            if _lstat(os.path.join(args[0], MANIFEST)) is None:
                errors = ["manifest verification failed: no manifest"]
            else:
                _, problems = verify_tree(args[0])
                errors = check_manifest_problems(problems)
        else:
            errors = ["unknown check or wrong arguments"]
    except Exception as exc:  # report the class only
        errors = [f"check failed ({type(exc).__name__})"]
    for err in errors:
        print(f"hostcheck: refused: {err}", file=out)
    return 1 if errors else 0
