#!/usr/bin/env python3
"""Release bundle (CRM-007, PBI-016): build and verify, standard library only.

    python3 scripts/release.py build <commit> [--repo DIR] [--out DIR] [--branch main]
    python3 scripts/release.py verify <bundle> [--sha256 HEX]
    python3 scripts/release.py verify-tree <dir> <bundle> --sha256 HEX

build: the commit must be accepted, i.e. reachable from the release branch
(main). The bundle crm-release-<shortsha>.tar.gz holds `git archive` of the
commit under crm-release-<shortsha>/, minus the delivery records (.forge/,
CRM-D017; recorded as `excluded`), plus RELEASE.json (the commit, the image
digests from the commit's security/EXTERNAL_CODE_REGISTER.yaml, the sha256 of
every file, and the latest commit of each CRM-002..CRM-006 delivery record).
It is byte-for-byte reproducible: members are sorted, owned by 0:0, dated with
the commit time, and gzip carries no name or timestamp.

verify: refuses (exit 1) a bundle whose member set, file digests, image
digests or name do not match RELEASE.json, that holds anything but regular
files and directories under its one top directory, or (with --sha256) whose
own digest differs. Without --sha256 the bundle is not anchored: RELEASE.json
sits inside it, so anyone can change a file and re-hash it. verify then warns;
deploy_release.sh always requires --sha256.

verify-tree: refuses (exit 1) unless <dir> holds exactly the files of the
anchored bundle (every file of RELEASE.json plus RELEASE.json itself, byte for
byte), only regular files and the directories that hold them, nothing else,
and none of them setuid, setgid, sticky or writable by group or others (as
verify refuses for tar members).
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import zlib

FORMAT = 1
DELIVERY_RECORDS = ("CRM-002", "CRM-003", "CRM-004", "CRM-005", "CRM-006")
REGISTER = "security/EXTERNAL_CODE_REGISTER.yaml"
EXCLUDED = (".forge/",)  # CRM-D017: delivery records are not part of a release
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMPOSE_FILES = ("deploy/compose.json", "deploy/beta/compose.json",
                 "deploy/beta/restoretest/compose.json")


class ReleaseError(Exception):
    pass


def git(repo, *args, binary=False):
    res = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if res.returncode != 0:
        raise ReleaseError(f"git {args[0]} failed: {res.stderr.decode(errors='replace').strip()}")
    return res.stdout if binary else res.stdout.decode().strip()


def register_digests(text):
    """{name: digest} from the register's candidate list."""
    out, current = {}, None
    for line in text.splitlines():
        line = line.split(" #", 1)[0].rstrip()
        m = re.match(r"^\s*-\s+name:\s*(\S+)\s*$", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r'^\s+digest:\s*"?(sha256:[0-9a-f]{64})"?\s*$', line)
        if m and current:
            out[current] = m.group(1)
    return out


def compose_digests(files):
    """Every sha256 digest an image reference in the compose files pins."""
    found = set()
    for text in files:
        for svc in (json.loads(text).get("services") or {}).values():
            m = re.search(r"@(sha256:[0-9a-f]{64})$", str(svc.get("image", "")))
            if not m:
                raise ReleaseError(f"image not pinned by digest: {svc.get('image')!r}")
            found.add(m.group(1))
    return found


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _member(name, data=None, mtime=0, mode=0o644):
    info = tarfile.TarInfo(name)
    info.mtime, info.uid, info.gid, info.uname, info.gname = mtime, 0, 0, "root", "root"
    if data is None:
        info.type, info.mode = tarfile.DIRTYPE, 0o755
    else:
        info.size, info.mode = len(data), mode
    return info


def build(repo, commit, out_dir, branch="main"):
    full = git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
    try:
        git(repo, "merge-base", "--is-ancestor", full, branch)
    except ReleaseError:
        raise ReleaseError(f"commit {full[:12]} is not accepted (not reachable from {branch})")
    short = full[:12]
    top = f"crm-release-{short}"
    mtime = int(git(repo, "show", "-s", "--format=%ct", full))
    archive = tarfile.open(fileobj=io.BytesIO(git(repo, "archive", "--format=tar", full,
                                                  binary=True)))
    files = {}
    for m in archive.getmembers():
        if m.isdir() or m.type == tarfile.XGLTYPE or m.name == "pax_global_header":
            continue
        if m.name.startswith(EXCLUDED):
            continue
        if not m.isfile():
            raise ReleaseError(f"refusing to bundle a non-regular file: {m.name}")
        files[m.name] = (archive.extractfile(m).read(), 0o755 if m.mode & 0o111 else 0o644)
    if REGISTER not in files:
        raise ReleaseError(f"{REGISTER} missing at {short}")
    images = register_digests(files[REGISTER][0].decode())
    records = {}
    for wo in DELIVERY_RECORDS:
        # CRM-006 was continued as CRM-006R/CRM-006S: any .forge/<wo>*/REPORT.md counts.
        log = git(repo, "log", "-1", "--format=%H", full, "--", f":(glob).forge/{wo}*/REPORT.md")
        records[wo] = log or None
    manifest = {"format": FORMAT, "commit": full, "short": short, "images": images,
                "delivery_records": records, "excluded": list(EXCLUDED),
                "files": {name: sha256(data) for name, (data, _) in sorted(files.items())}}
    release_json = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    dirs = {top}
    for name in files:
        parts = name.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add(top + "/" + "/".join(parts[:i]))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        entries = [(d, None, 0) for d in dirs]
        entries += [(f"{top}/{n}", d, mode) for n, (d, mode) in files.items()]
        entries.append((f"{top}/RELEASE.json", release_json, 0o644))
        for name, data, mode in sorted(entries, key=lambda e: e[0]):
            info = _member(name, data, mtime, mode)
            tar.addfile(info, None if data is None else io.BytesIO(data))
    path = os.path.join(out_dir, f"{top}.tar.gz")
    with open(path, "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0, compresslevel=9) as gz:
            gz.write(raw.getvalue())
    return path, manifest


def verify(path, expected_sha256=None):
    """The manifest of a bundle that passes every check; raises ReleaseError."""
    return _verify(path, expected_sha256)[0]


def _verify(path, expected_sha256):
    """(manifest, raw RELEASE.json bytes) of a bundle that passes every check."""
    with open(path, "rb") as fh:
        blob = fh.read()
    if expected_sha256 is not None:
        if not SHA256_RE.fullmatch(expected_sha256):
            raise ReleaseError("--sha256 must be exactly 64 lower-case hex digits")
        if sha256(blob) != expected_sha256:
            raise ReleaseError("bundle sha256 does not match the expected digest")
    m = re.fullmatch(r"crm-release-([0-9a-f]{12})\.tar\.gz", os.path.basename(path))
    if not m:
        raise ReleaseError("bundle name is not crm-release-<12 hex>.tar.gz")
    top = f"crm-release-{m.group(1)}"
    try:
        inflate = zlib.decompressobj(wbits=31)  # exactly one gzip member, nothing after it
        raw = inflate.decompress(blob) + inflate.flush()
        if not inflate.eof or inflate.unused_data:
            raise ReleaseError("bundle is not exactly one complete gzip stream")
    except zlib.error:
        raise ReleaseError("bundle is not valid gzip")
    try:
        tar = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
        members = tar.getmembers()
    except (tarfile.TarError, OSError, EOFError) as err:
        raise ReleaseError(f"bundle is not a readable tar.gz: {type(err).__name__}")
    files = {}
    for mem in members:
        name = mem.name
        if name.startswith("/") or ".." in name.split("/") or not (
                name == top or name.startswith(top + "/")):
            raise ReleaseError(f"member outside {top}/: {name}")
        if mem.isdir():
            continue
        if not mem.isfile():
            raise ReleaseError(f"member is not a regular file or directory: {name}")
        if mem.mode & 0o7022:
            raise ReleaseError(f"member has setuid/setgid/sticky or writable-by-others mode: {name}")
        rel = name[len(top) + 1:]
        if rel in files:
            raise ReleaseError(f"duplicate member: {name}")
        files[rel] = tar.extractfile(mem).read()
    if "RELEASE.json" not in files:
        raise ReleaseError("RELEASE.json missing")
    raw_json = files.pop("RELEASE.json")
    try:
        manifest = json.loads(raw_json)
    except ValueError:
        raise ReleaseError("RELEASE.json is not valid JSON")
    if manifest.get("format") != FORMAT or manifest.get("short") != m.group(1) \
            or not str(manifest.get("commit", "")).startswith(m.group(1)):
        raise ReleaseError("RELEASE.json does not describe this bundle (format, commit or name)")
    if manifest.get("excluded") != list(EXCLUDED):
        raise ReleaseError(f"RELEASE.json must record excluded: {list(EXCLUDED)}")
    listed = manifest.get("files") or {}
    if any(n.startswith(EXCLUDED) for n in listed):
        raise ReleaseError("bundle holds an excluded path (.forge/)")
    if set(listed) != set(files):
        extra, missing = sorted(set(files) - set(listed)), sorted(set(listed) - set(files))
        raise ReleaseError(f"member set differs from RELEASE.json (extra {extra[:5]}, "
                           f"missing {missing[:5]})")
    bad = sorted(n for n, data in files.items() if sha256(data) != listed[n])
    if bad:
        raise ReleaseError(f"file digest mismatch: {bad[:5]}")
    if register_digests(files.get(REGISTER, b"").decode()) != manifest.get("images"):
        raise ReleaseError("RELEASE.json image digests differ from the bundled register")
    pinned = compose_digests(files[c].decode() for c in COMPOSE_FILES if c in files)
    if not pinned <= set(manifest["images"].values()):
        raise ReleaseError("a compose image digest is not in the register")
    return manifest, raw_json


def verify_tree(directory, bundle, expected_sha256):
    """Raises ReleaseError unless directory holds exactly the anchored bundle's files."""
    if expected_sha256 is None:
        raise ReleaseError("verify-tree needs --sha256")
    manifest, raw_json = _verify(bundle, expected_sha256)
    want = dict(manifest["files"])
    want["RELEASE.json"] = sha256(raw_json)
    want_dirs = {""}
    for name in want:
        parts = name.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            want_dirs.add("/".join(parts[:i]))
    if os.path.islink(directory) or not os.path.isdir(directory):
        raise ReleaseError(f"not a real directory: {directory}")
    found, problems = {}, []
    for root, dirs, files in os.walk(directory):
        rel_root = os.path.relpath(root, directory)
        rel_root = "" if rel_root == "." else rel_root
        if rel_root not in want_dirs:
            problems.append(f"extra directory {rel_root}")
        for name in dirs + files:
            rel = f"{rel_root}/{name}" if rel_root else name
            path = os.path.join(root, name)
            if os.path.islink(path) or not (os.path.isdir(path) or os.path.isfile(path)):
                problems.append(f"not a regular file or directory: {rel}")
            elif os.lstat(path).st_mode & 0o7022:  # as _verify for tar members
                problems.append(f"setuid/setgid/sticky or writable-by-others mode: {rel}")
            elif os.path.isfile(path):
                with open(path, "rb") as fh:
                    found[rel] = sha256(fh.read())
    extra = sorted(set(found) - set(want))
    missing = sorted(set(want) - set(found))
    changed = sorted(n for n in set(found) & set(want) if found[n] != want[n])
    if extra:
        problems.append(f"extra files {extra[:5]}")
    if missing:
        problems.append(f"missing files {missing[:5]}")
    if changed:
        problems.append(f"changed files {changed[:5]}")
    if problems:
        raise ReleaseError("unpacked tree differs from RELEASE.json: " + "; ".join(problems[:5]))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(prog="release.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("commit")
    b.add_argument("--repo", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    b.add_argument("--out", default=".")
    b.add_argument("--branch", default="main")
    v = sub.add_parser("verify")
    v.add_argument("bundle")
    v.add_argument("--sha256")
    t = sub.add_parser("verify-tree")
    t.add_argument("directory")
    t.add_argument("bundle")
    t.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "build":
            path, manifest = build(args.repo, args.commit, args.out, args.branch)
            with open(path, "rb") as fh:
                print(f"{path} sha256 {sha256(fh.read())} ({len(manifest['files'])} files)")
        elif args.cmd == "verify-tree":
            manifest = verify_tree(args.directory, args.bundle, args.sha256)
            print(f"tree verified: commit {manifest['commit']} ({len(manifest['files'])} files)")
        else:
            manifest = verify(args.bundle, args.sha256)
            if args.sha256 is None:
                print("release.py: WARNING: no --sha256 given, so this bundle is NOT ANCHORED: "
                      "RELEASE.json sits inside it and a consistently re-hashed bundle also "
                      "passes. Deploy only with --sha256 from the release record.",
                      file=sys.stderr)
            print(f"bundle verified: commit {manifest['commit']} "
                  f"({len(manifest['files'])} files)")
    except (ReleaseError, OSError) as err:
        print(f"release.py: refused: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
