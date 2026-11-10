"""CRM-002-T: ``hostcheck.parse_legacy_env`` reads the two target values with the ELT
consumer's literal semantics. Synthetic values only."""

import random
import re
import string
import unittest

from crm_migrate import hostcheck as hc

from .fake_salesforce import SENTINEL

USER, PASS = "NIF_SRC_SALESFORCE_USER", "NIF_SRC_SALESFORCE_PASS"
NEWLY_ACCEPTED = ";&|<>()#!*?{}[]~^%@=+,.:/-_"
ALPHABET = string.ascii_letters + string.digits + NEWLY_ACCEPTED
ERROR_RE = re.compile(r"\Alegacy env file(?: line [0-9]+)?:? [A-Za-z -]+(?:; file refused)?\Z")


def reference_load(text):
    """The consumer's algorithm, verbatim (file opened in text mode; CR is refused before this)."""
    env = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env.setdefault(key.strip(), value.strip())   # the first definition wins for the consumer
    return env


def creds_text(user="u", password="p"):
    return f"{USER}={user}\n{PASS}={password}\n"


class DifferentialTest(unittest.TestCase):
    SEED = 20261110
    N = 400

    def corpus(self):
        rng = random.Random(self.SEED)
        fillers = ("# comment", "", "   ", "OTHER=x y z", "garbage line", "export OTHER=1",
                   "NIF_DB_HOST = db.example.test", "#NIF_SRC_SALESFORCE_PASS=commented",
                   "X='open quote", "Y=\"a b\"", "NIF_SRC_SALESFORCE_PASSWORD=other",
                   "  # indented comment \\")
        for i in range(self.N):
            def value():
                v = "".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 40)))
                return v
            user, password = value(), value()
            if i % 10 == 0:
                password = "#" + password                  # a value starting with #
            if i % 10 == 1:
                password = password + "=" + value()        # = inside the value
            if i % 10 == 2:
                password = password + "#"                  # # after the value, kept literal
            if i % 10 == 3:
                password = "".join(NEWLY_ACCEPTED)         # every newly accepted character
            pad = lambda: rng.choice(("", " ", "  ", "\t"))  # noqa: E731
            lines = [rng.choice(fillers) for _ in range(rng.randint(0, 4))]
            lines.append(f"{pad()}{USER}{pad()}={pad()}{user}{pad()}")
            lines += [rng.choice(fillers) for _ in range(rng.randint(0, 3))]
            lines.append(f"{pad()}{PASS}{pad()}={pad()}{password}{pad()}")
            lines += [rng.choice(fillers) for _ in range(rng.randint(0, 3))]
            if rng.random() < 0.5:
                lines.reverse()
            yield "\n".join(lines) + rng.choice(("\n", "")), user, password

    def test_agrees_with_reference_loader(self):
        accepted = 0
        for n, (text, user, password) in enumerate(self.corpus()):
            with self.subTest(entry=n):
                ref = reference_load(text)
                creds, errors = hc.parse_legacy_env(text)
                self.assertEqual(errors, [])
                self.assertEqual(creds, {"username": ref[USER], "password": ref[PASS]})
                self.assertEqual(creds, {"username": user, "password": password})
                accepted += 1
        self.assertEqual(accepted, self.N)

    def test_refused_entries_are_the_ambiguous_ones(self):
        rng = random.Random(self.SEED + 1)
        for n in range(100):
            bad = rng.choice("'\"`$\\ \t\x00\x07\x7f ​")
            base = "".join(rng.choice(ALPHABET) for _ in range(8))
            password = base[:4] + bad + base[4:]
            text = creds_text("u", password)
            with self.subTest(entry=n, bad=hex(ord(bad))):
                creds, errors = hc.parse_legacy_env(text)
                self.assertIsNone(creds)
                self.assertTrue(errors)
                # the reference would read something; the CRM refuses rather than guess
                self.assertIn(PASS, reference_load(text))


class LiteralValueTest(unittest.TestCase):
    def parse_pass(self, line):
        return hc.parse_legacy_env(f"{USER}=u\n{line}\n")

    def ok(self, line, expected):
        self.assertEqual(self.parse_pass(line), ({"username": "u", "password": expected}, []))
        self.assertEqual(reference_load(f"{USER}=u\n{line}\n")[PASS], expected)

    def test_each_newly_accepted_character(self):
        for ch in NEWLY_ACCEPTED:
            with self.subTest(ch=ch):
                self.ok(f"{PASS}=a{ch}b", f"a{ch}b")
                self.ok(f"{PASS}={ch}b", f"{ch}b")
                self.ok(f"{PASS}=a{ch}", f"a{ch}")

    def test_equals_inside_value(self):
        self.ok(f"{PASS}=a=b", "a=b")
        self.ok(f"{PASS}==ab", "=ab")
        self.ok(f"{PASS}=ab==", "ab==")

    def test_hash_is_literal(self):
        self.ok(f"{PASS}=#ab", "#ab")
        self.ok(f"{PASS}=ab#", "ab#")
        self.ok(f"{PASS}=a#b", "a#b")

    def test_surrounding_whitespace_is_stripped(self):
        self.ok(f"  {PASS}  =  ab  ", "ab")
        self.ok(f"\t{PASS}=\tab\t", "ab")

    def test_inline_comment_is_not_a_comment(self):
        # the consumer reads "abc # x"; that holds whitespace, so it is refused
        self.assertEqual(reference_load(f"{USER}=u\n{PASS}=abc # x\n")[PASS], "abc # x")
        self.assertEqual(self.parse_pass(f"{PASS}=abc # x"), (None, ["legacy env file line 2: refused-character"]))
        self.assertEqual(self.parse_pass(f"{PASS}=abc#x"), ({"username": "u", "password": "abc#x"}, []))

    def test_commented_target_is_skipped(self):
        self.assertEqual(hc.parse_legacy_env(f"#{PASS}=old\n" + creds_text()), ({"username": "u", "password": "p"}, []))
        self.assertEqual(hc.parse_legacy_env(f"  # {PASS}=old\n" + creds_text()), ({"username": "u", "password": "p"}, []))

    def test_other_lines_not_interpreted(self):
        for other in ("garbage line", "X = a b c", "export OTHER=$(x)", "Y='open", "Z=\"a", "W=`x`",
                      f"{PASS}X=other", f"X{PASS}=other", "=novalue-key"):
            with self.subTest(other=other):
                self.assertEqual(hc.parse_legacy_env(other + "\n" + creds_text()),
                                 ({"username": "u", "password": "p"}, []))


class RefusalTest(unittest.TestCase):
    def refused(self, text, expected):
        creds, errors = hc.parse_legacy_env(text)
        self.assertIsNone(creds)
        self.assertEqual(errors, expected)
        for e in errors:
            self.assertRegex(e, ERROR_RE)
            self.assertNotIn(SENTINEL, e)

    def test_refused_characters(self):
        cases = ["'", '"', "`", "$", "\\x", " ", "\t", "\x00", "\x01", "\x1b", "\x7f", "\x9f",
                 " ", " ", "​", "­", "﻿", "\U000e0001"]
        for ch in cases:
            with self.subTest(ch=ascii(ch)):
                self.refused(creds_text("u", SENTINEL + ch + SENTINEL),
                             ["legacy env file line 2: refused-character"])
                self.refused(creds_text(SENTINEL + ch + SENTINEL, "p"),
                             ["legacy env file line 1: refused-character"])

    def test_quoted_values(self):
        for raw in (f"'{SENTINEL}'", f'"{SENTINEL}"', f"'{SENTINEL}", f"{SENTINEL}'"):
            with self.subTest(raw=raw):
                self.refused(creds_text("u", raw), ["legacy env file line 2: refused-character"])

    def test_export_prefix(self):
        self.refused(f"export {USER}=u\n{PASS}=p\n",
                     ["legacy env file line 1: export-prefix", "legacy env file: missing-user"])
        self.refused(f"{USER}=u\nexport\t{PASS}={SENTINEL}\n",
                     ["legacy env file line 2: export-prefix", "legacy env file: missing-pass"])
        self.refused(creds_text("u", SENTINEL) + f"export {PASS}={SENTINEL}\n",
                     ["legacy env file line 3: export-prefix"])
        # "export" for an unrelated name is not interpreted
        self.assertEqual(hc.parse_legacy_env("export OTHER=1\n" + creds_text())[1], [])

    def test_duplicate(self):
        self.refused(creds_text("u", SENTINEL) + f"{PASS}={SENTINEL}x\n",
                     ["legacy env file line 3: duplicate-definition"])
        self.refused(creds_text("u", SENTINEL) + f"  {PASS} = {SENTINEL}\n",
                     ["legacy env file line 3: duplicate-definition"])
        self.refused(f"{USER}=\n" + creds_text(),     # an empty first definition still counts
                     ["legacy env file line 1: empty-value", "legacy env file line 2: duplicate-definition"])

    def test_missing_and_empty(self):
        self.refused(f"{USER}=u\n", ["legacy env file: missing-pass"])
        self.refused(f"{PASS}={SENTINEL}\n", ["legacy env file: missing-user"])
        self.refused("", ["legacy env file: missing-user", "legacy env file: missing-pass"])
        self.refused(f"{USER}=u\n{PASS}=\n", ["legacy env file line 2: empty-value"])
        self.refused(f"{USER}=u\n{PASS}=   \n", ["legacy env file line 2: empty-value"])
        self.refused(f"{USER}=u\n{PASS}\n", ["legacy env file: missing-pass"])     # no "=": skipped

    def test_cr(self):
        self.refused(creds_text("u", SENTINEL).replace("\n", "\r\n"),
                     ["legacy env file line 1 holds a carriage return; file refused"])
        self.refused(creds_text("u", SENTINEL + "\r" + SENTINEL),
                     ["legacy env file line 2 holds a carriage return; file refused"])

    def test_other_line_breaks(self):
        for ch in "\x0b\x0c\x1c\x1d\x1e\x85  ":
            with self.subTest(ch=ascii(ch)):
                # the consumer's splitlines would end the value at ch; a LF reader would not
                self.refused(creds_text("u", SENTINEL + ch + SENTINEL),
                             ["legacy env file line 2 holds a line break other than LF; file refused"])
                self.refused("OTHER=a" + ch + f"{PASS}=x\n" + creds_text("u", SENTINEL),
                             ["legacy env file line 1 holds a line break other than LF; file refused"])

    def test_continuation(self):
        self.refused(creds_text("u", SENTINEL + "\\"),
                     ["legacy env file line 2 ends with a line continuation; file refused"])
        self.refused("OTHER=x\\\n" + creds_text("u", SENTINEL),
                     ["legacy env file line 1 ends with a line continuation; file refused"])
        self.assertEqual(hc.parse_legacy_env("# ends with \\\n" + creds_text())[1], [])

    def test_not_text(self):
        self.refused(b"x", ["legacy env file is not text"])

    def test_messages_hold_no_value_or_character_class(self):
        texts = [creds_text(SENTINEL + c + SENTINEL, SENTINEL + c + SENTINEL) for c in "'\"`$ \t\x00 "]
        texts += [creds_text("u", SENTINEL) + f"{PASS}={SENTINEL}\n", f"export {PASS}={SENTINEL}\n",
                  creds_text("u", SENTINEL + "\\"), creds_text("u", SENTINEL + "\r")]
        seen = set()
        for text in texts:
            _, errors = hc.parse_legacy_env(text)
            self.assertTrue(errors)
            for e in errors:
                self.assertNotIn(SENTINEL, e)
                self.assertNotRegex(e.lower(), r"quote|space|backslash|dollar|control|printable|unicode|tab")
                seen.add(e.split(": ")[-1])
        self.assertIn("refused-character", seen)


if __name__ == "__main__":
    unittest.main()
