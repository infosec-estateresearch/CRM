"""scripts/check_access.py: the fail-closed LAN access check (CRM-D019).

Bind addresses are RFC 5737 documentation addresses. Allowed sources have to be
RFC 1918, which has no documentation range, so they are derived at run time from
the validator's own RFC 1918 blocks; no private address is written here
(TestLiteralAddresses in test_compose_policy.py enforces that).
"""

import io
import ipaddress
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO, "scripts", "check_access.py")
sys.path.insert(0, os.path.join(REPO, "scripts"))

import check_access as ca  # noqa: E402

TEN, ONE_SEVEN_TWO, ONE_NINE_TWO = ca.RFC1918
CRM_NET = ca.compose_subnets()[0]


def private(block, index, prefix=24):
    """The index-th /prefix network inside an RFC 1918 block, as text."""
    net = ipaddress.ip_network((int(block.network_address) + index * 2 ** (32 - prefix), prefix))
    assert net.subnet_of(block), (block, index, prefix)
    return str(net)


BIND = "192.0.2.10"
SUBNET_A = private(ONE_NINE_TWO, 201)
SUBNET_B = private(TEN, 77 * 256 + 5)
SECRET = "s3cr3t-Value-never-printed"


def env_text(**over):
    values = {"CRM_DB_PASSWORD": SECRET, "CRM_ADMIN_PASSWORD": SECRET,
              "CRM_BIND_IP": BIND,
              "CRM_ALLOWED_SOURCES": f"{SUBNET_A} {SUBNET_B}",
              "CRM_SITE_URL": f"http://{BIND}:8180"}
    values.update(over)
    return "# synthetic env\n" + "".join(f"{k}={v}\n" for k, v in values.items() if v is not None)


class TestHelpers(unittest.TestCase):
    def test_derived_subnets_are_private_and_distinct_from_crm_net(self):
        for net in (SUBNET_A, SUBNET_B):
            n = ipaddress.ip_network(net)
            self.assertTrue(any(n.subnet_of(b) for b in ca.RFC1918), net)
            self.assertFalse(n.overlaps(CRM_NET), net)
        self.assertEqual(ipaddress.ip_network(SUBNET_A).prefixlen, 24)


class TestBindIp(unittest.TestCase):
    def test_accepts_unicast_addresses(self):
        for ip in (BIND, "198.51.100.7", "203.0.113.254"):
            with self.subTest(ip=ip):
                self.assertEqual(ca.validate_bind_ip(ip), [])

    def test_refuses(self):
        refused = {
            "empty": "", "unset": None,
            "unspecified": "0.0.0.0", "this network": "0.1.2.3",
            "loopback": "127.0.0.1", "other loopback": "127.1.2.3",
            "multicast": "224.0.0.1", "broadcast": "255.255.255.255",
            "reserved": "240.0.0.1", "link-local": "169.254.1.1",
            "two addresses": f"{BIND} 198.51.100.7", "comma list": f"{BIND},198.51.100.7",
            "CIDR": f"{BIND}/32", "with port": f"{BIND}:8180",
            "IPv6": "2001:db8::1", "IPv6 loopback": "::1", "hostname": "docker1",
            "octet too big": "192.0.2.256", "leading zero": "192.0.2.010",
            "three octets": "192.0.2", "integer": "3221225994", "spaces": f" {BIND} ",
        }
        for why, ip in refused.items():
            with self.subTest(why=why):
                self.assertTrue(ca.validate_bind_ip(ip))


class TestAllowedSources(unittest.TestCase):
    def test_accepts_one_or_more_private_cidrs_of_at_least_16(self):
        cases = [
            SUBNET_A,
            f"{SUBNET_A} {SUBNET_B}",
            f"  {SUBNET_A}   {SUBNET_B} ",
            private(ONE_SEVEN_TWO, 15, 16),          # the last /16 of 172.16/12
            private(TEN, 1234567, 32),               # a single host
            ca.RFC1918[2].with_prefixlen,            # the whole 192.168/16 block
        ]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(ca.validate_sources(value, [CRM_NET]), [])

    def test_refuses(self):
        refused = {
            "empty": "", "blank": "   ", "unset": None,
            "everyone": "0.0.0.0/0",
            "wider than /16": private(TEN, 1, 15),
            "whole 10/8": TEN.with_prefixlen,
            "whole 172.16/12": ONE_SEVEN_TWO.with_prefixlen,
            "public (documentation) network": "192.0.2.0/24",
            "second entry public": f"{SUBNET_A} 198.51.100.0/24",
            "loopback network": "127.0.0.0/8",
            "bare address without prefix": SUBNET_A.split("/")[0],
            "host bits set": SUBNET_A.replace(".0/24", ".9/24"),
            "prefix out of range": SUBNET_A.replace("/24", "/33"),
            "comma separated": f"{SUBNET_A},{SUBNET_B}",
            "tab separated": f"{SUBNET_A}\t{SUBNET_B}",
            "IPv6": "2001:db8::/64",
            "hostname": "lan-a",
            "Apache keyword": "all",
            "overlaps crm-net": str(CRM_NET),
            "contains crm-net": str(CRM_NET.supernet(new_prefix=16)),
            "inside crm-net": str(list(CRM_NET.subnets(new_prefix=28))[0]),
            "variable reference": "${OTHER}",
        }
        for why, value in refused.items():
            with self.subTest(why=why):
                self.assertTrue(ca.validate_sources(value, [CRM_NET]))

    def test_errors_name_the_position_never_the_value(self):
        errors = ca.validate_sources(f"{SUBNET_A} 198.51.100.0/24", [CRM_NET])
        self.assertEqual(len(errors), 1)
        self.assertIn("entry 2", errors[0])
        self.assertNotIn("198.51.100", errors[0])


class TestSiteUrl(unittest.TestCase):
    def test_accepts(self):
        for url in (f"http://{BIND}:8180", f"http://{BIND}:8180/"):
            with self.subTest(url=url):
                self.assertEqual(ca.validate_site_url(url, BIND), [])

    def test_refuses(self):
        refused = {
            "empty": "", "loopback (old value)": "http://127.0.0.1:8180",
            "other host": "http://198.51.100.7:8180", "hostname": "http://docker1:8180",
            "no port": f"http://{BIND}", "other port": f"http://{BIND}:80",
            "https (not implemented)": f"https://{BIND}:8180",
            "path": f"http://{BIND}:8180/crm", "query": f"http://{BIND}:8180/?a=1",
            "user info": f"http://admin@{BIND}:8180", "bad port": f"http://{BIND}:99999",
            "no scheme": f"{BIND}:8180",
        }
        for why, url in refused.items():
            with self.subTest(why=why):
                self.assertTrue(ca.validate_site_url(url, BIND))
        self.assertTrue(ca.validate_site_url(f"http://{BIND}:8180", None),
                        "no valid bind address: nothing can match")


class TestEnvFile(unittest.TestCase):
    def test_good_file_passes(self):
        self.assertEqual(ca.check(env_text(), {}), [])
        quoted = env_text(CRM_ALLOWED_SOURCES=f'"{SUBNET_A} {SUBNET_B}"',
                          CRM_BIND_IP=f"'{BIND}'")
        self.assertEqual(ca.check(quoted, {}), [])

    def test_missing_duplicate_or_ambiguous_assignments_are_refused(self):
        cases = {
            "bind missing": env_text(CRM_BIND_IP=None),
            "sources missing": env_text(CRM_ALLOWED_SOURCES=None),
            "site url missing": env_text(CRM_SITE_URL=None),
            "assigned twice": env_text() + "CRM_ALLOWED_SOURCES=0.0.0.0/0\n",
            "export form too": env_text() + "export CRM_BIND_IP=0.0.0.0\n",
            "colon form too": env_text() + "CRM_BIND_IP: 0.0.0.0\n",
            "bare name too": env_text() + "CRM_ALLOWED_SOURCES\n",
            "inline comment": env_text(CRM_ALLOWED_SOURCES=f"{SUBNET_A} # lab"),
        }
        for why, text in cases.items():
            with self.subTest(why=why):
                self.assertTrue(ca.check(text, {}))
        only_export = env_text(CRM_BIND_IP=None) + f"export CRM_BIND_IP={BIND}\n"
        self.assertTrue(ca.check(only_export, {}), "non-plain form refused")

    def test_values_in_the_process_environment_are_refused(self):
        for name in ca.NAMES:
            with self.subTest(name=name):
                self.assertTrue(ca.check(env_text(), {name: "anything"}))

    def test_bad_values_are_refused(self):
        for over in ({"CRM_BIND_IP": "0.0.0.0"}, {"CRM_BIND_IP": "127.0.0.1"},
                     {"CRM_ALLOWED_SOURCES": "0.0.0.0/0"}, {"CRM_ALLOWED_SOURCES": ""},
                     {"CRM_SITE_URL": "http://127.0.0.1:8180"}):
            with self.subTest(over=over):
                self.assertTrue(ca.check(env_text(**over), {}))

    def test_unreadable_compose_subnet_fails_closed(self):
        self.assertTrue(ca.check(env_text(), {}, compose_path="/nonexistent/compose.json"))


class TestCommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = os.path.join(self.tmp.name, "runtime", "dev")
        os.makedirs(self.runtime)
        self.write(env_text())

    def write(self, text):
        with open(os.path.join(self.runtime, "env"), "w") as fh:
            fh.write(text)

    def run_cli(self, *args, runtime=None, extra_env=None):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "CRM_RUNTIME_DIR": runtime or self.runtime}
        env.update(extra_env or {})
        res = subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True,
                             text=True, env=env, timeout=30)
        out = res.stdout + res.stderr
        for value in (SECRET, BIND, SUBNET_A, SUBNET_B):
            self.assertNotIn(value, out, "a value from the env file was printed")
        return res

    def test_good_settings_exit_0(self):
        res = self.run_cli("dev")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("access settings OK", res.stdout)
        self.assertIn("2 network(s)", res.stdout)

    def test_dev_guard(self):
        for args in ([], ["prod"], ["beta"], ["DEV"], ["dev "], ["development"], [""],
                     ["dev", "extra"]):
            with self.subTest(args=args):
                res = self.run_cli(*args)
                self.assertEqual(res.returncode, 2)
                self.assertIn("refusing to run", res.stderr)
        prod = os.path.join(self.tmp.name, "runtime", "prod")
        os.makedirs(prod)
        res = self.run_cli("dev", runtime=prod)
        self.assertEqual(res.returncode, 2)
        self.assertIn("not a dev runtime", res.stderr)

    def test_refusals_exit_1_without_printing_values(self):
        self.write(env_text(CRM_BIND_IP="0.0.0.0", CRM_ALLOWED_SOURCES=f"{SUBNET_A} 0.0.0.0/0"))
        res = self.run_cli("dev")
        self.assertEqual(res.returncode, 1)
        self.assertIn("CRM_BIND_IP", res.stderr)
        self.assertIn("CRM_ALLOWED_SOURCES entry 2", res.stderr)
        self.assertEqual(res.stdout, "")

    def test_missing_env_file_and_environment_override(self):
        os.remove(os.path.join(self.runtime, "env"))
        res = self.run_cli("dev")
        self.assertEqual(res.returncode, 1)
        self.assertIn("env file not readable", res.stderr)
        self.write(env_text())
        res = self.run_cli("dev", extra_env={"CRM_BIND_IP": "198.51.100.7"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("process environment", res.stderr)

    def test_main_in_process(self):
        err, out = io.StringIO(), io.StringIO()
        with redirect_stderr(err), redirect_stdout(out):
            code = ca.main(["dev"], {"CRM_RUNTIME_DIR": self.runtime})
        self.assertEqual(code, 0, err.getvalue())


if __name__ == "__main__":
    unittest.main()
