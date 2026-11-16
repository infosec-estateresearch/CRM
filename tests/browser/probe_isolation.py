#!/usr/bin/env python3
"""CRM-CLIENT-001R2 annex B4: prove the browser container's isolation before any journey.

Runs only inside the hardened runner container (never on the host). It contacts
exactly the probe targets handed in as data (--targets), nothing else, and holds
no address, credential or host name of its own. Standard library only.

targets file (JSON, written by the operator):
  {"reachable": [{"id": "...", "host": "...", "port": 80}],
   "unreachable": [{"id": "...", "kind": "tcp", "host": "...", "port": 3306},
                   {"id": "...", "kind": "dns", "name": "..."}]}

isolation.json records every target with the expected and the actual result and the
raw route table. Exit status: 0 only if the route table shows exactly one connected
network and no default route, every reachable target connected, and every
unreachable target failed within the time limit. Any unexpected success stops the
run (exit 3): there is no fallback to a wider network.
"""
import argparse
import json
import socket
import sys
import time

TIMEOUT = 3.0
ROUTE_TABLE = "/proc/net/route"
REQUIRED_IDS = ("app-http", "db-3306", "app-crmnet", "host-dev-8180", "host-dev-8290",
                "loopback-8280", "beta-gateway", "beta-app", "public-443", "dns-public")


def read_route_table(path=ROUTE_TABLE):
    with open(path, encoding="ascii") as fh:
        return fh.read()


def parse_routes(text):
    """[(destination, mask)] hex pairs of the kernel route table, header skipped."""
    routes = []
    for line in text.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 8:
            routes.append((cols[1], cols[7]))
    return routes


def routes_ok(text):
    routes = parse_routes(text)
    return len(routes) == 1 and routes[0] != ("00000000", "00000000")


def tcp_connect(host, port, timeout=TIMEOUT):
    """True if a TCP connection is made; False if it fails or times out."""
    start = time.monotonic()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, time.monotonic() - start
    except OSError:
        return False, time.monotonic() - start


def resolves(name, timeout=TIMEOUT):
    """True if the name resolves within the time limit. A resolver that cannot answer
    in time counts as failure."""
    import threading
    box = {}

    def work():
        try:
            box["ok"] = bool(socket.getaddrinfo(name, None))
        except OSError:
            box["ok"] = False
    start = time.monotonic()
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    return bool(box.get("ok")), time.monotonic() - start


def probe(targets, route_text):
    results = []
    for t in targets.get("reachable", []):
        ok, took = tcp_connect(t["host"], t["port"])
        results.append({"id": t["id"], "kind": "tcp", "host": t["host"], "port": int(t["port"]),
                        "expected": "success", "actual": "success" if ok else "fail",
                        "elapsed": round(took, 3)})
    for t in targets.get("unreachable", []):
        if t.get("kind") == "dns":
            ok, took = resolves(t["name"])
            rec = {"id": t["id"], "kind": "dns", "name": t["name"]}
        else:
            ok, took = tcp_connect(t["host"], t["port"])
            rec = {"id": t["id"], "kind": "tcp", "host": t["host"], "port": int(t["port"])}
        rec.update({"expected": "fail", "actual": "success" if ok else "fail",
                    "elapsed": round(took, 3)})
        results.append(rec)
    gate = routes_ok(route_text) and all(
        r["expected"] == r["actual"] and (r["expected"] == "success" or r["elapsed"] <= TIMEOUT + 1.0)
        for r in results)
    ids = {r["id"] for r in results}
    gate = gate and all(i in ids for i in REQUIRED_IDS)
    return {"route_table": route_text, "targets": results, "gate": gate,
            "time_limit_seconds": TIMEOUT}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    with open(args.targets, encoding="utf-8") as fh:
        targets = json.load(fh)
    result = probe(targets, read_route_table())
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    if not result["gate"]:
        print("probe_isolation: ISOLATION GATE FAILED; the run is BLOCKED", file=sys.stderr)
        return 3
    print("probe_isolation: isolation proven")
    return 0


if __name__ == "__main__":
    sys.exit(main())
