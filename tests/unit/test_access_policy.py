"""Access policy and metadata tests (WO CRM-003 items 1, 2, 5, 6 and 7).

TestDeployedRoles, TestDeployedKeys and TestDeployedHook check the files in the
repository. To show a rule's test can fail, point it at a broken fixture:

    CRM_ACCESS_UNDER_TEST=tests/unit/fixtures/access_bad_staff_deletes_account.json \
        python3 -m unittest discover -s tests/unit -p test_access_policy.py
    CRM_KEYS_UNDER_TEST=tests/unit/fixtures/keys_bad_sfid_not_unique.json \
        python3 -m unittest discover -s tests/unit -p test_access_policy.py
    CRM_HOOK_UNDER_TEST=tests/unit/fixtures/hook_bad_admin_bypass.php \
        python3 -m unittest discover -s tests/unit -p test_access_policy.py

TestBrokenFixtures keeps those demonstrations permanently in the suite.
The hook is checked statically: php is not available in the loop.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

import access_policy as policy

REPO = policy.REPO
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
RES = policy.RES
sys.path.insert(0, os.path.join(REPO, "scripts"))

import provision_access  # noqa: E402

ACCESS_UNDER_TEST = os.environ.get("CRM_ACCESS_UNDER_TEST")
KEYS_UNDER_TEST = os.environ.get("CRM_KEYS_UNDER_TEST")
HOOK_UNDER_TEST = os.environ.get("CRM_HOOK_UNDER_TEST", policy.HOOK_PATH)

# fixture -> the rules it must break (every other rule in its group must still hold)
BROKEN_ACCESS = {
    "access_bad_staff_deletes_account.json": {"no_account_delete", "matches_work_order_table"},
    "access_bad_manager_deletes_account.json": {"no_account_delete", "matches_work_order_table"},
    "access_bad_staff_edits_all_opportunity.json": {"staff_edits_own_opportunity",
                                                    "matches_work_order_table"},
    "access_bad_intake_edits_own_opportunity.json": {"intake_edits_all_opportunity",
                                                     "matches_work_order_table"},
    "access_bad_import_deletes.json": {"import_never_deletes", "matches_work_order_table"},
    "access_bad_import_role_widened.json": {"import_api_only"},
    "access_bad_stream_not_read.json": {"stream_as_read", "matches_work_order_table"},
    "access_bad_invalid_level.json": {"known_levels", "matches_work_order_table"},
    "access_bad_missing_scope.json": {"every_acl_scope_explicit", "matches_work_order_table"},
    "access_bad_missing_lead.json": {"every_acl_scope_explicit", "unused_scopes_disabled",
                                     "matches_work_order_table"},
    "access_bad_unknown_scope.json": {"every_acl_scope_explicit", "matches_work_order_table"},
    "access_bad_boolean_as_levels.json": {"every_acl_scope_explicit", "boolean_scopes",
                                          "matches_work_order_table"},
    "access_bad_unused_scope_enabled.json": {"unused_scopes_disabled", "matches_work_order_table"},
    "access_bad_import_deletes_user.json": {"import_never_deletes", "read_only_reference_scopes",
                                            "matches_work_order_table"},
    "access_bad_staff_import_tool.json": {"boolean_scopes", "matches_work_order_table"},
    "access_bad_import_boolean_enabled.json": {"boolean_scopes", "matches_work_order_table"},
    "access_bad_missing_team.json": {"teams_and_roles_present"},
    "access_bad_sfid_visible.json": {"sf_id_admin_only"},
    "access_bad_staff_edits_sf_owner.json": {"sf_fields_read_only_for_people"},
    "access_bad_intake_provenance_hidden.json": {"sf_fields_read_only_for_people"},
    "access_bad_import_cannot_edit_sf.json": {"import_edits_sf_fields"},
    # CRM-004
    "access_bad_staff_creates_service_type.json": {"service_type_admin_managed",
                                                   "matches_work_order_table"},
    "access_bad_import_deletes_service_type.json": {"service_type_admin_managed",
                                                    "import_never_deletes",
                                                    "matches_work_order_table"},
    "access_bad_staff_edits_legacy_stale.json": {"sf_fields_read_only_for_people"},
    "access_bad_import_cannot_edit_legacy.json": {"import_edits_sf_fields"},
    # CRM-004 round 2: a human role reading Opportunity.sfId
    "access_bad_opportunity_sfid_readable.json": {"sf_id_admin_only"},
    # CRM-005
    "access_bad_email_sfid_readable.json": {"sf_id_admin_only"},
    "access_bad_staff_edits_email.json": {"staff_and_intake_cannot_edit_email",
                                          "matches_work_order_table"},
    "access_bad_manager_edits_task_sf_owner.json": {"sf_fields_read_only_for_people"},
    # CRM-003-F: Currency back on the five-action table (read all), refused by 10.0.12
    "access_bad_currency_all.json": {"level_scopes", "read_only_reference_scopes",
                                     "matches_work_order_table"},
}
BROKEN_KEYS = {
    "keys_bad_sfid_writable.json": {"sf_id_field"},
    "keys_bad_sfid_audited.json": {"sf_id_field"},
    "keys_bad_sfid_maxlength.json": {"sf_id_field"},
    "keys_bad_sfid_not_unique.json": {"sf_id_unique_index"},
    "keys_bad_user_no_index.json": {"sf_id_unique_index"},
    "keys_bad_sfid_read_only.json": {"sf_fields_not_read_only"},
    "keys_bad_owner_read_only.json": {"sf_fields_not_read_only"},
    "keys_bad_created_wrong_type.json": {"sf_provenance_fields"},
    "keys_bad_assigned_user_not_audited.json": {"audited_fields"},
    "keys_bad_contact_email_not_audited.json": {"audited_fields"},
}
BROKEN_HOOK = {
    "hook_bad_no_throw.php": {"hook_throws_forbidden", "hook_body_is_the_guard"},
    "hook_bad_commented_throw.php": {"hook_throws_forbidden", "hook_body_is_the_guard"},
    "hook_bad_wrong_relation.php": {"hook_counts_opportunities", "hook_body_is_the_guard"},
    "hook_bad_admin_bypass.php": {"hook_no_admin_bypass", "hook_body_is_the_guard"},
    "hook_bad_options_skip.php": {"hook_no_admin_bypass", "hook_body_is_the_guard"},
    "hook_bad_before_save.php": {"hook_shape"},
    "hook_bad_count_times_zero.php": {"hook_body_is_the_guard"},
    "hook_bad_false_and.php": {"hook_throws_forbidden", "hook_body_is_the_guard"},
    "hook_bad_early_return.php": {"hook_throws_forbidden", "hook_no_admin_bypass",
                                  "hook_body_is_the_guard"},
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def access_doc():
    return load_json(ACCESS_UNDER_TEST) if ACCESS_UNDER_TEST else policy.load_access()


def keys_doc():
    return load_json(KEYS_UNDER_TEST) if KEYS_UNDER_TEST else policy.load_entity_defs()


class TestDeployedRoles(unittest.TestCase):
    """One test per role rule, against config/access (or CRM_ACCESS_UNDER_TEST)."""

    @classmethod
    def setUpClass(cls):
        cls.doc = access_doc()

    def assertRule(self, rule):
        self.assertEqual(policy.ROLE_RULES[rule](self.doc), [], f"{rule} violated")

    def test_the_three_teams_and_four_roles(self):
        self.assertRule("teams_and_roles_present")

    def test_every_verified_acl_scope_is_explicit_in_every_role(self):
        self.assertRule("every_acl_scope_explicit")

    def test_every_scope_and_action_has_a_valid_level(self):
        self.assertRule("known_levels")

    def test_level_based_scopes_use_only_their_own_actions_and_levels(self):
        self.assertRule("level_scopes")

    def test_unused_crm_scopes_are_disabled(self):
        self.assertRule("unused_scopes_disabled")

    def test_reference_scopes_are_read_only(self):
        self.assertRule("read_only_reference_scopes")

    def test_boolean_scopes_are_as_ruled(self):
        self.assertRule("boolean_scopes")

    def test_stream_access_is_as_for_read(self):
        self.assertRule("stream_as_read")

    def test_no_role_deletes_an_account(self):
        self.assertRule("no_account_delete")

    def test_staff_edits_only_its_own_opportunities(self):
        self.assertRule("staff_edits_own_opportunity")

    def test_intake_edits_all_opportunities(self):
        self.assertRule("intake_edits_all_opportunity")

    def test_import_never_deletes(self):
        self.assertRule("import_never_deletes")

    def test_import_role_is_api_only(self):
        self.assertRule("import_api_only")

    def test_roles_match_the_work_order_table(self):
        self.assertRule("matches_work_order_table")

    def test_sf_id_hidden_from_human_roles(self):
        self.assertRule("sf_id_admin_only")

    def test_staff_and_intake_cannot_edit_email(self):
        self.assertRule("staff_and_intake_cannot_edit_email")

    def test_human_roles_cannot_edit_any_sf_field(self):
        self.assertRule("sf_fields_read_only_for_people")

    def test_import_role_can_write_every_sf_field(self):
        self.assertRule("import_edits_sf_fields")


class TestDeployedKeys(unittest.TestCase):
    """One test per Salesforce key / audit rule, against the custom entityDefs."""

    @classmethod
    def setUpClass(cls):
        cls.defs = keys_doc()

    def assertRule(self, rule):
        self.assertEqual(policy.KEY_RULES[rule](self.defs), [], f"{rule} violated")

    def test_sf_id_is_an_immutable_after_create_unaudited_varchar_18(self):
        self.assertRule("sf_id_field")

    def test_sf_id_has_a_unique_index_named_sf_id(self):
        self.assertRule("sf_id_unique_index")

    def test_sf_owner_and_created_are_typed_custom_fields(self):
        self.assertRule("sf_provenance_fields")

    def test_no_sf_field_is_globally_read_only(self):
        self.assertRule("sf_fields_not_read_only")

    def test_key_firm_and_contact_fields_are_audited(self):
        self.assertRule("audited_fields")


class TestDeployedHook(unittest.TestCase):
    """One test per hook rule, against the hook source (or CRM_HOOK_UNDER_TEST)."""

    @classmethod
    def setUpClass(cls):
        cls.source = policy.load_hook(HOOK_UNDER_TEST)

    def assertRule(self, rule):
        self.assertEqual(policy.HOOK_RULES[rule](self.source), [], f"{rule} violated")

    def test_before_remove_hook_shape(self):
        self.assertRule("hook_shape")

    def test_counts_related_opportunities(self):
        self.assertRule("hook_counts_opportunities")

    def test_throws_forbidden_when_there_are_any(self):
        self.assertRule("hook_throws_forbidden")

    def test_applies_to_admins_too(self):
        self.assertRule("hook_no_admin_bypass")

    def test_before_remove_body_is_exactly_the_guard(self):
        self.assertRule("hook_body_is_the_guard")


class TestScopeSet(unittest.TestCase):
    """The authoritative scope set is well formed and fully covered by the expectations."""

    def test_scope_lists_are_disjoint_and_complete(self):
        self.assertFalse(set(policy.ACL_ENTITY_SCOPES) & set(policy.ACL_BOOLEAN_SCOPES))
        self.assertEqual(len(policy.ACL_SCOPES), len(set(policy.ACL_SCOPES)))
        self.assertEqual(set(policy.MAIN_SCOPES) | set(policy.READ_ONLY_SCOPES)
                         | set(policy.UNUSED_SCOPES) | set(policy.ADMIN_MANAGED_SCOPES),
                         set(policy.ACL_ENTITY_SCOPES))
        self.assertEqual(set(policy.HUMAN_BOOLEAN), set(policy.ACL_BOOLEAN_SCOPES))

    def test_expected_table_covers_every_scope_for_every_role(self):
        for role, data in policy.EXPECTED_DATA.items():
            self.assertEqual(set(data), set(policy.ACL_SCOPES), role)

    def test_a_newly_listed_scope_is_required_of_every_role(self):
        # CRM-004 added ServiceType; a further (hypothetical) scope listed alone must
        # still make every role fail.
        doc = policy.load_access()
        original = list(policy.ACL_ENTITY_SCOPES)
        try:
            policy.ACL_ENTITY_SCOPES.append("FutureScope")
            policy.ACL_SCOPES.append("FutureScope")
            found = policy.rule_every_acl_scope_explicit(doc)
        finally:
            policy.ACL_ENTITY_SCOPES[:] = original
            policy.ACL_SCOPES.remove("FutureScope")
        self.assertEqual(len([v for v in found if "FutureScope" in v]), len(policy.ROLES))

    def test_service_type_is_explicit_in_every_role(self):
        # CRM-004: removing ServiceType from the roles makes every role fail.
        doc = policy.load_access()
        for role in doc["roles"]:
            del role["data"]["ServiceType"]
        found = policy.rule_every_acl_scope_explicit(doc)
        self.assertEqual(len([v for v in found if "ServiceType" in v]), len(policy.ROLES))


class TestLevelScopes(unittest.TestCase):
    """CRM-003-F: Currency's ACL is level-based in EspoCRM 10.0.12 (aclActionList
    [read, edit], aclLevelList [yes, no]); anything else is refused with HTTP 400."""

    def test_currency_is_level_based_with_read_and_edit_yes_no(self):
        self.assertEqual(policy.LEVEL_SCOPES["Currency"],
                         {"actions": ["read", "edit"], "levels": {"yes", "no"}})
        self.assertTrue(set(policy.LEVEL_SCOPES) <= set(policy.ACL_ENTITY_SCOPES))

    def test_read_only_is_expressed_per_scope_kind(self):
        self.assertEqual(policy.read_only_row("Currency"), {"read": "yes", "edit": "no"})
        for scope in set(policy.READ_ONLY_SCOPES) - set(policy.LEVEL_SCOPES):
            self.assertEqual(policy.read_only_row(scope),
                             {"create": "no", "read": "all", "edit": "no", "delete": "no",
                              "stream": "all"}, scope)

    def test_every_role_gives_currency_read_yes_edit_no(self):
        for role in policy.load_access()["roles"]:
            self.assertEqual(role["data"]["Currency"], {"read": "yes", "edit": "no"},
                             role["name"])

    def violations(self, currency):
        doc = policy.load_access()
        for role in doc["roles"]:
            role["data"]["Currency"] = currency
        return {r: v for r, v in policy.check_roles(doc).items() if v}

    def test_the_repository_currency_passes(self):
        self.assertEqual(self.violations({"read": "yes", "edit": "no"}), {})

    def test_refused_currency_shapes(self):
        cases = {
            "read all": {"read": "all", "edit": "no"},
            "unknown action delete": {"read": "yes", "edit": "no", "delete": "no"},
            "unknown action stream": {"read": "yes", "edit": "no", "stream": "yes"},
            "edit missing": {"read": "yes"},
            "edit all": {"read": "yes", "edit": "all"},
            "true instead of levels": True,
        }
        for label, currency in cases.items():
            with self.subTest(case=label):
                found = self.violations(currency)
                self.assertIn("level_scopes", found)
                self.assertEqual(len(found["level_scopes"]), len(policy.ROLES))
                self.assertIn("read_only_reference_scopes", found)

    def test_edit_yes_is_a_valid_level_but_not_read_only(self):
        found = self.violations({"read": "yes", "edit": "yes"})
        self.assertNotIn("level_scopes", found)
        self.assertIn("read_only_reference_scopes", found)

    def test_import_deleting_currency_is_refused(self):
        doc = policy.load_access()
        _roles = {r["name"]: r for r in doc["roles"]}
        _roles[policy.IMPORT]["data"]["Currency"] = {"read": "yes", "edit": "no", "delete": "all"}
        self.assertTrue(policy.rule_import_never_deletes(doc))
        self.assertTrue(policy.rule_level_scopes(doc))


class TestBrokenFixtures(unittest.TestCase):
    """Each rule fails on a fixture that breaks it, and only the intended rules fail."""

    def check_group(self, prefix, broken, rules, load, check):
        self.assertEqual(set().union(*broken.values()), set(rules))
        self.assertEqual(set(broken), {f for f in os.listdir(FIXTURES) if f.startswith(prefix)})
        for fixture, expected in broken.items():
            with self.subTest(fixture=fixture):
                result = check(load(os.path.join(FIXTURES, fixture)))
                self.assertEqual({r for r, v in result.items() if v}, expected)

    def test_access_fixtures(self):
        self.check_group("access_bad_", BROKEN_ACCESS, policy.ROLE_RULES, load_json,
                         policy.check_roles)

    def test_key_fixtures(self):
        self.check_group("keys_bad_", BROKEN_KEYS, policy.KEY_RULES, load_json, policy.check_keys)

    def test_hook_fixtures(self):
        self.check_group("hook_bad_", BROKEN_HOOK, policy.HOOK_RULES, policy.load_hook,
                         policy.check_hook)

    def test_the_repository_passes_every_rule(self):
        for result in (policy.check_roles(policy.load_access()),
                       policy.check_keys(policy.load_entity_defs()),
                       policy.check_hook(policy.load_hook())):
            self.assertEqual({r: v for r, v in result.items() if v}, {})


# Core fields: CRM-003 only switches field history on ({"audited": true}). The one
# exception (CRM-006, PL-authorised): Contact.opportunityRole may also set its options, so
# the enquiry contact-role column accepts the Salesforce roles. Any other key is refused.
CORE_OVERRIDE_EXCEPTIONS = {("Contact", "opportunityRole"): {"audited", "options"},
                            # CRM-008: maxLength only, raised to 255 so the real Title fits.
                            ("Contact", "title"): {"maxLength"}}


def core_override_violations(entity, name, field):
    allowed = CORE_OVERRIDE_EXCEPTIONS.get((entity, name))
    if allowed is None:
        return [] if field == {"audited": True} else [
            f"{entity}.{name} overrides {k}" for k in sorted(set(field) - {"audited"}) or ["audited"]]
    out = [f"{entity}.{name} overrides {k}" for k in sorted(set(field) - allowed)]
    if "audited" in field and field["audited"] is not True:
        out.append(f"{entity}.{name} audited must be true")
    options = field.get("options")
    if "options" in field and not (isinstance(options, list) and all(isinstance(o, str) for o in options)):
        out.append(f"{entity}.{name} options must be a list of strings")
    return out


class TestMetadataConsistency(unittest.TestCase):
    """Fields, indexes and layouts agree (WO CRM-003 item 7)."""

    @classmethod
    def setUpClass(cls):
        cls.defs = policy.load_entity_defs()

    def test_index_columns_are_fields_of_the_entity(self):
        for entity, defs in self.defs.items():
            for name, index in defs.get("indexes", {}).items():
                for column in index["columns"]:
                    with self.subTest(entity=entity, index=name):
                        self.assertIn(column, defs["fields"])
                        self.assertEqual(defs["fields"][column]["type"], "varchar")

    def test_new_fields_define_their_type_and_overrides_only_audit(self):
        for entity, defs in self.defs.items():
            for name, field in defs["fields"].items():
                with self.subTest(field=f"{entity}.{name}"):
                    if name.startswith("sf"):
                        self.assertTrue(field.get("isCustom"))
                        self.assertNotIn("readOnly", field)
                        self.assertEqual(field.get("readOnlyAfterCreate"), name == "sfId" or None)
                        self.assertFalse(field.get("audited"))
                        self.assertTrue(field.get("layoutMassUpdateDisabled"))
                        self.assertTrue(field.get("layoutListDisabled"))
                    elif "type" not in field:
                        self.assertEqual(core_override_violations(entity, name, field), [])

    def test_core_override_refuses_other_keys_on_opportunity_role(self):
        # CRM-006 exception: Contact.opportunityRole may carry options (and audited) only.
        defs = policy.load_entity_defs(overrides={
            "Contact": os.path.join(FIXTURES, "overrides_bad_opportunity_role_required.json")})
        field = defs["Contact"]["fields"]["opportunityRole"]
        self.assertEqual(core_override_violations("Contact", "opportunityRole", field),
                         ["Contact.opportunityRole overrides required"])
        self.assertEqual(core_override_violations("Contact", "emailAddress", {"options": ["x"]}),
                         ["Contact.emailAddress overrides options"])
        self.assertEqual(core_override_violations("Contact", "opportunityRole", {"options": "Other"}),
                         ["Contact.opportunityRole options must be a list of strings"])

    def test_crm001_account_definitions_preserved(self):
        fields = self.defs["Account"]["fields"]
        self.assertEqual(fields["learningPlatformAccess"]["options"],
                         ["", "No", "TLP", "Full Access", "E-Course"])
        self.assertEqual(fields["parent"]["type"], "link")
        self.assertEqual(self.defs["Account"]["links"]["branches"]["foreign"], "parent")
        self.assertIn("billingAddressPostalCode",
                      self.defs["Account"]["collection"]["textFilterFields"])
        self.assertEqual(self.defs["Contact"]["collection"]["textFilterFields"],
                         ["name", "emailAddress", "phoneNumber"])

    def test_account_detail_shows_the_salesforce_keys_in_their_own_panel(self):
        detail = load_json(os.path.join(RES, "layouts", "Account", "detail.json"))
        panels = {p.get("label"): [c["name"] for row in p["rows"] for c in row if c]
                  for p in detail}
        self.assertEqual(sorted(panels["Salesforce"]), ["sfCreatedAt", "sfId", "sfOwnerId"])
        for label, names in panels.items():
            if label != "Salesforce":
                self.assertFalse({n for n in names if n.startswith("sf")}, label)

    def test_sf_fields_appear_in_no_list_filter_or_edit_layout(self):
        layouts = os.path.join(RES, "layouts")
        for entity in os.listdir(layouts):
            for name in os.listdir(os.path.join(layouts, entity)):
                if name == "detail.json":
                    continue
                with self.subTest(layout=f"{entity}/{name}"):
                    with open(os.path.join(layouts, entity, name), encoding="utf-8") as fh:
                        text = fh.read()
                    if entity == "ServiceType":
                        # CRM-004: ServiceType.sfValue is the Salesforce picklist value
                        # it maps, reference data rather than a Salesforce key.
                        text = text.replace('"sfValue"', '""')
                    self.assertNotRegex(text, r'"sf[A-Z]\w*"')

    def test_layouts_only_for_allowlisted_entities(self):
        self.assertTrue(set(os.listdir(os.path.join(RES, "layouts"))) <= {
            "User", "Account", "Contact", "Opportunity", "ServiceType",  # CRM-004 adds two
            "Call", "Meeting", "Task"})  # CRM-005

    def test_role_field_data_names_real_fields(self):
        defs = dict(self.defs, **{e: load_json(  # CRM-004 Opportunity, CRM-005 activities
            os.path.join(policy.ENTITY_DEFS_DIR, f"{e}.json"))
            for e in ["Opportunity"] + policy.ACTIVITIES + ["Email"]})
        for role in policy.load_access()["roles"]:
            for entity, fields in role["fieldData"].items():
                for name in fields:
                    with self.subTest(role=role["name"], field=f"{entity}.{name}"):
                        self.assertIn(name, defs[entity]["fields"])

    def test_role_documents_use_only_espocrm_role_attributes(self):
        config = provision_access.load_config()  # raises on unknown attributes
        for role in config["roles"]:
            self.assertEqual(set(role) - {"name"} - set(provision_access.ROLE_DOC_KEYS),
                             set(provision_access.ROLE_ATTRIBUTES),
                             role["name"])

    def test_role_info_is_documentation_only_and_never_sent(self):
        # CRM-008 change 8: EspoCRM has no Role.info attribute.
        self.assertNotIn("info", provision_access.ROLE_ATTRIBUTES)
        for role in provision_access.load_config()["roles"]:
            self.assertNotIn("info", provision_access.role_desired(role), role["name"])


class TestSettingsFile(unittest.TestCase):
    """CRM-008 change 2: the Settings provision_access.py enforces on the target."""

    def test_settings_are_gbp_and_national_phone_numbers(self):
        settings = provision_access.load_settings()
        self.assertEqual(settings, {"currencyList": ["GBP"], "defaultCurrency": "GBP",
                                    "baseCurrency": "GBP", "phoneNumberInternational": False})

    def test_settings_file_lives_in_config(self):
        self.assertEqual(os.path.relpath(provision_access.SETTINGS_FILE, REPO),
                         os.path.join("config", "settings.json"))

    def test_importer_currency_is_in_the_currency_list(self):
        mapping = load_json(os.path.join(REPO, "load", "contract", "mapping.json"))
        settings = provision_access.load_settings()
        self.assertEqual(mapping["currency"], settings["defaultCurrency"])
        self.assertIn(mapping["currency"], settings["currencyList"])


class TestHookFile(unittest.TestCase):
    def test_hook_lives_at_the_espocrm_custom_hook_path(self):
        rel = os.path.relpath(policy.HOOK_PATH, os.path.join(REPO, "custom"))
        self.assertEqual(rel.split(os.sep), ["Espo", "Custom", "Hooks", "Account",
                                             "RestrictDeleteWithEnquiries.php"])
        self.assertTrue(policy.load_hook().startswith("<?php\n"))

    def test_only_the_account_hook_exists(self):
        hooks = os.path.join(REPO, "custom", "Espo", "Custom", "Hooks")
        found = [os.path.relpath(os.path.join(r, f), hooks)
                 for r, _, files in os.walk(hooks) for f in files]
        self.assertEqual(sorted(found), [os.path.join("Account", "RestrictDeleteWithEnquiries.php"),
                                         os.path.join("Email", "ProtectArchivedEmail.php"),
                                         os.path.join("Opportunity", "RequireLossReason.php"),
                                         os.path.join("Task", "PreserveSalesforceCompletedDate.php")])

    def test_braces_balance(self):
        code = policy._code(policy.load_hook())
        code = re.sub(r"'(?:[^'\\]|\\.)*'", "''", code)
        for open_, close in ("{}", "()", "[]"):
            self.assertEqual(code.count(open_), code.count(close), open_ + close)

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_php_lints(self):
        res = subprocess.run(["php", "-l", policy.HOOK_PATH], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def run_hook(self, path):
        """Run beforeRemove against stubs of the EspoCRM interfaces it uses
        (signatures as verified in 10.0.12) for 0, 1 and 3 related enquiries."""
        res = subprocess.run(["php", "-d", "display_errors=stderr", "-r", HOOK_HARNESS, path],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return res.stdout.split()

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_hook_refuses_only_when_the_firm_has_enquiries(self):
        self.assertEqual(self.run_hook(policy.HOOK_PATH),
                         ["0:allowed", "1:forbidden", "3:forbidden"])

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_harness_detects_a_hook_that_does_not_refuse(self):
        self.assertEqual(self.run_hook(os.path.join(FIXTURES, "hook_bad_no_throw.php")),
                         ["0:allowed", "1:allowed", "3:allowed"])


# Minimal stand-ins for Espo\ORM\Entity, EntityManager, RemoveOptions, Forbidden
# and BeforeRemove. The relation stub throws unless asked for Account.opportunities.
HOOK_HARNESS = r"""
namespace Espo\ORM {
    interface Entity {}
    class EntityManager {
        public function __construct(public int $n) {}
        public function getRDBRepository(string $type) {
            return new class($this->n, $type) {
                public function __construct(public int $n, public string $type) {}
                public function getRelation(\Espo\ORM\Entity $e, string $link) {
                    if ($this->type !== 'Account' || $link !== 'opportunities') {
                        throw new \LogicException("unexpected relation {$this->type}.{$link}");
                    }
                    return new class($this->n) {
                        public function __construct(public int $n) {}
                        public function count(): int { return $this->n; }
                    };
                }
            };
        }
    }
}
namespace Espo\ORM\Repository\Option { class RemoveOptions {} }
namespace Espo\Core\Exceptions { class Forbidden extends \Exception {} }
namespace Espo\Core\Hook\Hook {
    interface BeforeRemove {
        public function beforeRemove(\Espo\ORM\Entity $entity,
            \Espo\ORM\Repository\Option\RemoveOptions $options): void;
    }
}
namespace {
    require $argv[1];
    $entity = new class implements \Espo\ORM\Entity {};
    foreach ([0, 1, 3] as $n) {
        $hook = new \Espo\Custom\Hooks\Account\RestrictDeleteWithEnquiries(
            new \Espo\ORM\EntityManager($n));
        try {
            $hook->beforeRemove($entity, new \Espo\ORM\Repository\Option\RemoveOptions());
            echo "$n:allowed\n";
        } catch (\Espo\Core\Exceptions\Forbidden $e) {
            echo "$n:forbidden\n";
        }
    }
}
"""


if __name__ == "__main__":
    unittest.main()
