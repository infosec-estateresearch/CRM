"""Enquiry tests (WO CRM-004 v1.1 item 9).

TestRepository checks the files in the repository against enquiry_policy.
TestBrokenFixtures breaks each rule with a mutated copy of the repository bundle
and checks that exactly the intended rules fail. TestLossReasonTable is the
PHP-free decision table of the loss-reason hook.
"""

import copy
import itertools
import json
import os
import unittest

import access_policy
import enquiry_policy as policy


# "Cond" followed by two colons; spelt out so the CRM-001 literal-address scan does
# not read it as an IPv6 literal.
COND = "Cond" + ":" * 2


def _fields(b):
    return b["defs"]["fields"]


def _set(path, value):
    def mutate(b):
        node = b
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return mutate


def _del(path):
    def mutate(b):
        node = b
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]
    return mutate


def _hook(old, new):
    def mutate(b):
        assert old in b["hook"], old
        b["hook"] = b["hook"].replace(old, new, 1)
    return mutate


def _filter(name, old, new):
    def mutate(b):
        assert old in b["filters"][name], old
        b["filters"][name] = b["filters"][name].replace(old, new, 1)
    return mutate


def _layout(name, mutate_layout):
    def mutate(b):
        mutate_layout(b["layouts"][name])
    return mutate


# fixture name -> (mutation of the repository bundle, rules it must break)
BROKEN = {
    "stage_closed_won_kept": (_set(["defs", "fields", "stage", "options"],
                                   ["Enquiry", "Quoted", "Instructed", "Lost", "Closed Won"]),
                              {"stage", "labels"}),
    "stage_wrong_probability": (_set(["defs", "fields", "stage", "probabilityMap", "Lost"], 10),
                                {"stage"}),
    "stage_default_quoted": (_set(["defs", "fields", "stage", "default"], "Quoted"), {"stage"}),
    "loss_reason_missing_option": (_set(["defs", "fields", "lossReason", "options"],
                                        policy.LOSS_REASONS[:-1]),
                                   {"custom_fields", "labels"}),
    "service_type_link_to_account": (_set(["defs", "links", "serviceType", "entity"], "Account"),
                                     {"custom_fields"}),
    "close_date_not_audited": (_set(["defs", "fields", "closeDate", "audited"], False),
                               {"audited"}),
    "sf_id_read_only": (_set(["defs", "fields", "sfId", "readOnly"], True), {"legacy_fields"}),
    "legacy_stale_read_only": (_set(["defs", "fields", "legacyStale", "readOnly"], True),
                               {"legacy_fields"}),
    "sf_id_not_unique": (_del(["defs", "indexes", "sfId"]), {"legacy_fields"}),
    "sf_id_mutable": (_del(["defs", "fields", "sfId", "readOnlyAfterCreate"]), {"legacy_fields"}),
    "service_type_name_not_unique": (_del(["serviceTypeDefs", "indexes", "name"]),
                                     {"service_type_entity"}),
    "service_type_no_acl": (_set(["serviceTypeScope", "acl"], False), {"service_type_entity"}),
    "last_stage_closed_lost": (_set(["logic", "fields", "lastStage", "visible", "conditionGroup",
                                     0, "value"], "Closed Lost"), {"dynamic_logic"}),
    "loss_reason_not_required": (_del(["logic", "fields", "lossReason", "required"]),
                                 {"dynamic_logic"}),
    "layout_unknown_field": (_layout("list", lambda l: l.append({"name": "nosuchField"})),
                             {"layout_fields_exist", "layouts_as_specified"}),
    "quick_create_extra_field": (_layout("detailSmall",
                                         lambda l: l[0]["rows"].append([{"name": "stage"}])),
                                 {"layouts_as_specified"}),
    "legacy_panel_expanded": (_layout("detail", lambda l: l[2].pop("collapsed")),
                              {"layouts_as_specified"}),
    "legacy_field_in_quick_create": (
        _layout("detailSmall", lambda l: l[0]["rows"][2].append({"name": "sfStageName"})),
        {"layouts_as_specified", "legacy_not_in_edit_layouts"}),
    "open_filter_includes_stale": (_filter("openEnquiries",
                                           f"{COND}equal({COND}column('legacyStale'), false)",
                                           f"{COND}equal({COND}column('stage'), 'Enquiry')"),
                                   {"primary_filters"}),
    "my_filter_not_mine": (_filter("myOpenEnquiries",
                                   f"{COND}equal({COND}column('assignedUserId'), "
                                   "$this->user->getId())",
                                   f"{COND}equal({COND}column('stage'), 'Enquiry')"),
                           {"primary_filters"}),
    "default_filter_not_open": (_set(["client", "defaultFilterData", "primary"], "won"),
                                {"primary_filters"}),
    "filter_not_registered": (_del(["select", "primaryFilterClassNameMap", "legacyStale"]),
                              {"primary_filters"}),
    "scope_not_relabelled": (_set(["global", "scopeNames", "Opportunity"], "Opportunity"),
                             {"labels"}),
    "amount_label": (_set(["i18n", "fields", "amount"], "Amount"), {"labels"}),
    "hook_wrong_interface": (_hook("RequireLossReason implements BeforeSave",
                                   "RequireLossReason implements AfterSave"),
                             {"hook_shape"}),
    "hook_no_throw": (_hook("throw new BadRequest('A lost enquiry needs a loss reason.');", ""),
                      {"hook_body"}),
    "hook_api_bypass_without_flag": (_hook("if ($legacyMissing && $isImportUser)",
                                           "if ($legacyMissing || $isImportUser)"),
                                     {"hook_body"}),
    "hook_flag_alone_exempts": (_hook("if ($legacyMissing && $unchanged)",
                                      "if ($legacyMissing)"), {"hook_body"}),
    "hook_commented_throw": (_hook("throw new BadRequest(", "// throw new BadRequest("),
                             {"hook_body"}),
    "hook_wrong_stage": (_hook("!== 'Lost'", "!== 'Closed Lost'"), {"hook_body"}),
    # CRM-004 round 2
    "amount_required": (_set(["defs", "fields", "amount", "required"], True),
                        {"fee_and_close_date_optional"}),
    "close_date_required_by_core": (_del(["defs", "fields", "closeDate", "required"]),
                                    {"fee_and_close_date_optional"}),
    "hook_any_api_user_exempt": (_hook("User::TYPE_API &&\n"
                                       "            $this->user->getUserName() === 'er-import';",
                                       "User::TYPE_API;"), {"hook_body"}),
    "hook_other_user_name": (_hook("=== 'er-import'", "=== 'sync-bot'"), {"hook_body"}),
    "api_user_renamed": (_set(["apiUsers", 0, "userName"], "er-loader"), {"hook_body"}),
    "account_link_not_relabelled": (_del(["accountI18n", "links", "opportunities"]), {"labels"}),
    "contact_link_not_relabelled": (_set(["contactI18n", "links", "opportunities"],
                                         "Opportunities"), {"labels"}),
}


class TestRepository(unittest.TestCase):
    def test_every_rule_holds(self):
        result = policy.check(policy.load_bundle())
        self.assertEqual({r: v for r, v in result.items() if v}, {})

    def test_stage_options_and_probabilities(self):
        stage = _fields(policy.load_bundle())["stage"]
        self.assertEqual(stage["options"], ["Enquiry", "Quoted", "Instructed", "Lost"])
        self.assertEqual(stage["probabilityMap"],
                         {"Enquiry": 10, "Quoted": 50, "Instructed": 100, "Lost": 0})
        # the core won/lost filters derive from the map: exactly one won, one lost stage
        self.assertEqual([s for s, p in stage["probabilityMap"].items() if p == 100],
                         ["Instructed"])
        self.assertEqual([s for s, p in stage["probabilityMap"].items() if p == 0], ["Lost"])

    def test_no_legacy_field_is_globally_read_only(self):
        fields = _fields(policy.load_bundle())
        for name in policy.LEGACY_FIELDS:
            self.assertNotIn("readOnly", fields[name], name)
        self.assertIs(fields["sfId"]["readOnlyAfterCreate"], True)

    def test_human_roles_cannot_edit_legacy_fields(self):
        roles = {r["name"]: r for r in access_policy.load_access()["roles"]}
        for name in access_policy.NON_ADMIN_HUMAN_ROLES:
            for field in policy.LEGACY_FIELDS:
                self.assertEqual(roles[name]["fieldData"]["Opportunity"][field]["edit"], "no",
                                 f"{name} {field}")
        for field in policy.LEGACY_FIELDS:
            self.assertEqual(roles["ER Import"]["fieldData"]["Opportunity"][field],
                             {"read": "yes", "edit": "yes"})

    def test_service_type_admin_managed_in_every_role(self):
        roles = {r["name"]: r for r in access_policy.load_access()["roles"]}
        for name in access_policy.NON_ADMIN_HUMAN_ROLES:
            self.assertEqual(roles[name]["data"]["ServiceType"],
                             {"create": "no", "read": "all", "edit": "no", "delete": "no",
                              "stream": "all"}, name)
        self.assertEqual(roles["ER Import"]["data"]["ServiceType"]["delete"], "no")
        self.assertEqual(roles["ER Import"]["data"]["ServiceType"]["create"], "yes")

    def test_fee_and_close_date_not_required_but_audited(self):
        fields = _fields(policy.load_bundle())
        for name in ("amount", "closeDate"):
            self.assertIs(fields[name]["required"], False, name)
            self.assertIs(fields[name]["audited"], True, name)

    def test_hook_exempts_only_the_named_import_user(self):
        b = policy.load_bundle()
        self.assertEqual(policy.import_user_names(b), ["er-import"])
        self.assertIn("getUserName() === 'er-import'", b["hook"])

    def test_contact_metadata_unchanged(self):
        # The Salesforce contact roles are stored raw by the importer; Contact's
        # opportunityRole options are not changed by CRM-004.
        with open(os.path.join(policy.RES, "metadata", "entityDefs", "Contact.json"),
                  encoding="utf-8") as fh:
            contact = json.load(fh)
        self.assertNotIn("opportunityRole", contact.get("fields", {}))

    def test_every_new_json_file_names_only_opportunity_or_service_type(self):
        for kind in ("entityDefs", "clientDefs", "logicDefs", "selectDefs", "scopes"):
            for name in os.listdir(os.path.join(policy.RES, "metadata", kind)):
                self.assertIn(name[:-5], {"Account", "Contact", "User", "Opportunity",
                                          "ServiceType", "Call", "Meeting", "Task",
                                          "Email"},  # CRM-005
                              f"{kind}/{name}")


class TestBrokenFixtures(unittest.TestCase):
    def test_every_rule_is_broken_by_some_fixture(self):
        self.assertEqual(set().union(*(r for _, r in BROKEN.values())), set(policy.RULES))

    def test_each_fixture_breaks_exactly_its_rules(self):
        base = policy.load_bundle()
        for name, (mutate, expected) in BROKEN.items():
            with self.subTest(fixture=name):
                bundle = copy.deepcopy(base)
                mutate(bundle)
                result = policy.check(bundle)
                self.assertEqual({r for r, v in result.items() if v}, expected)


class TestLossReasonTable(unittest.TestCase):
    """The PHP-free spec of RequireLossReason (WO CRM-004 item 4, D3)."""

    def test_rule_table(self):
        for *args, want in self.TABLE:
            with self.subTest(case=args):
                self.assertIs(policy.loss_reason_allowed(*args), want)

    # stage, reason, legacyMissing, stageChanged, reasonChanged, apiUser -> allowed
    TABLE = [
            ("Quoted", "", False, True, False, False, True),
            ("Instructed", "", False, True, False, False, True),
            ("Lost", "Price", False, True, True, False, True),
            ("Lost", "", False, True, False, False, False),     # AC4: refused
            ("Lost", "", False, False, False, False, False),    # unflagged, unchanged
            ("Lost", "", False, True, False, True, False),      # importer, no flag
            ("Lost", "", True, False, False, False, True),      # AC4: legacy record saves
            ("Lost", "", True, True, False, False, False),      # person sets Lost on flagged
            ("Lost", "", True, False, True, False, False),      # person clears the reason
            ("Lost", "", True, True, True, True, True),         # importer creates legacy Lost
    ]

    def test_never_allows_lost_without_reason_unless_flagged(self):
        for changed_s, changed_r, api in itertools.product([True, False], repeat=3):
            self.assertFalse(policy.loss_reason_allowed("Lost", "", False, changed_s,
                                                        changed_r, api))

    def test_harness_detects_a_wrong_table(self):
        original = policy.loss_reason_allowed
        try:
            policy.loss_reason_allowed = lambda *a: True
            wrong = [args for *args, want in self.TABLE
                     if policy.loss_reason_allowed(*args) is not want]
        finally:
            policy.loss_reason_allowed = original
        self.assertEqual(len(wrong), 5)


if __name__ == "__main__":
    unittest.main()
