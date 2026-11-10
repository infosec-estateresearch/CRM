"""Compose policy tests (WO CRM-001 item 5).

TestDeployedComposePolicy checks deploy/compose.json. To show a rule's test can
fail, point it at a broken fixture:

    CRM_COMPOSE_UNDER_TEST=tests/unit/fixtures/compose_bad_db_ports.json \
        python3 -m unittest discover -s tests/unit -p test_compose_policy.py

The Apache access file works the same way:

    CRM_ACCESS_CONF_UNDER_TEST=tests/unit/fixtures/apache_bad_remoteip.conf \
        python3 -m unittest discover -s tests/unit -p test_compose_policy.py

TestBrokenFixtures keeps both demonstrations permanently in the suite.
"""

import json
import os
import re
import shutil
import tempfile
import unittest

import compose_policy as policy

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
UNDER_TEST = os.environ.get("CRM_COMPOSE_UNDER_TEST", policy.COMPOSE_PATH)
CONF_UNDER_TEST = os.environ.get("CRM_ACCESS_CONF_UNDER_TEST", policy.ACCESS_CONF_PATH)
ENV_EXAMPLE = os.path.join(policy.REPO, "deploy", "env.example")

ESPOCRM_IMAGE = ("espocrm/espocrm:10.0.12@sha256:"
                 "b50245d1e291b2636116b0396ce0d06018ffcded6a6c61c7af2420443a20f3ec")
MARIADB_IMAGE = ("mariadb:11.4.13@sha256:"
                 "d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620")
BIND = "${CRM_BIND_IP:?CRM_BIND_IP must be set in the env file}:8180:80"
SOURCES = "${CRM_ALLOWED_SOURCES:?CRM_ALLOWED_SOURCES must be set in the env file}"
CONF_MOUNT = {"type": "bind", "source": "./apache/crm-access.conf",
              "target": "/etc/apache2/conf-enabled/crm-access.conf", "read_only": True}

# fixture -> the rules it must break (every other rule must still hold)
BROKEN = {
    "compose_bad_db_ports.json": {"db_no_ports", "app_single_env_bind"},
    "compose_bad_port_all_interfaces.json": {"ports_host_ip", "app_single_env_bind"},
    "compose_bad_port_unspecified_ip.json": {"ports_host_ip", "app_single_env_bind",
                                             "no_literal_ip"},
    "compose_bad_port_literal_bind_ip.json": {"app_single_env_bind", "no_literal_ip"},
    "compose_bad_daemon_publishes.json": {"app_single_env_bind"},
    "compose_bad_literal_ip_site_url.json": {"no_literal_ip"},
    "compose_bad_access_conf_writable.json": {"access_conf_mount"},
    "compose_bad_access_conf_on_daemon.json": {"access_conf_mount"},
    "compose_bad_access_conf_missing.json": {"access_conf_mount"},
    "compose_bad_access_sources_missing.json": {"access_sources_env"},
    "compose_bad_access_sources_default.json": {"access_sources_env"},
    "compose_bad_external_network.json": {"no_external"},
    "compose_bad_external_volume.json": {"no_external"},
    "compose_bad_image_unpinned.json": {"images_pinned", "images_match_register"},
    "compose_bad_digest_mismatch.json": {"images_match_register"},
    "compose_bad_prefix_service.json": {"crm_prefix"},
    "compose_bad_prefix_network.json": {"crm_prefix"},
    "compose_bad_prefix_volume.json": {"crm_prefix"},
    "compose_bad_container_name.json": {"no_container_name"},
    "compose_bad_docroot_mount.json": {"no_docroot_mount", "espocrm_mounts"},
    "compose_bad_mount_missing.json": {"espocrm_mounts"},
    "compose_bad_mount_literal_source.json": {"espocrm_mounts"},
    "compose_bad_mount_read_only.json": {"espocrm_mounts_writable"},
}

# Apache access-file fixture -> the conf rules it must break
BROKEN_CONF = {
    "apache_bad_all_granted.conf": {"conf_deny_by_default", "conf_no_grant"},
    "apache_bad_satisfy_any.conf": {"conf_no_grant"},
    "apache_bad_sub_path_override.conf": {"conf_deny_by_default"},
    "apache_bad_remoteip.conf": {"conf_no_remoteip"},
    "apache_bad_directory_only.conf": {"conf_deny_by_default"},
    "apache_bad_location_extra_grant.conf": {"conf_deny_by_default", "conf_no_grant"},
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

    def test_every_published_port_names_a_host_ip_never_unspecified(self):
        self.assertRule("ports_host_ip")

    def test_app_publishes_only_the_env_sourced_lan_bind(self):
        self.assertRule("app_single_env_bind")

    def test_no_literal_non_loopback_address(self):
        self.assertRule("no_literal_ip")

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

    def test_no_service_mounts_the_document_root(self):
        self.assertRule("no_docroot_mount")

    def test_espocrm_services_mount_the_three_persistent_dirs_from_env(self):
        self.assertRule("espocrm_mounts")

    def test_espocrm_persistent_mounts_are_writable(self):
        self.assertRule("espocrm_mounts_writable")

    def test_access_file_mounted_read_only_on_crm_app_only(self):
        self.assertRule("access_conf_mount")

    def test_app_receives_allowed_sources_from_the_env_file(self):
        self.assertRule("access_sources_env")


class TestDeployedAccessConf(unittest.TestCase):
    """One test per access-file rule, against the conf file under test."""

    @classmethod
    def setUpClass(cls):
        cls.text = policy.load_conf(CONF_UNDER_TEST)

    def assertRule(self, rule):
        self.assertEqual(policy.CONF_RULES[rule](self.text), [],
                         f"{rule} violated in {CONF_UNDER_TEST}")

    def test_every_path_denied_by_default_except_loopback_and_sources(self):
        self.assertRule("conf_deny_by_default")

    def test_nothing_grants_everyone(self):
        self.assertRule("conf_no_grant")

    def test_no_remoteip_and_no_trusted_header(self):
        self.assertRule("conf_no_remoteip")

    def test_compose_mount_source_is_this_file(self):
        source = os.path.join(policy.REPO, "deploy", policy.ACCESS_CONF_SOURCE)
        self.assertTrue(os.path.samefile(source, policy.ACCESS_CONF_PATH))
        self.assertNotIn("${CRM_ALLOWED_SOURCES}",
                         "".join(l for l in policy.load_conf().splitlines(True)
                                 if l.lstrip().startswith("#")),
                         "Apache must not see the variable in a comment")


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

    def test_every_conf_rule_has_a_breaking_fixture(self):
        self.assertEqual(set().union(*BROKEN_CONF.values()), set(policy.CONF_RULES))
        self.assertEqual(set(BROKEN_CONF), {f for f in os.listdir(FIXTURES)
                                            if f.startswith("apache_bad_")})

    def test_conf_fixtures_break_exactly_their_rules(self):
        for fixture, expected in BROKEN_CONF.items():
            with self.subTest(fixture=fixture):
                text = policy.load_conf(os.path.join(FIXTURES, fixture))
                failing = {r for r, v in policy.check_conf(text).items() if v}
                self.assertEqual(failing, expected)


class TestPortParsing(unittest.TestCase):
    def test_short_and_long_syntax(self):
        cases = {
            "127.0.0.1:8180:80": ("127.0.0.1", "8180"),
            "8180:80": ("", "8180"),
            "80": ("", ""),
            "127.0.0.1:8180:80/tcp": ("127.0.0.1", "8180"),
            "[::1]:8180:80": ("::1", "8180"),
            BIND: ("${CRM_BIND_IP:?CRM_BIND_IP must be set in the env file}", "8180"),
            BIND + "/tcp": ("${CRM_BIND_IP:?CRM_BIND_IP must be set in the env file}", "8180"),
        }
        for port, expected in cases.items():
            with self.subTest(port=port):
                self.assertEqual(policy._published(port), expected)
        self.assertEqual(policy._published({"host_ip": "127.0.0.1", "published": 8180,
                                            "target": 80}), ("127.0.0.1", "8180"))
        self.assertEqual(policy._port_spec(BIND)[2], "80")
        self.assertEqual(policy._port_spec("${CRM_BIND_IP:?x}:80"),
                         ("${CRM_BIND_IP:?x}", "", "80"))

    def test_bare_container_port_and_host_network_are_violations(self):
        doc = {"services": {"crm-app": {"ports": ["80"]},
                            "crm-x": {"network_mode": "host"}}}
        self.assertEqual(len(policy.rule_ports_host_ip(doc)), 2)
        self.assertTrue(policy.rule_ports_host_ip(
            {"services": {"crm-app": {"ports": [{"target": 80, "published": 8180}]}}}))

    def test_unspecified_addresses_are_violations_and_named_ips_are_not(self):
        for port in ("0.0.0.0:8180:80", "[::]:8180:80", "8180:80",
                     {"host_ip": "0.0.0.0", "published": 8180, "target": 80}):
            with self.subTest(port=port):
                self.assertTrue(policy.rule_ports_host_ip(
                    {"services": {"crm-app": {"ports": [port]}}}))
        for port in (BIND, "127.0.0.1:8180:80", "192.0.2.10:8180:80"):
            with self.subTest(port=port):
                self.assertEqual(policy.rule_ports_host_ip(
                    {"services": {"crm-app": {"ports": [port]}}}), [])


class TestBindRules(unittest.TestCase):
    """app_single_env_bind and no_literal_ip on small documents."""

    def app(self, ports, **others):
        services = {"crm-app": {"ports": ports}}
        services.update(others)
        return {"services": services}

    def test_exact_env_bind_passes(self):
        self.assertEqual(policy.rule_app_single_env_bind(self.app([BIND])), [])
        self.assertEqual(policy.rule_app_single_env_bind(self.app(
            [{"host_ip": "${CRM_BIND_IP:?x}", "published": 8180, "target": 80}])), [])

    def test_anything_else_is_a_violation(self):
        bad = {
            "loopback, the old binding": ["127.0.0.1:8180:80"],
            "literal LAN address": ["192.0.2.10:8180:80"],
            "no host IP": ["8180:80"],
            "default instead of required": ["${CRM_BIND_IP:-127.0.0.1}:8180:80"],
            "other variable": ["${CRM_OTHER_IP:?x}:8180:80"],
            "other host port": ["${CRM_BIND_IP:?x}:8181:80"],
            "other container port": ["${CRM_BIND_IP:?x}:8180:443"],
            "two mappings": [BIND, "${CRM_BIND_IP:?x}:8443:443"],
            "none": [],
        }
        for why, ports in bad.items():
            with self.subTest(why=why):
                self.assertTrue(policy.rule_app_single_env_bind(self.app(ports)))
        self.assertTrue(policy.rule_app_single_env_bind(
            self.app([BIND], **{"crm-db": {"ports": ["${CRM_BIND_IP:?x}:3306:3306"]}})))
        self.assertTrue(policy.rule_app_single_env_bind({"services": {}}))

    def test_literal_addresses_found_anywhere_except_loopback_and_own_subnet(self):
        ok = {"services": {"crm-app": {"ports": [BIND], "healthcheck": {
                  "test": ["CMD", "curl", "http://127.0.0.1/", "http://[::1]/"]}}},
              "networks": {"crm-net": {"ipam": {"config": [{"subnet": "172.16.10.0/24"}]}}}}
        self.assertEqual(policy.rule_no_literal_ip(ok), [])
        bad = [
            {"services": {"crm-app": {"environment": {"X": "http://192.0.2.10:8180"}}}},
            {"services": {"crm-app": {"extra_hosts": ["db:198.51.100.7"]}}},
            {"services": {"crm-app": {"dns": ["2001:db8::53"]}}},
            {"services": {"crm-app": {"ports": ["0.0.0.0:8180:80"]}}},
            {"x-note": {"203.0.113.0/24": "a key"}},
            {"networks": {"crm-net": {"ipam": {"config": [{"subnet": "192.0.2.0/24"}]}}}},
            {"services": {"crm-app": {"labels": {"subnet": "172.16.10.0/24"}}}},
        ]
        for doc in bad:
            with self.subTest(doc=doc):
                self.assertEqual(len(policy.rule_no_literal_ip(doc)), 1)

    def test_versions_and_digests_are_not_addresses(self):
        doc = {"services": {"crm-app": {"image": ESPOCRM_IMAGE},
                            "crm-db": {"image": MARIADB_IMAGE}}}
        self.assertEqual(policy.rule_no_literal_ip(doc), [])


class TestAccessRules(unittest.TestCase):
    """access_conf_mount and access_sources_env on small documents."""

    def doc(self, app_volumes, daemon_volumes=(), env=None):
        return {"services": {
            "crm-app": {"volumes": list(app_volumes),
                        "environment": {"CRM_ALLOWED_SOURCES": SOURCES} if env is None else env},
            "crm-daemon": {"volumes": list(daemon_volumes)}}}

    def test_good_mount_passes_in_long_and_short_syntax(self):
        self.assertEqual(policy.rule_access_conf_mount(self.doc([CONF_MOUNT])), [])
        short = "./apache/crm-access.conf:/etc/apache2/conf-enabled/crm-access.conf:ro"
        self.assertEqual(policy.rule_access_conf_mount(self.doc([short])), [])

    def test_bad_mounts_are_violations(self):
        bad = {
            "missing": self.doc([]),
            "writable": self.doc([dict(CONF_MOUNT, read_only=False)]),
            "short syntax rw": self.doc(
                ["./apache/crm-access.conf:/etc/apache2/conf-enabled/crm-access.conf"]),
            "other source": self.doc([dict(CONF_MOUNT, source="/srv/x/crm-access.conf")]),
            "other target": self.doc([dict(CONF_MOUNT,
                                           target="/etc/apache2/conf-available/crm-access.conf")]),
            "volume": self.doc([dict(CONF_MOUNT, type="volume")]),
            "twice": self.doc([CONF_MOUNT, CONF_MOUNT]),
            "also on daemon": self.doc([CONF_MOUNT], [CONF_MOUNT]),
            "something else at the target on daemon": self.doc(
                [CONF_MOUNT], [dict(CONF_MOUNT, source="./other.conf")]),
        }
        for why, doc in bad.items():
            with self.subTest(why=why):
                self.assertTrue(policy.rule_access_conf_mount(doc))
        self.assertTrue(policy.rule_access_conf_mount({"services": {}}))

    def test_sources_env_must_be_required(self):
        self.assertEqual(policy.rule_access_sources_env(self.doc([])), [])
        self.assertEqual(policy.rule_access_sources_env(
            self.doc([], env=["CRM_ALLOWED_SOURCES=" + SOURCES])), [])
        for env in ({}, {"CRM_ALLOWED_SOURCES": "${CRM_ALLOWED_SOURCES}"},
                    {"CRM_ALLOWED_SOURCES": "${CRM_ALLOWED_SOURCES:-}"},
                    {"CRM_ALLOWED_SOURCES": "192.0.2.0/24"},
                    ["CRM_ALLOWED_SOURCES"]):
            with self.subTest(env=env):
                self.assertTrue(policy.rule_access_sources_env(self.doc([], env=env)))


class TestConfRules(unittest.TestCase):
    """The access-file rules on small texts."""

    GOOD = '<Location "/">\n    Require ip 127.0.0.1 ::1 ${CRM_ALLOWED_SOURCES}\n</Location>\n'

    def failing(self, text):
        return {r for r, v in policy.check_conf(text).items() if v}

    def test_good_text_and_unquoted_location_pass(self):
        self.assertEqual(self.failing(self.GOOD), set())
        self.assertEqual(self.failing(self.GOOD.replace('"/"', "/")), set())
        self.assertEqual(self.failing("# comment\n\n" + self.GOOD), set())

    def test_deny_by_default_violations(self):
        bad = [
            "",  # no restriction at all
            self.GOOD.replace('"/"', '"/api"'),
            self.GOOD.replace(" ${CRM_ALLOWED_SOURCES}", ""),
            self.GOOD.replace("127.0.0.1 ::1 ", ""),  # healthcheck locked out
            self.GOOD.replace("${CRM_ALLOWED_SOURCES}", "192.0.2.0/24"),
            self.GOOD.replace("</Location>\n", ""),
            self.GOOD + self.GOOD,
            "<LocationMatch \"^/\">\n</LocationMatch>\n" + self.GOOD,
            self.GOOD + "<If \"true\">\n</If>\n",
            self.GOOD + "<Directory /var/www/>\nRequire ip 192.0.2.0/24\n</Directory>\n",
        ]
        for text in bad:
            with self.subTest(text=text):
                self.assertIn("conf_deny_by_default", self.failing(text))

    def test_grants_are_violations(self):
        for extra in ("Require all granted", "Require env CRM_X", "Require host example.test",
                      "Require not ip 192.0.2.1", "Allow from all", "Satisfy Any",
                      "Order allow,deny", "AuthMerging Or", "Require   all \\\n  granted"):
            with self.subTest(extra=extra):
                self.assertIn("conf_no_grant", self.failing(extra + "\n" + self.GOOD))

    def test_header_trust_is_a_violation(self):
        for extra in ("RemoteIPHeader X-Forwarded-For", "RemoteIPTrustedProxy 192.0.2.1",
                      "LoadModule remoteip_module modules/mod_remoteip.so",
                      "SetEnvIf X-Real-IP . ok", "RemoteIPProxyProtocol On"):
            with self.subTest(extra=extra):
                self.assertIn("conf_no_remoteip", self.failing(extra + "\n" + self.GOOD))

    def test_missing_db_service_is_a_violation(self):
        self.assertTrue(policy.rule_db_no_ports({"services": {}}))


class TestMountRules(unittest.TestCase):
    """The mount rules on small documents, short syntax included."""

    IMAGE = ESPOCRM_IMAGE
    GOOD = ["${CRM_DATA_DIR:?x}:/var/www/html/data",
            "${CRM_CUSTOM_DIR:?x}:/var/www/html/custom",
            "${CRM_CLIENT_CUSTOM_DIR:?x}:/var/www/html/client/custom"]

    def doc(self, *volume_lists):
        return {"services": {f"crm-e{i}": {"image": self.IMAGE, "volumes": v}
                             for i, v in enumerate(volume_lists)}}

    def test_short_syntax_good_layout_passes(self):
        doc = self.doc(self.GOOD, self.GOOD)
        for rule in ("no_docroot_mount", "espocrm_mounts", "espocrm_mounts_writable"):
            self.assertEqual(policy.RULES[rule](doc), [], rule)

    def test_short_syntax_docroot_and_ro(self):
        doc = self.doc(["${CRM_DATA_DIR:?x}:/var/www/html"])
        self.assertTrue(policy.rule_no_docroot_mount(doc))
        self.assertTrue(policy.rule_espocrm_mounts(doc))
        ro = self.doc(self.GOOD[:2] + [self.GOOD[2] + ":ro"])
        self.assertEqual(policy.rule_espocrm_mounts(ro), [])
        self.assertEqual(len(policy.rule_espocrm_mounts_writable(ro)), 1)

    def test_docroot_on_any_service_is_a_violation(self):
        doc = {"services": {"crm-db": {"image": MARIADB_IMAGE,
                                       "volumes": ["/srv/x:/var/www/html"]}}}
        self.assertTrue(policy.rule_no_docroot_mount(doc))

    def test_named_volume_literal_path_and_shared_variable_are_violations(self):
        named = self.doc(["crm-data:/var/www/html/data"] + self.GOOD[1:])
        self.assertTrue(policy.rule_espocrm_mounts(named))
        literal = self.doc(["/srv/CRM/runtime/dev/data:/var/www/html/data"] + self.GOOD[1:])
        self.assertTrue(policy.rule_espocrm_mounts(literal))
        shared = self.doc(["${CRM_DATA_DIR:?x}:/var/www/html/custom",
                           self.GOOD[0], self.GOOD[2]])
        self.assertTrue(policy.rule_espocrm_mounts(shared))
        differ = self.doc(self.GOOD, ["${OTHER_DIR:?x}:/var/www/html/data"] + self.GOOD[1:])
        self.assertTrue(policy.rule_espocrm_mounts(differ))
        extra = self.doc(self.GOOD + ["${CRM_X:?x}:/var/www/html/upload"])
        self.assertTrue(policy.rule_espocrm_mounts(extra))

    def test_no_espocrm_service_is_a_violation(self):
        self.assertTrue(policy.rule_espocrm_mounts({"services": {}}))


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
        self.assertEqual(self.svc["crm-app"]["ports"], [BIND])
        self.assertNotIn("127.0.0.1:8180:80", json.dumps(self.doc), "loopback bind removed")
        self.assertNotIn("ports", self.svc["crm-daemon"])
        self.assertNotIn("ports", self.svc["crm-db"])

    def test_healthchecks(self):
        for name in ("crm-app", "crm-db"):
            self.assertTrue(self.svc[name]["healthcheck"]["test"], name)
        # the access file admits loopback for exactly this check
        self.assertIn("http://127.0.0.1/", self.svc["crm-app"]["healthcheck"]["test"])

    def test_allowed_sources_reach_crm_app_only(self):
        self.assertEqual(self.svc["crm-app"]["environment"]["CRM_ALLOWED_SOURCES"], SOURCES)
        for name in ("crm-db", "crm-daemon"):
            self.assertNotIn("CRM_ALLOWED_SOURCES", self.svc[name].get("environment") or {})

    def test_mounts(self):
        def binds(name):
            return {v["target"]: v for v in self.svc[name]["volumes"]}
        expected = {
            "/var/www/html/data": "CRM_DATA_DIR",
            "/var/www/html/custom": "CRM_CUSTOM_DIR",
            "/var/www/html/client/custom": "CRM_CLIENT_CUSTOM_DIR",
        }
        self.assertEqual(len(self.svc["crm-daemon"]["volumes"]), 3)
        self.assertEqual(len(self.svc["crm-app"]["volumes"]), 4)
        self.assertEqual(binds("crm-app")[CONF_MOUNT["target"]], CONF_MOUNT)
        for name in ("crm-app", "crm-daemon"):
            self.assertEqual(set(binds(name)) - {CONF_MOUNT["target"]}, set(expected), name)
            self.assertNotIn("/var/www/html", binds(name))
            for target, var in expected.items():
                vol = binds(name)[target]
                self.assertEqual(vol["type"], "bind")
                self.assertEqual(vol["source"], f"${{{var}:?{var} must be set in the env file}}")
                self.assertFalse(vol.get("read_only", False), f"{name} {target}")
        self.assertEqual(binds("crm-db")["/var/lib/mysql"]["source"],
                         "${CRM_DB_DIR:?CRM_DB_DIR must be set in the env file}")
        self.assertEqual(len(self.svc["crm-db"]["volumes"]), 1)
        for name, svc in self.svc.items():
            for vol in svc["volumes"]:
                self.assertEqual(vol["type"], "bind", name)


class TestLiteralAddresses(unittest.TestCase):
    """No literal non-loopback address in deploy/, scripts/ or tests/ (standing rule)."""

    def test_repository_has_none(self):
        self.assertEqual(policy.scan_literal_ips(), [])

    def scan(self, files):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        return policy.scan_literal_ips(root)

    def test_scan_finds_private_and_documentation_addresses_outside_tests(self):
        # private addresses are assembled at run time so this file holds no literal
        private = ".".join(["10", "20", "30", "40"])
        near_subnet = ".".join(["172", "16", "10", "0"]) + "/25"
        public_v6 = ":".join(["2a00", "1450", "", "1"])
        found = self.scan({
            "scripts/x.py": f"HOST = '{private}' '169.254.1.1'\n",
            "deploy/env.example": "CRM_BIND_IP=192.0.2.10\n",
            "deploy/apache/crm-access.conf": "Require ip 198.51.100.0/24\n",
            "deploy/x.json": '{"dns": "2001:db8::53"}\n',
            "tests/unit/test_x.py": f"BAD = '{private}/24' '{public_v6}'\n",
            "tests/unit/fixtures/compose_bad_x.json": f'"{near_subnet}"\n',
        })
        self.assertEqual(sorted(found), [
            "deploy/apache/crm-access.conf:1: 198.51.100.0/24",
            "deploy/env.example:1: 192.0.2.10",
            "deploy/x.json:1: 2001:db8::53",
            "scripts/x.py:1: " + private,
            "scripts/x.py:1: 169.254.1.1",
            "tests/unit/fixtures/compose_bad_x.json:1: " + near_subnet,
            "tests/unit/test_x.py:1: " + private + "/24",
            "tests/unit/test_x.py:1: " + public_v6,
        ])

    def test_scan_allows_loopback_unspecified_blocks_and_test_data(self):
        found = self.scan({
            "scripts/x.sh": "curl http://127.0.0.1/ [::1] 0.0.0.0 0.0.0.0/0 10.0.0.0/8\n"
                            "VERSION=10.0.12 mariadb:11.4.13\n",
            "deploy/compose.json": '"subnet": "172.16.10.0/24"\n',
            "tests/unit/test_x.py": "'192.0.2.10' '198.51.100.0/24' '203.0.113.5' "
                                    "'2001:db8::53' 0.1.2.3 169.254.1.1 224.0.0.1 "
                                    "240.0.0.1 255.255.255.255\n",
            "tests/unit/fixtures/compose_bad_y.json": '"172.16.10.0/24"\n',
        })
        self.assertEqual(found, [])

    def test_crm_net_subnet_is_allowed_only_in_compose_and_tests(self):
        self.assertEqual(self.scan({"scripts/y.py": "'172.16.10.0/24'\n"}),
                         ["scripts/y.py:1: 172.16.10.0/24"])


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
