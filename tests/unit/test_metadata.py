"""EspoCRM customisation tests (WO CRM-001 items 2 and 5).

Core EspoCRM field and link names below come from the Engineer's knowledge of
EspoCRM conventions; they could not be checked against the 10.0.12 image in
the ForgeV2 sandbox (no network, no Docker).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CUSTOM = os.path.join(REPO, "custom")
ESPO_CUSTOM = os.path.join(CUSTOM, "Espo", "Custom")
RES = os.path.join(ESPO_CUSTOM, "Resources")
sys.path.insert(0, os.path.join(REPO, "scripts"))

import seed_synthetic as seeder  # noqa: E402

CORE_FIELDS = {
    "Account": {"name", "website", "emailAddress", "phoneNumber", "billingAddress",
                "shippingAddress", "description", "assignedUser", "teams", "createdAt",
                "modifiedAt", "billingAddressPostalCode", "billingAddressCity",
                "billingAddressStreet", "billingAddressCountry", "type", "industry"},
    "Contact": {"name", "firstName", "lastName", "emailAddress", "phoneNumber",
                "account", "accounts", "description"},
}
CORE_LINKS = {"Account": {"contacts", "opportunities", "cases", "documents"}}


def load(*parts):
    with open(os.path.join(RES, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def layout_names(layout):
    """Field names referenced by a detail/list/filters layout."""
    names = []
    for item in layout:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and "rows" in item:
            for row in item["rows"]:
                names += [cell["name"] for cell in row if cell]
        elif isinstance(item, dict):
            names.append(item["name"])
    return names


class TestJson(unittest.TestCase):
    def test_every_json_file_parses(self):
        found = 0
        for root, _, files in os.walk(CUSTOM):
            for name in files:
                if name.endswith(".json"):
                    found += 1
                    with self.subTest(file=os.path.relpath(os.path.join(root, name), REPO)):
                        with open(os.path.join(root, name), encoding="utf-8") as fh:
                            json.load(fh)
        self.assertGreaterEqual(found, 10)

    def test_customisation_lives_only_under_custom_espo_custom(self):
        for root, _, files in os.walk(CUSTOM):
            for name in files:
                path = os.path.join(root, name)
                self.assertTrue(path.startswith(ESPO_CUSTOM + os.sep), path)


class TestAccountDefs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defs = load("metadata", "entityDefs", "Account.json")
        cls.fields = cls.defs["fields"]
        cls.links = cls.defs["links"]
        cls.i18n = load("i18n", "en_US", "Account.json")

    def test_required_option_lists(self):
        self.assertEqual([o for o in self.fields["type"]["options"] if o], [
            "Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tier 5", "Prospect",
            "Closed/Ceased Trading"])
        self.assertEqual([o for o in self.fields["industry"]["options"] if o], [
            "Solicitor", "Other Legal Service", "Barrister", "Accountant", "Other"])
        self.assertEqual(self.fields["learningPlatformAccess"]["options"],
                         ["No", "TLP", "Full Access", "E-Course"])
        self.assertEqual(self.fields["learningPlatformAccess"]["type"], "enum")
        self.assertEqual(self.fields["practiceManagementSystem"]["type"], "varchar")

    def test_seeder_uses_the_metadata_options(self):
        self.assertEqual(seeder.TIERS, [o for o in self.fields["type"]["options"] if o])
        self.assertEqual(seeder.INDUSTRIES,
                         [o for o in self.fields["industry"]["options"] if o])
        self.assertEqual(seeder.LEARNING_PLATFORM_ACCESS,
                         self.fields["learningPlatformAccess"]["options"])

    def test_self_link_parent_and_branches(self):
        parent, branches = self.links["parent"], self.links["branches"]
        self.assertEqual((parent["type"], parent["entity"], parent["foreign"]),
                         ("belongsTo", "Account", "branches"))
        self.assertEqual((branches["type"], branches["entity"], branches["foreign"]),
                         ("hasMany", "Account", "parent"))

    def test_links_are_consistent(self):
        for name, link in self.links.items():
            with self.subTest(link=name):
                target = load("metadata", "entityDefs", f"{link['entity']}.json")
                foreign = target["links"][link["foreign"]]
                self.assertEqual(foreign["foreign"], name)
                self.assertEqual(foreign["entity"], "Account")
                field_type = {"belongsTo": "link", "hasMany": "linkMultiple"}[link["type"]]
                self.assertEqual(self.fields[name]["type"], field_type)

    def test_every_custom_field_and_link_has_a_label(self):
        for name in self.fields:
            self.assertIn(name, self.i18n["fields"], f"field label {name}")
        for name in self.links:
            self.assertIn(name, self.i18n["links"], f"link label {name}")
        for name in self.i18n["fields"]:
            self.assertIn(name, self.fields.keys() | CORE_FIELDS["Account"])
        for name in self.i18n["links"]:
            self.assertIn(name, self.links)

    def test_enum_translations_match_options(self):
        enums = {n: f for n, f in self.fields.items() if f["type"] == "enum"}
        self.assertEqual(set(enums), set(self.i18n["options"]))
        for name, field in enums.items():
            self.assertEqual(set(field["options"]), set(self.i18n["options"][name]), name)
            self.assertIn(field["default"], field["options"], name)

    def test_text_filter_fields_exist(self):
        for entity in ("Account", "Contact"):
            defs = load("metadata", "entityDefs", f"{entity}.json")
            known = CORE_FIELDS[entity] | set(defs.get("fields", {}))
            for name in defs["collection"]["textFilterFields"]:
                self.assertIn(name, known, f"{entity}.{name}")
        account = load("metadata", "entityDefs", "Account.json")["collection"]
        self.assertIn("billingAddressPostalCode", account["textFilterFields"])
        self.assertIn("phoneNumber", account["textFilterFields"])


class TestAccountLayouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fields = load("metadata", "entityDefs", "Account.json")["fields"]
        cls.links = load("metadata", "entityDefs", "Account.json")["links"]
        cls.known = CORE_FIELDS["Account"] | set(cls.fields)

    def test_layout_fields_exist(self):
        for layout in ("detail", "list", "listForBranches", "filters"):
            with self.subTest(layout=layout):
                for name in layout_names(load("layouts", "Account", f"{layout}.json")):
                    self.assertIn(name, self.known)
                    if name in self.fields:
                        self.assertNotEqual(self.fields[name]["type"], "linkMultiple",
                                            "linkMultiple fields are panels, not cells")

    def test_required_placement(self):
        detail = layout_names(load("layouts", "Account", "detail.json"))
        listing = layout_names(load("layouts", "Account", "list.json"))
        filters = layout_names(load("layouts", "Account", "filters.json"))
        for name in ("billingAddress", "parent", "type", "industry",
                     "practiceManagementSystem", "learningPlatformAccess"):
            self.assertIn(name, detail)
        self.assertIn("billingAddress", listing)
        for name in ("learningPlatformAccess", "type", "industry"):
            self.assertIn(name, filters)

    def test_branches_relationship_panel(self):
        rel = load("layouts", "Account", "relationships.json")
        names = [r if isinstance(r, str) else r["name"] for r in rel]
        self.assertEqual(names[0], "branches")
        for name in names:
            self.assertIn(name, set(self.links) | CORE_LINKS["Account"])
        panels = load("metadata", "clientDefs", "Account.json")["relationshipPanels"]
        for name, panel in panels.items():
            self.assertIn(name, self.links)
            self.assertTrue(os.path.isfile(os.path.join(RES, "layouts", "Account",
                                                        panel["layout"] + ".json")))


class TestDuplicateChecks(unittest.TestCase):
    def php_class(self, entity):
        cls = load("metadata", "recordDefs", f"{entity}.json")["duplicateWhereBuilderClassName"]
        self.assertTrue(cls.startswith("Espo\\Custom\\"), cls)
        path = os.path.join(CUSTOM, *cls.split("\\")) + ".php"
        self.assertTrue(os.path.isfile(path), path)
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        namespace, _, short = cls.rpartition("\\")
        self.assertIn(f"namespace {namespace};", source)
        self.assertRegex(source, rf"class {short} implements WhereBuilder\b")
        return path, source

    def test_account_checks_name_and_postcode(self):
        _, source = self.php_class("Account")
        self.assertIn("'name'", source)
        self.assertIn("'billingAddressPostalCode'", source)

    def test_contact_checks_email(self):
        _, source = self.php_class("Contact")
        self.assertIn("'emailAddress'", source)
        self.assertNotRegex(source, r"'(firstName|lastName)'")

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_php_lints(self):
        for entity in ("Account", "Contact"):
            path, _ = self.php_class(entity)
            res = subprocess.run(["php", "-l", path], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_no_php_outside_classes(self):
        for root, _, files in os.walk(CUSTOM):
            for name in files:
                if name.endswith(".php"):
                    self.assertTrue(re.search(r"[\\/]Classes[\\/]", root), root)


if __name__ == "__main__":
    unittest.main()
