"""Output directory and manifest handling.

* The output directory must be new or empty, and is never overwritten.
* Every file is created with ``O_CREAT | O_EXCL | O_NOFOLLOW`` and mode ``0600``
  (the CLI also sets umask ``077``).
* gzip output is deterministic (``mtime=0``, no file name), so identical content gives
  identical checksums.
* ``manifest.json`` is written last and lists the sha256 of every other file.
"""

import gzip
import hashlib
import io
import json
import os
import re
import stat

from .errors import OutputError, SnapshotError

MANIFEST = "manifest.json"
_REL_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")


def _check_rel(rel):
    if not isinstance(rel, str) or not _REL_RE.match(rel) or any(p in (".", "..") for p in rel.split("/")):
        raise OutputError("output_path", detail="invalid relative path")
    return rel


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dumps(doc):
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class OutputDir:
    def __init__(self, path):
        path = os.path.abspath(path)
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            try:
                os.mkdir(path, 0o700)
            except OSError:
                raise OutputError("output_dir", detail="cannot create output directory") from None
        else:
            if not stat.S_ISDIR(st.st_mode):
                raise OutputError("output_dir", detail="output path is not a directory")
            if os.listdir(path):
                raise OutputError("output_dir_not_empty", detail="output directory must be new and empty")
        self.path = path
        self.files = {}
        self._finalized = False

    def _open(self, rel):
        rel = _check_rel(rel)
        if self._finalized or rel == MANIFEST or rel in self.files:
            raise OutputError("output_exists", detail="file already written")
        full = os.path.join(self.path, *rel.split("/"))
        parent = os.path.dirname(full)
        cur = self.path
        for part in os.path.relpath(parent, self.path).split(os.sep):
            if part in ("", "."):
                continue
            cur = os.path.join(cur, part)
            try:
                os.mkdir(cur, 0o700)
            except FileExistsError:
                st = os.lstat(cur)
                if not stat.S_ISDIR(st.st_mode):
                    raise OutputError("output_path", detail="parent is not a directory") from None
        try:
            fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            raise OutputError("output_exists", detail="refusing to overwrite") from None
        return rel, full, os.fdopen(fd, "wb")

    def _record(self, rel, full):
        self.files[rel] = {"sha256": sha256_file(full), "bytes": os.path.getsize(full)}

    def write_bytes(self, rel, data):
        rel, full, fh = self._open(rel)
        with fh:
            fh.write(data)
        self._record(rel, full)

    def write_json(self, rel, doc):
        self.write_bytes(rel, dumps(doc).encode("utf-8"))

    def write_text(self, rel, text):
        self.write_bytes(rel, text.encode("utf-8"))

    def write_jsonl_gz(self, rel, rows):
        rel, full, fh = self._open(rel)
        count = 0
        with fh:
            with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
                buf = io.TextIOWrapper(gz, encoding="utf-8", newline="\n")
                for row in rows:
                    buf.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    count += 1
                buf.flush()
                buf.detach()
        self._record(rel, full)
        return count

    def subdir(self, rel):
        """Create an empty child directory and return a new OutputDir for it."""
        rel = _check_rel(rel)
        if self._finalized:
            raise OutputError("output_exists", detail="already finalized")
        return OutputDir(os.path.join(self.path, *rel.split("/")))

    def finalize(self, doc):
        doc = dict(doc)
        doc["files"] = collect_files(self.path)
        full = os.path.join(self.path, MANIFEST)
        try:
            fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            raise OutputError("output_exists", detail="manifest exists") from None
        with os.fdopen(fd, "wb") as fh:
            fh.write(dumps(doc).encode("utf-8"))
        self._finalized = True
        return doc


def collect_files(root):
    """sha256 of every regular file below ``root`` except the top-level manifest."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel == MANIFEST:
                continue
            st = os.lstat(full)
            if not stat.S_ISREG(st.st_mode):
                raise OutputError("output_path", detail="non-regular file in output")
            out[rel] = {"sha256": sha256_file(full), "bytes": st.st_size}
    return out


def compare_manifest_files(listed, actual):
    """Pure comparison of manifest ``files`` against the files found. Returns problem codes."""
    problems = []
    if not isinstance(listed, dict):
        return ["manifest_files_missing"]
    for rel in sorted(set(listed) | set(actual)):
        if rel not in actual:
            problems.append("missing_file")
        elif rel not in listed:
            problems.append("unlisted_file")
        else:
            entry = listed[rel]
            if not isinstance(entry, dict) or entry.get("sha256") != actual[rel]["sha256"]:
                problems.append("checksum_mismatch")
    return problems


def read_manifest(root):
    full = os.path.join(root, MANIFEST)
    try:
        with open(full, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise SnapshotError("manifest_unreadable") from None


def verify_tree(root):
    """Re-verify every checksum below ``root``. Returns (manifest, problems)."""
    manifest = read_manifest(root)
    try:
        actual = collect_files(root)
    except OutputError:
        return manifest, ["non_regular_file"]
    problems = compare_manifest_files(manifest.get("files"), actual)
    return manifest, problems


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)
