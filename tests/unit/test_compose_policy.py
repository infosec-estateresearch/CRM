"""Compose policy tests (WO CRM-001 item 5).

TestDeployedComposePolicy checks deploy/compose.json. To show a rule's test can
fail, point it at a broken fixture:

    CRM_COMPOSE_UNDER_TEST=tests/unit/fixtures/compose_bad_db_ports.json \
        python3 -m unittest discover -s tests/unit -p test_compose_policy.py

TestBrokenFixtures keeps that demonstration permanently in the suite.
"""

import json
import os
import re
import unittest

import compose_policy as policy

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
UNDER_TEST = os.environ.get("CRM_COMPOSE_UNDER_TEST", policy.COMPOSE_PATH)
ENV_EXAMPLE = os.path.join(policy.REPO, "deploy", "env.example")

ESPOCRM_IMAGE = ("espocrm/espocrm:10.0.12@sha256:"
                 "b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec")
MARIADB_IMAGE = ("mariadb:11.4.13@sha256:"
                 "d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620")

# fixture -> the rules it must break (every other rule must still hold)
BROKEN = {
    "compose_bad_db_ports.json": {"db_no_ports"},
    "compose_bad_port_all_interfaces.json": {"ports_loopback"},
    "compose_bad_external_network.json": {"no_external"},
    "compose_bad_external_volume.json": {"no_external"},
    "compose_bad_image_unpinned.json": {"images_pinned", "images_match_register"},
    "compose_bad_digest_mismatch.json": {"images_match_register"},
    "compose_bad_prefix_service.json": {"crm_prefix"},
    "compose_bad_prefix_network.json": {"crm_prefix"},
    "compose_bad_prefix_volume.json": {"crm_prefix"},
    "compose_bad_container_name.json": {"no_container_name"},
}


class TestDeployedComposePolicy(unittest.TestCase):
    """One test per policy rule, against the compose file under test."""

    @classmethod
    def setUpClass(cls):
        cls.doc = policy.load_compose(UNDER_TEST)
        cls.register = policy.load_register()

    def assertRule(self, rule):
        self.assertEqual(policy.RULES[rule](self.doc, self.register), [],
                         f"{rule} violated in {UNDER_TEST}")

    def test_db_publishes_no_ports(self):
        self.assertRule("db_no_ports")

    def test_every_published_port_binds_loopback(self):
        self.assertRule("ports_loopback")

    def test_no_external_networks_or_volumes(self):
        self.assertRule("no_external")

    def test_every_image_pinned_by_digest(self):
        self.assertRule("images_pinned")

    def test_images_equal_register_digests(self):
        self.assertRule("images_match_register")

    def test_service_network_volume_keys_have_crm_prefix(self):
        self.assertRule("crm_prefix")

    def test_no_service_sets_container_name(self):
        self.assertRule("no_container_name")


class TestBrokenFixtures(unittest.TestCase):
    """Each rule fails on a fixture that breaks it, and only the intended rules fail."""

    def setUp(self):
        self.register = policy.load_register()

    def test_every_rule_has_a_breaking_fixture(self):
        covered = set().union(*BROKEN.values())
        self.assertEqual(covered, set(policy.RULES))
        self.assertEqual(set(BROKEN), {f for f in os.listdir(FIXTURES)
                                       if f.startswith("compose_bad_")})

    def test_fixtures_break_exactly_their_rules(self):
        for fixture, expected in BROKEN.items():
            with self.subTest(fixture=fixture):
                doc = policy.load_compose(os.path.join(FIXTURES, fixture))
                failing = {r for r, v in policy.check(doc, self.register).items() if v}
                self.assertEqual(failing, expected)


class TestPortParsing(unittest.TestCase):
    def test_short_and_long_syntax(self):
        cases = {
            "127.0.0.1:8180:80": ("127.0.0.1", "8180"),
            "8180:80": ("", "8180"),
            "80": ("", ""),
            "127.0.0.1:8180:80/tcp": ("127.0.0.1", "8180"),
            "[::1]:8180:80": ("::1", "8180"),
        }
        for port, expected in cases.items():
            with self.subTest(port=port):
                self.assertEqual(policy._published(port), expected)
        self.assertEqual(policy._published({"host_ip": "127.0.0.1", "published": 8180,
                                            "target": 80}), ("127.0.0.1", "8180"))

    def test_bare_container_port_and_host_network_are_violations(self):
        doc = {"services": {"crm-app": {"ports": ["80"]},
                            "crm-x": {"network_mode": "host"}}}
        self.assertEqual(len(policy.rule_ports_loopback(doc)), 2)
        self.assertTrue(policy.rule_ports_loopback(
            {"services": {"crm-app": {"ports": [{"target": 80, "published": 8180}]}}}))

    def test_missing_db_service_is_a_violation(self):
        self.assertTrue(policy.rule_db_no_ports({"services": {}}))


class TestRegister(unittest.TestCase):
    def test_register_parses_both_images(self):
        reg = policy.load_register()
        self.assertEqual(reg["espocrm"]["version"], "10.0.12")
        self.assertEqual(reg["mariadb"]["version"], "11.4.13")
        self.assertEqual(reg["espocrm"]["digest"], ESPOCRM_IMAGE.split("@")[1])
        self.assertEqual(reg["mariadb"]["digest"], MARIADB_IMAGE.split("@")[1])


class TestComposeShape(unittest.TestCase):
    """The structure WO item 1 asks for, on deploy/compose.json itself."""

    @classmethod
    def setUpClass(cls):
        cls.doc = policy.load_compose()
        cls.svc = cls.doc["services"]

    def test_project_services_and_network(self):
        self.assertEqual(self.doc["name"], "crm-dev")
        self.assertEqual(set(self.svc), {"crm-app", "crm-daemon", "crm-db"})
        self.assertEqual(set(self.doc["networks"]), {"crm-net"})
        self.assertNotIn("name", self.doc["networks"]["crm-net"])
        self.assertEqual(self.doc["networks"]["crm-net"]["ipam"]["config"],
                         [{"subnet": "172.16.10.0/24"}])
        self.assertNotIn("volumes", self.doc)
        for name, svc in self.svc.items():
            self.assertEqual(set(svc["networks"]), {"crm-net"}, name)

    def test_images_and_daemon_entrypoint(self):
        self.assertEqual(self.svc["crm-app"]["image"], ESPOCRM_IMAGE)
        self.assertEqual(self.svc["crm-daemon"]["image"], ESPOCRM_IMAGE)
        self.assertEqual(self.svc["crm-db"]["image"], MARIADB_IMAGE)
        self.assertEqual(self.svc["crm-daemon"]["entrypoint"], "docker-daemon.sh")

    def test_only_app_publishes_and_only_8180(self):
        self.assertEqual(self.svc["crm-app"]["ports"], ["127.0.0.1:8180:80"])
        self.assertNotIn("ports", self.svc["crm-daemon"])
        self.assertNotIn("ports", self.svc["crm-db"])

    def test_healthchecks(self):
        for name in ("crm-app", "crm-db"):
            self.assertTrue(self.svc[name]["healthcheck"]["test"], name)

    def test_mounts(self):
        def binds(name):
            return {v["target"]: v for v in self.svc[name]["volumes"]}
        for name in ("crm-app", "crm-daemon"):
            custom = binds(name)["/var/www/html/custom"]
            self.assertEqual(custom["type"], "bind")
            self.assertTrue(custom["read_only"])
            # compose.json lives in deploy/, so the repo's custom/ is ../custom
            self.assertEqual(os.path.normpath(os.path.join(policy.REPO, "deploy",
                                                           custom["source"])),
                             os.path.join(policy.REPO, "custom"))
            self.assertEqual(binds(name)["/var/www/html"]["source"],
                             "${CRM_DATA_DIR:?CRM_DATA_DIR must be set in the env file}")
        self.assertEqual(binds("crm-db")["/var/lib/mysql"]["source"],
                         "${CRM_DB_DIR:?CRM_DB_DIR must be set in the env file}")
        for name, svc in self.svc.items():
            for vol in svc["volumes"]:
                self.assertEqual(vol["type"], "bind", name)


class TestEnvExample(unittest.TestCase):
    def setUp(self):
        with open(ENV_EXAMPLE, encoding="utf-8") as fh:
            self.lines = [l.strip() for l in fh if l.strip() and not l.lstrip().startswith("#")]
        with open(policy.COMPOSE_PATH, encoding="utf-8") as fh:
            self.compose_text = fh.read()

    def test_names_only_no_values(self):
        for line in self.lines:
            self.assertRegex(line, r"^[A-Z][A-Z0-9_]*=$", f"value present: {line!r}")

    def test_names_match_compose_variables_and_are_required(self):
        names = {l[:-1] for l in self.lines}
        used = set(re.findall(r"\$\{([A-Z0-9_]+)", self.compose_text))
        self.assertEqual(names, used)
        # every interpolation fails loudly when unset
        self.assertEqual(re.findall(r"\$\{[A-Z0-9_]+(?!:\?)[}:-]", self.compose_text), [])

    def test_compose_holds_no_literal_secrets(self):
        doc = json.loads(self.compose_text)
        for name, svc in doc["services"].items():
            for key, value in (svc.get("environment") or {}).items():
                if "PASSWORD" in key:
                    self.assertRegex(value, r"^\$\{[A-Z0-9_]+:\?", f"{name}.{key}")


if __name__ == "__main__":
    unittest.main()
