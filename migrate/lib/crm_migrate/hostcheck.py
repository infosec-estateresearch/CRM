"""Host guard decisions for ``scripts/migrate.sh``.

The ``check_*`` functions are pure: they take ``os.stat_result``-like values (anything with
``st_mode``, ``st_uid``, ``st_gid``), strings and mappings, and return a list of refusal
reasons (empty means allowed). They are unit-tested without root. ``main`` is the thin
I/O wrapper the script calls as ``crm-migrate.py hostcheck <check> ...``; it prints only
reasons and variable names, never a value.
"""

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
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-(?:" + "|".join(re.escape(m) for m in RUN_MODES) + r")$")
_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _mode(st):
    return stat.S_IMODE(st.st_mode)


def check_target(target):
    return [] if target == TARGET else ["target must be 'migrate'"]


def check_runtime_path(path, expected=RUNTIME):
    return [] if path == expected else [f"runtime must be {expected}"]


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
        if not _NAME_RE.match(name) or (sep and value):
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
        errors.append("env file has unexpected names: " + ",".join(n if _NAME_RE.match(n) else "<invalid>"
                                                                    for n in extra))
    return errors


def check_no_exported(environ, names):
    present = sorted(n for n in names if n in environ)
    return [f"refusing: {n} is exported in the calling shell" for n in present]


def check_uid_free(passwd_entry, group_entry, uid=RUN_UID, gid=RUN_GID):
    errors = []
    if passwd_entry.strip():
        errors.append(f"UID {uid} belongs to an existing host account")
    if group_entry.strip():
        errors.append(f"GID {gid} belongs to an existing host group")
    return errors


def check_run_id(run_id):
    return [] if isinstance(run_id, str) and RUN_ID_RE.match(run_id) else ["invalid run id"]


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
        elif check == "runtime-dirs" and len(args) == 0:
            errors = check_runtime_path(RUNTIME)
            errors += check_root_private_dir(_lstat(RUNTIME), "runtime directory")
            errors += check_root_private_dir(_lstat(SNAPSHOTS), "snapshots directory")
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
