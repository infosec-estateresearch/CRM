"""Input gate and read-only snapshot reader.

The snapshot argument is the ``<id>`` directory. ``manifest.json`` is located in exactly
one of two layouts (the CRM-002-W rule), anything else is refused:

* client-credentials: ``<id>/manifest.json`` exists and ``<id>`` has no ``run`` and no
  ``input`` entry; the snapshot root is ``<id>``;
* legacy mode: ``<id>/run/manifest.json`` exists, ``<id>/manifest.json`` does not, and the
  top level holds exactly the directories ``input`` and ``run``; the root is ``<id>/run``.
  ``input/`` (the waiver) is never read.

The reconciliation report comes from a separate, explicitly passed reconcile run directory
in its own layout: the ``<id>`` name ends in ``-reconcile``, its top level holds exactly the
real directory ``report``, and ``report/manifest.json`` is the sealed manifest (``mode``
``reconcile``, ``files`` keys relative to ``report/``, listing ``reconciliation.json``).
Its ``snapshot`` object must name the snapshot being loaded: ``t_start``, ``status``,
``contract_sha256`` and ``contract_version`` must equal the extract manifest's ``t_start``,
``status``, ``contract.sha256`` and ``contract.version``.

The importer refuses a snapshot unless:
* ``manifest.json`` parses and every file below the snapshot root is listed with a
  matching sha256, and nothing unlisted is present;
* ``mode`` is ``extract`` (a real extraction) or ``selftest`` (synthetic, written by
  ``crm-migrate selftest``), and the status is ``RECONCILED``, or
  ``RECONCILED_WITH_DRIFT`` with an accepted-drift Issue #9 comment URL;
* the contract version is exactly the int 4.

A snapshot is synthetic if and only if its manifest ``mode`` is ``selftest``.

Files are only ever opened for reading.
"""

import gzip
import hashlib
import json
import os
import re
import stat

from .errors import GateError

MANIFEST = "manifest.json"
LEGACY_TOP = ("input", "run")
RECONCILE_MODE = "reconcile"
RECONCILE_SUFFIX = "-reconcile"
RECONCILE_TOP = "report"
RECONCILIATION_REPORT = "reconciliation.json"
SUPPORTED_CONTRACT_VERSION = 4
MODES = ("extract", "selftest")
UNKNOWN = "unknown"
RECONCILED = "RECONCILED"
DRIFT = "RECONCILED_WITH_DRIFT"
ACCEPT_DRIFT_RE = re.compile(
    r"\Ahttps://github\.com/infosec-estateresearch/CRM/issues/9#issuecomment-[0-9]{1,20}\Z")
_REL_RE = re.compile(r"\A[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for d in dirnames:
            if os.path.islink(os.path.join(dirpath, d)):
                raise GateError("non_regular_file")
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel == MANIFEST:
                continue
            if not stat.S_ISREG(os.lstat(full).st_mode):
                raise GateError("non_regular_file")
            out[rel] = _sha256(full)
    return out


def _lexists(path):
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    return True


def _is_dir(path):
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def locate(id_dir):
    """The directory holding ``manifest.json`` for the ``<id>`` directory, or GateError."""
    try:
        st = os.lstat(id_dir)
    except OSError:
        raise GateError("snapshot_missing") from None
    if not stat.S_ISDIR(st.st_mode):
        raise GateError("snapshot_not_directory")
    try:
        top = set(os.listdir(id_dir))
    except OSError:
        raise GateError("snapshot_missing") from None
    if MANIFEST in top:
        if top & set(LEGACY_TOP):
            raise GateError("snapshot_layout_ambiguous")
        return id_dir
    run = os.path.join(id_dir, "run")
    if (top == set(LEGACY_TOP) and all(_is_dir(os.path.join(id_dir, d)) for d in LEGACY_TOP)
            and _lexists(os.path.join(run, MANIFEST))):
        return run
    raise GateError("snapshot_layout_unknown")


def _verify(root):
    try:
        st = os.lstat(root)
    except OSError:
        raise GateError("snapshot_missing") from None
    if not stat.S_ISDIR(st.st_mode):
        raise GateError("snapshot_not_directory")
    mpath = os.path.join(root, MANIFEST)
    try:
        if not stat.S_ISREG(os.lstat(mpath).st_mode):
            raise GateError("manifest_unreadable")
        with open(mpath, "rb") as fh:
            blob = fh.read()
        manifest = json.loads(blob.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise GateError("manifest_unreadable") from None
    if not isinstance(manifest, dict):
        raise GateError("manifest_unreadable")
    listed = manifest.get("files")
    if not isinstance(listed, dict) or not listed:
        raise GateError("manifest_files_missing")
    actual = _collect(root)
    for rel in sorted(set(listed) | set(actual)):
        if rel not in actual:
            raise GateError("missing_file")
        if rel not in listed:
            raise GateError("unlisted_file")
        entry = listed[rel]
        if not isinstance(entry, dict) or entry.get("sha256") != actual[rel]:
            raise GateError("checksum_mismatch")
    return manifest, hashlib.sha256(blob).hexdigest()


def verify(root):
    """Verify the manifest checksums of a manifest root. Returns the manifest or raises GateError."""
    return _verify(root)[0]


def contract_version(manifest):
    contract = manifest.get("contract")
    version = contract.get("version") if isinstance(contract, dict) else None
    if "contractVersion" in manifest:
        top = manifest["contractVersion"]
        if type(top) is not int or (version is not None and top != version):
            raise GateError("contract_version_unknown")
        version = top if version is None else version
    return version


def gate(manifest, accept_drift=None):
    """Apply the status and contract rules to a verified manifest."""
    if manifest.get("mode") not in MODES:
        raise GateError("not_a_snapshot")
    version = contract_version(manifest)
    if type(version) is not int or version != SUPPORTED_CONTRACT_VERSION:
        raise GateError("contract_version_unknown")
    status = manifest.get("status")
    if status == RECONCILED:
        if accept_drift is not None:
            raise GateError("accept_drift_not_applicable")
    elif status == DRIFT:
        if accept_drift is None:
            raise GateError("drift_not_accepted")
        if not isinstance(accept_drift, str) or not ACCEPT_DRIFT_RE.fullmatch(accept_drift):
            raise GateError("accept_drift_invalid")
    else:
        raise GateError("status_not_loadable")
    effective = (manifest.get("contract") or {}).get("effective")
    if not isinstance(effective, dict) or not effective:
        raise GateError("snapshot_without_data")
    return status


class Snapshot:
    """A verified, gated snapshot. Rows are read lazily, read-only."""

    def __init__(self, root, manifest, manifest_sha256=None, reconciliation=None):
        self.root = root
        self.manifest = manifest
        self.manifest_sha256 = manifest_sha256
        self._reconciliation = reconciliation
        self.effective = manifest["contract"]["effective"]
        self._cache = {}

    @property
    def synthetic(self):
        return manifest_is_synthetic(self.manifest)

    @property
    def as_of(self):
        """The snapshot's T_start (server time), used for legacyStale. Never the local clock."""
        value = self.manifest.get("t_start")
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", value):
            raise GateError("t_start_missing")
        return value[:10]

    @property
    def t_start(self):
        """T_start as EspoCRM 'YYYY-MM-DD HH:MM:SS' UTC (Meeting Held/Planned)."""
        from .mapping import espo_datetime
        self.as_of  # noqa: B018 - same presence check
        try:
            return espo_datetime(self.manifest["t_start"])
        except ValueError:
            raise GateError("t_start_missing") from None

    def has(self, obj):
        return obj in self.effective

    def fields(self, obj):
        return set(self.effective.get(obj, {}).get("fields", []))

    def soft_delete(self, obj):
        return bool(self.effective.get(obj, {}).get("softDelete"))

    def _read(self, rel):
        if not _REL_RE.fullmatch(rel) or rel not in self.manifest["files"]:
            return None
        rows = []
        try:
            with gzip.open(os.path.join(self.root, *rel.split("/")), "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            raise ValueError
                        rows.append(row)
        except (OSError, ValueError, EOFError):
            raise GateError("object_file_unreadable") from None
        return rows

    def rows(self, obj):
        """All extracted rows for ``obj`` (current and soft-deleted), sorted by Id."""
        if obj not in self._cache:
            if not self.has(obj):
                self._cache[obj] = []
            else:
                rows = self._read(f"objects/{obj}.jsonl.gz")
                if rows is None:
                    raise GateError("object_file_missing")
                self._cache[obj] = rows
        return self._cache[obj]

    def current(self, obj):
        return [r for r in self.rows(obj) if r.get("IsDeleted") is not True]

    def soft_deleted(self, obj):
        return [r for r in self.rows(obj) if r.get("IsDeleted") is True]

    def reconciliation(self):
        """The separate reconciliation report passed with ``--reconciliation``, else {}."""
        return self._reconciliation or {}

    @property
    def has_reconciliation(self):
        return self._reconciliation is not None

    def absent_unexplained(self, obj):
        """The count from the reconciliation, ``"unknown"`` without one, None if not listed."""
        if not self.has_reconciliation:
            return UNKNOWN
        doc = self.reconciliation()
        try:
            value = doc["objects"][obj]["deletion_classes"]["absent_since_previous_unexplained"]
        except (KeyError, TypeError):
            return None
        return value if type(value) is int else None


def manifest_is_synthetic(manifest):
    return manifest.get("mode") == "selftest"


def locate_reconcile(id_dir):
    """``<id>/report`` (the reconcile manifest root) for a ``*-reconcile`` run, or GateError."""
    try:
        st = os.lstat(id_dir)
    except OSError:
        raise GateError("reconciliation_snapshot_missing") from None
    if not stat.S_ISDIR(st.st_mode):
        raise GateError("reconciliation_snapshot_not_directory")
    try:
        top = set(os.listdir(id_dir))
    except OSError:
        raise GateError("reconciliation_snapshot_missing") from None
    report = os.path.join(id_dir, RECONCILE_TOP)
    if (os.path.basename(id_dir).endswith(RECONCILE_SUFFIX) and top == {RECONCILE_TOP}
            and _is_dir(report) and _lexists(os.path.join(report, MANIFEST))):
        return report
    raise GateError("reconciliation_layout_unknown")


def _same(a, b):
    return a is not None and type(a) is type(b) and a == b


def bind_reconciliation(doc, manifest):
    """Refuse a reconciliation that does not name this snapshot."""
    ref = doc.get("snapshot")
    contract = manifest.get("contract")
    contract = contract if isinstance(contract, dict) else {}
    if not isinstance(ref, dict) or not (
            _same(ref.get("t_start"), manifest.get("t_start"))
            and _same(ref.get("status"), manifest.get("status"))
            and _same(ref.get("contract_sha256"), contract.get("sha256"))
            and _same(ref.get("contract_version"), contract.get("version"))):
        raise GateError("reconciliation_snapshot_mismatch")


def open_reconciliation(path, manifest):
    """``report/reconciliation.json`` from a sealed reconcile run bound to ``manifest``."""
    root = locate_reconcile(os.path.abspath(path))
    try:
        rec_manifest = verify(root)
    except GateError as exc:
        raise GateError("reconciliation_" + exc.code) from None
    if rec_manifest.get("mode") != RECONCILE_MODE:
        raise GateError("reconciliation_not_a_reconcile_run")
    if RECONCILIATION_REPORT not in rec_manifest["files"]:
        raise GateError("reconciliation_report_missing")
    try:
        with open(os.path.join(root, RECONCILIATION_REPORT), "rb") as fh:
            doc = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise GateError("reconciliation_unreadable") from None
    if not isinstance(doc, dict):
        raise GateError("reconciliation_unreadable")
    bind_reconciliation(doc, manifest)
    return doc


def open_snapshot(id_dir, accept_drift=None, reconciliation=None):
    root = locate(os.path.abspath(id_dir))
    manifest, sha = _verify(root)
    gate(manifest, accept_drift)
    doc = open_reconciliation(reconciliation, manifest) if reconciliation is not None else None
    return Snapshot(root, manifest, sha, doc)
