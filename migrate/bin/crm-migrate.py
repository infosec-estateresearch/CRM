"""crm-migrate entry point (CRM-002).

Run as ``python -I -B /opt/crm-migrate/bin/crm-migrate.py <mode> ...``.

``-I`` ignores PYTHON* variables and keeps the script directory and the working directory
off ``sys.path``; ``-B`` writes no bytecode on the read-only mount. This script then inserts
exactly one absolute library path at ``sys.path[0]``:

* in the container, the constant ``/opt/crm-migrate/lib`` (when this file is
  ``/opt/crm-migrate/bin/crm-migrate.py``);
* otherwise (a test copy, or the host-side ``hostcheck`` call from ``scripts/migrate.sh``),
  ``<realpath of this file>/../../lib``, accepted only if it is an absolute directory
  holding ``crm_migrate/__init__.py``.

A ``crm_migrate`` package or a ``json.py`` planted in the working directory is never
importable: the working directory is not on ``sys.path``, and the imported package is
checked to come from the chosen library directory.
"""

import os
import sys

CONTAINER_ENTRY = "/opt/crm-migrate/bin/crm-migrate.py"
CONTAINER_LIB = "/opt/crm-migrate/lib"


def _library_dir():
    here = os.path.realpath(__file__)
    if here == CONTAINER_ENTRY:
        return CONTAINER_LIB
    lib = os.path.join(os.path.dirname(os.path.dirname(here)), "lib")
    if not os.path.isabs(lib) or not os.path.isfile(os.path.join(lib, "crm_migrate", "__init__.py")):
        sys.stderr.write("crm-migrate: library directory not found next to the entry script\n")
        raise SystemExit(2)
    return lib


def _bootstrap():
    if not (sys.flags.isolated and sys.flags.dont_write_bytecode):
        sys.stderr.write("crm-migrate: must be run as python -I -B\n")
        raise SystemExit(2)
    lib = _library_dir()
    sys.path.insert(0, lib)
    import crm_migrate  # noqa: E402  (after the path is fixed)

    pkg_dir = os.path.dirname(os.path.realpath(crm_migrate.__file__))
    if pkg_dir != os.path.join(os.path.realpath(lib), "crm_migrate"):
        sys.stderr.write("crm-migrate: crm_migrate imported from an unexpected location\n")
        raise SystemExit(2)
    from crm_migrate import cli  # noqa: E402

    return cli


if __name__ == "__main__":
    raise SystemExit(_bootstrap().main(sys.argv[1:]))
