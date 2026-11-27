"""CRM-BROWSER-001 increment 1: everything of the browser assurance runner that is executable
without Docker, a browser or a platform runtime. A fake `docker` records and answers every
command, so the runner's own command lines are checked against its host-safety policy."""

import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import browser_assurance as ba  # noqa: E402
import browser_assurance_core as core  # noqa: E402
import browser_assurance_runner as runner  # noqa: E402

KINDS = ["administrator", "er-staff", "er-intake", "er-manager"]
P = "crm-browser-abcd1234"
SUBNET = "10.%d.5.0/24" % 210  # built, not written: the repository policy forbids literal addresses


def event(kind, **kw):
    return dict(kind=kind, **kw)


class DataTests(unittest.TestCase):
    def test_shipped_data_declares_all_four_kinds_for_every_step(self):
        accounts = core.load_accounts()
        self.assertEqual([a["kind"] for a in accounts], KINDS)
        doc = core.load_expectations(KINDS)
        steps = doc["journeys"]["J1"]["steps"]
        self.assertEqual([s["id"] for s in steps], ["create-firm", "create-branch", "create-contact", "create-enquiry"])
        for s in steps:
            self.assertEqual(sorted(s["expect"]), sorted(KINDS))

    def test_missing_kind_or_unknown_result_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e.json")
            step = {"id": "s", "entity": "Account", "expect": {k: "performed" for k in KINDS}, "declarations": []}
            for mutate in (lambda s: s["expect"].pop("er-manager"), lambda s: s["expect"].update({"er-staff": "maybe"})):
                s = json.loads(json.dumps(step))
                mutate(s)
                with open(path, "w") as fh:
                    json.dump({"journeys": {"J1": {"steps": [s]}}}, fh)
                with self.assertRaises(core.DataError):
                    core.load_expectations(KINDS, path)

    def test_only_the_two_declarations_exist(self):
        core.check_declaration({"type": "client-access-denied", "console": ["x"]})
        core.check_declaration({"type": "server-refusal", "method": "DELETE", "status": 403,
                                "path_template": "Account/{id}", "console": [], "pageerrors": []})
        for bad in ({"type": "any-error", "console": []}, {"type": "client-access-denied", "console": [], "pattern": ".*"},
                    {"type": "server-refusal", "method": "DELETE", "status": 200, "path_template": "x", "console": [], "pageerrors": []}):
            with self.assertRaises(core.DataError):
                core.check_declaration(bad)


class VerdictTests(unittest.TestCase):
    def test_clean_step_passes(self):
        self.assertEqual(core.judge("performed", "performed", True, [])[0], "passed")

    def test_observed_differs_from_declared_fails(self):
        self.assertEqual(core.judge("performed", "refused", True, [])[0], "failed")

    def test_skipped_timed_out_or_unavailable_is_not_passed(self):
        for observed in ("timeout", "skipped", "error", None):
            self.assertEqual(core.judge("performed", observed, True, [])[0], "failed")

    def test_readback_disagreement_fails(self):
        self.assertEqual(core.judge("performed", "performed", False, [])[0], "failed")

    def test_undeclared_script_error_and_failed_request_fail(self):
        for ev in (event("pageerror", text="boom"), event("console", text="Failed to load resource"),
                   event("response", method="GET", status=400, path="Account"), event("requestfailed", text="GET /x")):
            verdict, reasons = core.judge("performed", "performed", True, [ev])
            self.assertEqual(verdict, "failed")
            self.assertTrue(any("undeclared" in r for r in reasons))

    def test_exact_server_refusal_declaration_is_accepted(self):
        decl = {"type": "server-refusal", "method": "DELETE", "status": 403, "path_template": "Account/{id}",
                "console": ["Failed to load resource: the server responded with a status of 403 (Forbidden)",
                            "Server side error 403: no"], "pageerrors": ["Error: 403"]}
        events = [event("response", method="DELETE", status=403, path="Account/" + "a" * 17),
                  event("console", text=decl["console"][0]), event("console", text=decl["console"][1]),
                  event("pageerror", text="Error: 403")]
        self.assertEqual(core.judge("refused", "refused", True, events, [decl])[0], "passed")

    def test_declaration_is_exact_not_a_filter(self):
        decl = {"type": "server-refusal", "method": "DELETE", "status": 403, "path_template": "Account/{id}",
                "console": [], "pageerrors": []}
        ok = event("response", method="DELETE", status=403, path="Account/" + "a" * 17)
        # another status, another method, another path, and a second occurrence are all undeclared
        for other in (event("response", method="DELETE", status=500, path="Account/" + "a" * 17),
                      event("response", method="POST", status=403, path="Account/" + "a" * 17),
                      event("response", method="DELETE", status=403, path="Contact/" + "a" * 17),
                      event("response", method="DELETE", status=403, path="Account/" + "b" * 17)):
            if other["path"] == ok["path"] and other["status"] == 403 and other["method"] == "DELETE":
                continue
            self.assertEqual(core.judge("refused", "refused", True, [ok, other], [decl])[0], "failed")
        self.assertEqual(core.judge("refused", "refused", True, [ok, dict(ok)], [decl])[0], "failed")

    def test_declared_but_absent_fails(self):
        decl = {"type": "client-access-denied", "console": ["Espo.Exceptions.AccessDenied"]}
        verdict, reasons = core.judge("not offered", "not offered", True, [], [decl])
        self.assertEqual(verdict, "failed")
        self.assertTrue(any("declared but absent" in r for r in reasons))


class ProofAndManifestTests(unittest.TestCase):
    def test_target_proof_accepts_own_value_and_refuses_a_foreign_application(self):
        import hashlib
        expected = hashlib.sha256(b"nonce-1").hexdigest()
        self.assertTrue(core.target_proof("nonce-1", expected))
        for foreign in ("nonce-2", "", "<html>EspoCRM</html>", None):
            self.assertFalse(core.target_proof(foreign, expected))
        self.assertFalse(core.target_proof("nonce-1", "not-a-digest"))

    def test_manifest_hashes_every_file_and_excludes_itself(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "J1"))
            pathlib.Path(d, "J1", "a.json").write_text("{}")
            pathlib.Path(d, "results.json").write_text("{}")
            exp = core.load_expectations(KINDS)
            res = {"J1": {"administrator": {"create-firm": {"verdict": "passed", "observed": "performed",
                                                             "expected": "performed", "reasons": []}}}}
            m = core.build_manifest(d, None, {"img": "id"}, {"p==1": "h"}, "chromium 1", res, exp)
            core.write_manifest(d, m)
            self.assertEqual(m["commit"], "uncommitted")
            self.assertEqual(sorted(m["files"]), ["J1/a.json", "results.json"])
            self.assertEqual(m["files"]["results.json"], core.sha256_file(os.path.join(d, "results.json")))
            self.assertNotIn("manifest.json", core.build_manifest(d, "a" * 40, {}, {}, "", {}, exp)["files"])
            self.assertEqual(core.build_manifest(d, "a" * 40, {}, {}, "", {}, exp)["commit"], "a" * 40)

    def test_package_hashes_read_the_two_pinned_wheels(self):
        found = core.package_hashes(os.path.join(REPO, "tests", "browser", "requirements.lock"))
        self.assertEqual(found, {
            "playwright==1.65.1": "5660e0b050a5bd5672bf8e366ed2580288a3d3640ff9444436ed2d890d3dc442",
            "greenlet==3.5.6": "975736b002ed080d124cf81a79cb7e05cb26d6b3f5c7a7b651c0fcce70353aa1"})


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.run_dir = os.path.join(self.tmp, "run")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.run_dir)
        os.makedirs(self.out)
        self.images = ba.pinned_images(REPO)
        self.policy = ba.Policy(P, REPO, self.run_dir, self.out, self.images)
        self.compose = ["compose", "-p", P, "-f", os.path.join(self.run_dir, "compose.json")]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_args(self, **over):
        a = ["run", "--rm", "--name", P + "-runner", f"--label={ba.LABEL}={P}", "--network", P + "_crm-net",
             "-v", f"{REPO}:/repo:ro", "-v", f"{self.out}:/out", self.images[2], "true"]
        return a

    def refused(self, args):
        with self.assertRaises(ba.RunError):
            self.policy.check(args)

    def test_admitted_commands(self):
        for args in (self.compose + ["up", "-d", "--wait"], self.compose + ["down", "-v", "--remove-orphans", "-t", "5"],
                     self.compose + ["exec", "-T", "crm-app", "true"], self.run_args(),
                     ["rm", "-f", P + "-runner"], ["network", "rm", P + "_egress"], ["volume", "rm", P + "_db"],
                     ["network", "create", f"--label={ba.LABEL}={P}", P + "_egress"],
                     ["ps", "-a", "-q", "--filter", f"label={ba.LABEL}={P}"]):
            self.policy.check(args)

    def test_prune_and_image_and_system_commands_are_refused(self):
        for args in (["system", "prune", "-f"], ["image", "prune"], ["container", "prune"], ["volume", "prune"],
                     ["network", "prune"], ["builder", "prune"], ["rmi", self.images[0]], ["image", "rm", self.images[0]],
                     ["pull", self.images[2]], ["image", "pull", self.images[2]], ["ps", "-a"], ["stop", P + "-x"]):
            self.refused(args)

    def test_nothing_foreign_can_be_touched(self):
        for args in (["rm", "-f", "crm-dev-crm-app-1"], ["rm", "-f", "crm-browser-other-runner"],
                     ["network", "rm", "crm-dev_crm-net"], ["volume", "rm", "crm-beta_db"],
                     ["rm", "-f", P + "-x", P + "-y"], ["rm", "-f", P + "-x; rm"],
                     ["ps", "-a", "-q", "--filter", f"label={ba.LABEL}=crm-dev"],
                     ["ps", "-a", "-q", "--filter", f"name={P}"],
                     ["compose", "-p", "crm-dev", "-f", os.path.join(self.run_dir, "compose.json"), "down", "-v"],
                     ["compose", "-p", P, "-f", "/srv/CRM/runtime/dev/compose.json", "down", "-v"],
                     self.compose + ["down", "--rmi", "all"], self.compose + ["rm", "-f"]):
            self.refused(args)

    def test_run_flags_never_allowed(self):
        base = self.run_args()
        for extra in (["--privileged"], ["--network=host"], ["--pid=host"], ["--pid", "host"], ["--ipc=host"],
                      ["--cap-add=SYS_ADMIN"], ["--userns=host"], ["--uts=host"], ["--device=/dev/mem"],
                      ["-v", "/var/run/docker.sock:/var/run/docker.sock"], ["-v", "/etc:/etc"], ["-v", f"{self.run_dir}x:/x"],
                      ["--mount", "type=bind,src=/,dst=/h"], ["-p", "80:80"], ["--volumes-from", "x"]):
            self.refused(base[:1] + extra + base[1:])
        self.refused(["run", "--rm", "--name", P + "-r", f"--label={ba.LABEL}={P}", "--network", "host",
                      self.images[2], "true"])
        self.refused([a for a in base if a != "--rm"])
        self.refused([a for a in base if not a.startswith("--label")])
        self.refused([a.replace(P + "-runner", "other") for a in base])
        self.refused([a.replace(":ro", "") if a.endswith(":ro") else a for a in base])
        self.refused(base[:-2] + ["ubuntu:latest", "true"])

    def test_remove_run_dir_only_removes_its_own_marked_directory(self):
        mine = ba.make_run_dir(P)
        try:
            ba.remove_run_dir(mine, P)
            self.assertFalse(os.path.exists(mine))
        finally:
            shutil.rmtree(mine, ignore_errors=True)
        foreign = tempfile.mkdtemp(prefix=P + "-")
        try:
            with self.assertRaises(ba.RunError):  # no marker
                ba.remove_run_dir(foreign, P)
            with open(os.path.join(foreign, ba.MARKER), "w") as fh:
                fh.write("crm-browser-other\n")
            with self.assertRaises(ba.RunError):  # marker names another run
                ba.remove_run_dir(foreign, P)
            link = os.path.join(self.tmp, P + "-link")
            os.symlink(foreign, link)
            with self.assertRaises(ba.RunError):
                ba.remove_run_dir(link, P)
            with self.assertRaises(ba.RunError):  # not named for the run
                ba.remove_run_dir(self.tmp, P)
            self.assertTrue(os.path.isdir(foreign))
        finally:
            shutil.rmtree(foreign)

    def test_out_dir_must_be_absent_or_empty(self):
        self.assertEqual(ba.check_out_dir(self.out), os.path.realpath(self.out))
        pathlib.Path(self.out, "x").write_text("")
        with self.assertRaises(ba.RunError):
            ba.check_out_dir(self.out)
        new = os.path.join(self.tmp, "new", "deeper")
        ba.check_out_dir(new)
        self.assertTrue(os.path.isdir(new))


class ComposeTests(unittest.TestCase):
    def doc(self):
        return ba.compose_document(REPO, P, SUBNET, {"db": "d", "db_root": "r", "admin": "a", "admin_user": "u"})

    def test_images_are_the_pinned_ones_and_the_network_has_no_route(self):
        doc = self.doc()
        base = json.loads(pathlib.Path(REPO, "deploy", "compose.json").read_text())["services"]
        self.assertEqual(doc["services"]["crm-app"]["image"], base["crm-app"]["image"])
        self.assertEqual(doc["services"]["crm-db"]["image"], base["crm-db"]["image"])
        self.assertTrue(doc["networks"]["crm-net"]["internal"])
        self.assertEqual(doc["services"]["crm-app"]["environment"]["CRM_ALLOWED_SOURCES"], SUBNET)
        ba.check_compose(doc, REPO, P)

    def test_refused_compose_content(self):
        for mutate in (lambda d: d["services"]["crm-app"].update(ports=["80:80"]),
                       lambda d: d["services"]["crm-app"].update(privileged=True),
                       lambda d: d["services"]["crm-app"].update(network_mode="host"),
                       lambda d: d["services"]["crm-app"].update(pid="host"),
                       lambda d: d["services"]["crm-app"]["volumes"].append(
                           {"type": "bind", "source": "/var/run/docker.sock", "target": "/s", "read_only": True}),
                       lambda d: d["services"]["crm-app"]["volumes"].append(
                           {"type": "bind", "source": "/srv/CRM/runtime/dev", "target": "/s", "read_only": True}),
                       lambda d: d["services"]["crm-app"]["volumes"].append(
                           {"type": "bind", "source": REPO, "target": "/rw"}),
                       lambda d: d["networks"]["crm-net"].update(internal=False)):
            doc = self.doc()
            mutate(doc)
            with self.assertRaises(ba.RunError):
                ba.check_compose(doc, REPO, P)
        with self.assertRaises(ba.RunError):
            ba.check_compose(self.doc(), REPO, "crm-dev")


class FakeDocker:
    """Stands in for subprocess.run: records every docker command and simulates the stack."""

    def __init__(self, runner_rc=0, leftover=False, interrupt_on_runner=False):
        self.calls, self.runner_rc, self.leftover, self.interrupt = [], runner_rc, leftover, interrupt_on_runner

    def __call__(self, argv, **kw):
        if argv[0] == "git":
            return subprocess.CompletedProcess(argv, 128, "", "")
        assert argv[0] == "docker", argv
        args = argv[1:]
        self.calls.append(args)
        out = ""
        if args[:2] == ["image", "inspect"]:
            out = "sha256:" + "0" * 64
        elif args[0] in ("ps", "network", "volume") and "--filter" in args:
            out = "leftover-id\n" if self.leftover and args[0] == "ps" else ""
        elif args[0] == "run" and "/out" in " ".join(args) and args[args.index("--name") + 1].endswith("-runner"):
            if self.interrupt:
                raise KeyboardInterrupt("signal 15")
            outdir = [a for a in args if a.endswith(":/out")][0].split(":")[0]
            exp = core.load_expectations(KINDS)["journeys"]
            doc = {"browser": "Chromium test", "error": None, "results": {j: {k: {st["id"]: {
                "verdict": "passed", "observed": st["expect"][k], "expected": st["expect"][k], "reasons": []}
                for st in exp[j]["steps"]} for k in KINDS} for j in exp}}
            for j in exp:
                for k in KINDS:
                    for st in exp[j]["steps"]:
                        d = pathlib.Path(outdir, j, k)
                        d.mkdir(parents=True, exist_ok=True)
                        (d / (st["id"] + ".json")).write_text(json.dumps({"verdict": "passed"}))
            pathlib.Path(outdir, "results.json").write_text(json.dumps(doc))
            return subprocess.CompletedProcess(argv, self.runner_rc, "", "")
        return subprocess.CompletedProcess(argv, 0, out, "")


class RunTests(unittest.TestCase):
    def go(self, fake, extra=()):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        out = os.path.join(tmp, "out")
        err = io.StringIO()
        self.err = err
        with mock.patch.object(ba.subprocess, "run", fake), mock.patch.dict(os.environ, {"TMPDIR": tmp}), \
                mock.patch.object(ba.tempfile, "tempdir", tmp), contextlib.redirect_stderr(err):
            rc = ba.main(["run", "--out", out, *extra])
        return rc, out, tmp

    def test_full_command_sequence_conforms_to_host_safety(self):
        fake = FakeDocker()
        rc, out, tmp = self.go(fake)
        self.assertEqual(rc, 0, self.err.getvalue())
        verbs = [c[0] for c in fake.calls]
        self.assertEqual(verbs[0], "compose")
        projects = {c[2] for c in fake.calls if c[0] == "compose"}
        self.assertEqual(len(projects), 1)
        project = projects.pop()
        self.assertTrue(project.startswith("crm-browser-"))
        for c in fake.calls:
            self.assertNotIn(c[0], ("pull", "rmi", "system", "builder", "prune"))
            for a in c:
                self.assertNotIn("docker.sock", a)
                self.assertNotIn("--privileged", a)
        removals = [c for c in fake.calls if c[0] in ("rm",) or c[:2] in (["network", "rm"], ["volume", "rm"])]
        for c in removals:
            self.assertTrue(c[-1].startswith(project), c)
        self.assertIn(["compose", "-p", project, "-f", mock.ANY, "down", "-v", "--remove-orphans", "-t", "5"],
                      [c if c[0] != "compose" or c[5] != "down" else c[:4] + [mock.ANY] + c[5:] for c in fake.calls])
        # the run directory is gone, the manifest and evidence are present
        self.assertEqual([n for n in os.listdir(tmp) if n.startswith("crm-browser-")], [])
        manifest = json.loads(pathlib.Path(out, "manifest.json").read_text())
        self.assertEqual(manifest["commit"], "uncommitted")
        self.assertEqual(manifest["journeys"], ["J1", "J2", "J3", "J4", "J5", "J6"])
        self.assertEqual(len(manifest["steps"]), 4 * sum(len(j["steps"]) for j in core.load_expectations(KINDS)["journeys"].values()))
        self.assertNotIn("manifest.json", manifest["files"])

    def test_failed_runner_exits_nonzero_and_still_tears_down(self):
        fake = FakeDocker(runner_rc=1)
        rc, out, tmp = self.go(fake)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c[0] == "compose" and "down" in c for c in fake.calls))
        self.assertEqual([n for n in os.listdir(tmp) if n.startswith("crm-browser-")], [])

    def test_interrupt_tears_down_and_exits_nonzero(self):
        fake = FakeDocker(interrupt_on_runner=True)
        rc, out, tmp = self.go(fake)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c[0] == "compose" and "down" in c for c in fake.calls))
        self.assertTrue(any(c[:2] == ["rm", "-f"] for c in fake.calls))
        self.assertEqual([n for n in os.listdir(tmp) if n.startswith("crm-browser-")], [])

    def test_anything_left_with_the_project_label_fails_the_run(self):
        rc, _out, _tmp = self.go(FakeDocker(leftover=True))
        self.assertEqual(rc, 3)

    def test_unknown_journey_is_refused_before_docker(self):
        for extra in (["--journey", "J9"],):
            fake = FakeDocker()
            rc, _o, _t = self.go(fake, extra)
            self.assertEqual(rc, 2)
            self.assertEqual(fake.calls, [])

    def test_the_command_accepts_no_target(self):
        for flag in ("--base-url", "--target", "--url", "--host"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                ba.main(["run", "--out", "/nonexistent-out", flag, "http://x"])


class VerifyTests(unittest.TestCase):
    """verify accepts genuine evidence and rejects every tampering of WO 3.5 (A5)."""
    SHA = "a" * 40

    def make(self, commit=None, fault=None):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        exp = core.load_expectations(KINDS)
        results = {}
        for j, jd in exp["journeys"].items():
            results[j] = {}
            for k in KINDS:
                results[j][k] = {}
                for st in jd["steps"]:
                    results[j][k][st["id"]] = {"verdict": "passed", "observed": st["expect"][k],
                                               "expected": st["expect"][k], "reasons": []}
                    d = pathlib.Path(self.out, j, k)
                    d.mkdir(parents=True, exist_ok=True)
                    (d / (st["id"] + ".json")).write_text(json.dumps({"verdict": "passed", "n": st["id"] + k}))
        core.write_manifest(self.out, core.build_manifest(self.out, commit or self.SHA, {}, {}, "C", results, exp, fault))
        self.exp = exp

    def problems(self, commit=None):
        return core.verify_evidence(self.out, commit or self.SHA, self.exp, KINDS)

    def edit_manifest(self, fn):
        path = os.path.join(self.out, "manifest.json")
        doc = json.loads(pathlib.Path(path).read_text())
        fn(doc)
        pathlib.Path(path).write_text(json.dumps(doc))

    def test_genuine_evidence_is_accepted(self):
        self.make()
        self.assertEqual(self.problems(), [])

    def test_another_commit_and_uncommitted_evidence_are_rejected(self):
        self.make()
        self.assertTrue(self.problems("b" * 40))
        self.make(commit="uncommitted")
        self.assertTrue(self.problems())

    def test_removed_changed_added_and_substituted_files_are_rejected(self):
        self.make()
        a, b = "J1/administrator/create-firm.json", "J1/er-staff/create-firm.json"
        os.remove(os.path.join(self.out, a))
        self.assertTrue(any("removed" in p for p in self.problems()))
        self.make()
        pathlib.Path(self.out, a).write_text("{}")
        self.assertTrue(any("changed" in p for p in self.problems()))
        self.make()
        pathlib.Path(self.out, "extra.txt").write_text("x")
        self.assertTrue(any("added" in p for p in self.problems()))
        self.make()
        shutil.copy(os.path.join(self.out, b), os.path.join(self.out, a))
        self.assertTrue(any("changed" in p for p in self.problems()))

    def test_incomplete_failed_and_fault_evidence_is_rejected(self):
        self.make()
        self.edit_manifest(lambda d: d["steps"].pop("J6/er-intake/request-edit-user"))
        self.assertTrue(any("missing step" in p for p in self.problems()))
        self.make()
        self.edit_manifest(lambda d: d["steps"]["J2/er-staff/edit-firm"].update(verdict="failed"))
        self.assertTrue(any("not passed" in p for p in self.problems()))
        self.make()
        self.edit_manifest(lambda d: d.update(journeys=["J1"]))
        self.assertTrue(any("journey set" in p for p in self.problems()))
        self.make(fault="killed-app")
        self.assertTrue(any("fault" in p for p in self.problems()))

    def test_a_changed_expectation_in_the_evidence_is_rejected(self):
        self.make()
        self.edit_manifest(lambda d: d["steps"]["J5/administrator/merge-firm"].update(observed="not offered", expected="not offered"))
        self.assertTrue(any("declared expectation" in p for p in self.problems()))

    def test_command_exit_codes(self):
        self.make()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ba.main(["verify", self.out, "--commit", self.SHA]), 0)
            self.assertEqual(ba.main(["verify", self.out, "--commit", "c" * 40]), 1)


class JourneyDataTests(unittest.TestCase):
    def test_every_journey_is_declared_for_all_four_kinds_and_implemented(self):
        doc = core.load_expectations(KINDS)
        self.assertEqual(sorted(doc["journeys"]), ["J1", "J2", "J3", "J4", "J5", "J6"])
        for jid, journey in doc["journeys"].items():
            for st in journey["steps"]:
                self.assertEqual(sorted(st["expect"]), sorted(KINDS))
                self.assertIn(st["id"], runner.JOURNEY_STEPS[jid])

    def test_declarations_are_per_kind_and_only_the_two_types(self):
        doc = core.load_expectations(KINDS)
        for journey in doc["journeys"].values():
            for st in journey["steps"]:
                for kind, lst in st["declarations"].items():
                    self.assertIn(kind, KINDS)
                    for d in lst:
                        core.check_declaration(d)
        step = {"id": "x", "expect": {k: "performed" for k in KINDS}, "declarations": [{"type": "x"}]}
        with self.assertRaises(core.DataError):
            core.load_expectations(KINDS, self.write({"journeys": {"J": {"steps": [step]}}}))

    def write(self, doc):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "e.json")
        pathlib.Path(path).write_text(json.dumps(doc))
        return path

    def test_refusals_are_declared_only_where_the_base_offers_the_control(self):
        steps = {s["id"]: s for s in core.load_expectations(KINDS)["journeys"]["J5"]["steps"]}
        self.assertEqual(steps["delete-firm-record"]["expect"]["er-staff"], "not offered")
        self.assertEqual(steps["delete-firm-record"]["expect"]["administrator"], "refused")
        self.assertEqual(steps["merge-enquiry"]["expect"]["er-manager"], "refused")
        self.assertEqual(steps["merge-enquiry"]["expect"]["er-intake"], "not offered")


class FaultTests(unittest.TestCase):
    def test_wrong_expectation_alters_exactly_one_expectation_and_the_step_fails(self):
        accounts = core.load_accounts()
        exp = core.load_expectations(KINDS)
        before = json.dumps(exp, sort_keys=True)
        runner.apply_fault("wrong-expectation", exp, accounts, ["J1"])
        step = exp["journeys"]["J1"]["steps"][0]
        self.assertEqual(step["expect"]["administrator"], "refused")
        self.assertNotEqual(before, json.dumps(exp, sort_keys=True))
        verdict, _ = core.judge(step["expect"]["administrator"], "performed", True, [], [])
        self.assertEqual(verdict, "failed")
        other = core.load_expectations(KINDS)
        runner.apply_fault(None, other, accounts, ["J1"])
        self.assertEqual(other["journeys"]["J1"]["steps"][0]["expect"]["administrator"], "performed")

    def test_fault_commands_conform_to_host_safety_and_are_recorded(self):
        for fault in ("broken-screen", "killed-app", "wrong-expectation"):
            fake = FakeDocker()
            tmp = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
            out = os.path.join(tmp, "out")
            with mock.patch.object(ba.subprocess, "run", fake), mock.patch.dict(os.environ, {"TMPDIR": tmp}), \
                    mock.patch.object(ba.tempfile, "tempdir", tmp), contextlib.redirect_stderr(io.StringIO()):
                ba.main(["run", "--out", out, "--journey", "J1", "--fault", fault])
            manifest = json.loads(pathlib.Path(out, "manifest.json").read_text())
            self.assertEqual(manifest["fault"], fault)
            if fault == "broken-screen":
                self.assertTrue(any("broken-screen" in " ".join(c) for c in fake.calls))
            self.assertFalse(any(c[0] not in ("compose", "run", "rm", "network", "volume", "ps", "image") for c in fake.calls))

    def test_killed_app_stops_only_this_runs_application_after_the_first_step(self):
        import threading
        calls = []
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        stop = threading.Event()
        os.makedirs(os.path.join(tmp, "J1", "administrator"))
        pathlib.Path(tmp, "J1", "administrator", "create-firm.json").write_text("{}")
        ba._kill_app_when_started(lambda *a, **k: calls.append(a), ["compose", "-p", P, "-f", "f"], tmp, stop)
        self.assertEqual(calls, [("compose", "-p", P, "-f", "f", "stop", "crm-app")])

    def test_policy_admits_stop_of_own_project_only(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        pol = ba.Policy(P, REPO, tmp, tmp, ba.pinned_images(REPO))
        pol.check(["compose", "-p", P, "-f", os.path.join(tmp, "compose.json"), "stop", "crm-app"])
        with self.assertRaises(ba.RunError):
            pol.check(["compose", "-p", "crm-dev", "-f", os.path.join(tmp, "compose.json"), "stop", "crm-app"])
        with self.assertRaises(ba.RunError):
            pol.check(["stop", "crm-app"])

    def test_break_screen_touches_only_the_runs_own_stack_paths(self):
        for path in set(__import__("re").findall(r"/var/www/html[\w/.-]*", ba.BREAK_SCREEN)):
            self.assertTrue(path.startswith(("/var/www/html/client/custom", "/var/www/html/custom")), path)
        self.assertNotIn("/repo", ba.BREAK_SCREEN)


class RunnerLogicTests(unittest.TestCase):
    def test_read_back_accepts_a_declared_list_only_when_contained(self):
        class Admin:
            def call(self, method, path):
                return {"contactsIds": ["a", "b"], "deleted": False}
        self.assertTrue(runner.read_back(Admin(), "Opportunity", "i", {"contactsIds": ["a"]}))
        self.assertFalse(runner.read_back(Admin(), "Opportunity", "i", {"contactsIds": ["c"]}))
        self.assertFalse(runner.read_back(Admin(), "Account", "i", {"deleted": True}))

    def test_the_early_proof_refuses_a_foreign_application_before_any_credential(self):
        import hashlib
        sha = hashlib.sha256(b"nonce").hexdigest()
        class Resp:
            def __init__(self, body): self.body = body
            def read(self): return self.body
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with mock.patch.object(runner.urllib.request, "urlopen", lambda *a, **k: Resp(b"nonce")):
            self.assertTrue(runner.early_proof("http://x", "/p", sha))
        with mock.patch.object(runner.urllib.request, "urlopen", lambda *a, **k: Resp(b"other")):
            self.assertFalse(runner.early_proof("http://x", "/p", sha))

    def test_outcome_ignores_the_saving_notice(self):
        class Page:
            url = "http://x/#Account/create"
            def query_selector(self, sel):
                return None if "alert-danger" in sel and False else (object() if sel == runner.journeys.REFUSAL else None)
            def wait_for_timeout(self, ms): pass
        self.assertNotIn(".alert,", runner.journeys.REFUSAL)
        self.assertIn("#notification.alert-danger", runner.journeys.REFUSAL)

    def test_git_commit_without_git_is_recorded_as_uncommitted(self):
        with mock.patch.object(ba.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(ba.git_commit(REPO))


class RunnerModuleTests(unittest.TestCase):
    def test_every_declared_step_has_an_implementation(self):
        doc = core.load_expectations(KINDS)
        for jid, journey in doc["journeys"].items():
            self.assertEqual(sorted(runner.JOURNEY_STEPS[jid]), sorted(s["id"] for s in journey["steps"]))

    def test_read_back_compares_stored_data(self):
        class Admin:
            def call(self, method, path):
                return {"name": "N", "accountId": "a1"}
        self.assertTrue(runner.read_back(Admin(), "Account", "i", {"name": "N", "accountId": "a1"}))
        self.assertFalse(runner.read_back(Admin(), "Account", "i", {"name": "other"}))
        self.assertFalse(runner.read_back(Admin(), "Account", None, {"name": "N"}))

    def test_missing_configuration_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "c.json")
            pathlib.Path(cfg).write_text(json.dumps({"base_url": "http://crm-app"}))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(["--config", cfg, "--out", d]), 2)


class GateTwoCorrectionTests(unittest.TestCase):
    """Corrections after operator gate 2: names, declarations as observed, selectors, setup."""

    FORBIDDEN = ("api", "key", "token", "secret", "auth", "access", "credential", "password")

    def steps(self):
        return core.load_expectations(KINDS)["journeys"]

    def test_no_step_id_or_evidence_name_looks_like_a_secret(self):
        for jid, journey in self.steps().items():
            for st in journey["steps"]:
                for kind in KINDS:
                    name = f"{jid}/{kind}/{st['id']}.json".lower()
                    for word in self.FORBIDDEN:
                        self.assertNotIn(word, name)

    def test_refusal_messages_are_the_observed_ones(self):
        j = {jid: {s["id"]: s for s in v["steps"]} for jid, v in self.steps().items()}
        def lines(step, kind):
            return [x for d in step["declarations"][kind] for x in d["console"]]
        never = "Server side error 403: Identity records (firms, contacts and their audit history) are never deleted. Retire a firm or contact, or supersede it with a successor."
        self.assertIn(never, lines(j["J5"]["delete-firm-record"], "administrator"))
        self.assertIn(never, lines(j["J5"]["delete-contact-related"], "administrator"))
        self.assertIn("Server side error 403: Mass action 'delete' is disabled for 'Account'.", lines(j["J5"]["delete-firm-list"], "administrator"))
        self.assertIn("Server side error 403: Action 'merge' is disabled for 'Opportunity'.", lines(j["J5"]["merge-enquiry"], "er-manager"))
        self.assertIn("Server side error 403: Identity audit records cannot be changed.", lines(j["J5"]["audit-edit"], "administrator"))
        self.assertIn("Server side error 403: No create access.", lines(j["J6"]["request-create-user"], "er-staff"))
        self.assertIn("Server side error 403: No edit access.", lines(j["J6"]["request-edit-user"], "er-intake"))
        self.assertEqual(j["J6"]["request-create-user"]["declarations"]["er-staff"][0]["pageerrors"], [])
        self.assertEqual(j["J5"]["audit-edit"]["declarations"]["administrator"][0]["pageerrors"], ["error"])

    def test_every_server_refusal_declares_both_console_lines(self):
        for journey in self.steps().values():
            for st in journey["steps"]:
                for decls in st["declarations"].values():
                    for d in decls:
                        if d["type"] == "server-refusal":
                            self.assertEqual(d["console"][0], "Failed to load resource: the server responded with a status of 403 (Forbidden)")
                            self.assertTrue(d["console"][1].startswith("Server side error 403: "))

    def test_base_behaviour_is_declared_not_labelled_not_offered(self):
        j = {s["id"]: s for s in self.steps()["J5"]["steps"]}
        for sid in ("delete-firm-list", "delete-contact-list", "audit-edit", "audit-remove", "delete-contact-related"):
            self.assertEqual(j[sid]["expect"]["administrator"], "refused", sid)
            self.assertEqual(j[sid]["expect"]["er-manager"], "not offered", sid)
        for kind in KINDS:
            self.assertEqual(j["unlink-primary-firm"]["expect"][kind], "refused")
        j4 = {s["id"]: s for s in self.steps()["J4"]["steps"]}
        self.assertEqual(set(j4["branches-panel"]["expect"].values()), {"not offered"})
        self.assertNotIn("delete-branch-related", j)

    def test_journeys_use_the_observed_selectors(self):
        src = pathlib.Path(REPO, "scripts", "browser_assurance_journeys.py").read_text()
        self.assertIn("button[data-name=select]", src)
        self.assertNotIn("button[data-action=select]", src)
        self.assertIn("#main .admin-content", src)
        self.assertIn("#main .import-container", src)
        self.assertNotIn("#main, ", src)
        self.assertIn('f"%{c.tag}{slug(c)}"', src)
        self.assertIn("[data-action=setPrimary]", src)
        self.assertNotIn("data-name=account]", src.split("def j4_switch_primary_firm")[1].split("def j4_change_enquiry_firm")[0])
        self.assertIn("assignedUser", src)

    def test_offered_counts_only_visible_elements(self):
        seen = []
        class Loc:
            def count(self): return 0
        class Page:
            def locator(self, sel): seen.append(sel); return Loc()
        self.assertFalse(runner.journeys.offered(Page(), "a[data-action=remove]"))
        self.assertEqual(seen, ["a[data-action=remove]:visible"])

    def test_open_screen_waits_for_the_target_marker_not_a_stale_one(self):
        j = runner.journeys
        class Page:
            def __init__(self): self.n = 0
            def goto(self, *a, **k): pass
            def query_selector(self, sel):
                self.n += 1
                return object() if sel == "#main .admin-content" and self.n > 2 else None
            def inner_text(self, sel): return "loading"
            def wait_for_timeout(self, ms): pass
        c = j.Ctx(Page(), "http://x", "t", "administrator", "u", None)
        self.assertEqual(j.open_screen(c, "Admin", "#main .admin-content"), "ready")
        self.assertGreater(c.page.n, 2)

    def test_a_denied_screen_is_not_ready(self):
        j = runner.journeys
        class Page:
            def goto(self, *a, **k): pass
            def query_selector(self, sel): return None
            def inner_text(self, sel): return j.DENIED
            def wait_for_timeout(self, ms): pass
        c = j.Ctx(Page(), "http://x", "t", "er-staff", "u", None)
        self.assertEqual(j.open_screen(c, "Admin", "#main .admin-content"), "denied")

    def test_every_step_starts_from_a_blank_page(self):
        src = pathlib.Path(REPO, "scripts", "browser_assurance_runner.py").read_text()
        self.assertLess(src.index('page.goto("about:blank")'), src.index("rec.reset()"))

    def test_the_vendor_frame_is_disabled_in_the_runs_own_stack_only(self):
        fake = FakeDocker()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with mock.patch.object(ba.subprocess, "run", fake), mock.patch.dict(os.environ, {"TMPDIR": tmp}), \
                mock.patch.object(ba.tempfile, "tempdir", tmp), contextlib.redirect_stderr(io.StringIO()):
            ba.main(["run", "--out", os.path.join(tmp, "out"), "--journey", "J1"])
        cmds = [" ".join(c) for c in fake.calls if "adminPanelIframeDisabled" in " ".join(c)]
        self.assertEqual(len(cmds), 1)
        self.assertIn("exec -T crm-app", cmds[0])
        self.assertIn("adminPanelIframeDisabled true --type=bool", cmds[0])
        self.assertNotIn("adminPanelIframeUrl", " ".join(" ".join(c) for c in fake.calls))


if __name__ == "__main__":
    unittest.main()
