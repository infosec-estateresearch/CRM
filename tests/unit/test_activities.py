"""Activity and archived-email tests (WO CRM-005 v1.1 item 6).

TestRepository checks the files in the repository against activity_policy.
TestBrokenFixtures breaks each rule with a mutated copy of the repository bundle
and checks that exactly the intended rules fail. TestArchivedEmailTable is the
PHP-free decision table of the archived-email hook.
"""

import copy
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import access_policy
import activity_policy as policy


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


def _completed(old, new):
    def mutate(b):
        assert old in b["completedHook"], old
        b["completedHook"] = b["completedHook"].replace(old, new, 1)
    return mutate


def _call(fn):
    def mutate(b):
        fn(b)
    return mutate


# fixture name -> (mutation of the repository bundle, rules it must break)
BROKEN = {
    "call_sf_id_read_only": (_set(["defs", "Call", "fields", "sfId", "readOnly"], True),
                             {"legacy_fields"}),
    "email_thread_read_only": (_set(["defs", "Email", "fields", "sfThreadIdentifier",
                                     "readOnly"], True), {"legacy_fields"}),
    "task_sf_id_mutable": (_del(["defs", "Task", "fields", "sfId", "readOnlyAfterCreate"]),
                           {"legacy_fields"}),
    "meeting_owner_audited": (_set(["defs", "Meeting", "fields", "sfOwnerId", "audited"], True),
                              {"legacy_fields"}),
    "email_duplicate_message_id": (_set(["defs", "Email", "fields", "messageId"],
                                        {"type": "varchar", "isCustom": True}),
                                   {"legacy_fields", "labels"}),
    "email_no_activity_id": (_del(["defs", "Email", "fields", "sfActivityId"]),
                             {"legacy_fields"}),
    "meeting_sf_id_not_unique": (_del(["defs", "Meeting", "indexes", "sfId"]),
                                 {"unique_indexes"}),
    "email_index_wrong_column": (_set(["defs", "Email", "indexes", "sfId", "columns"],
                                      ["sfActivityId"]), {"unique_indexes"}),
    "meeting_type_missing_option": (_set(["defs", "Meeting", "fields", "meetingType", "options"],
                                         policy.MEETING_TYPES[:-1]),
                                    {"meeting_type", "labels"}),
    "meeting_type_read_only": (_set(["defs", "Meeting", "fields", "meetingType", "readOnly"],
                                    True), {"meeting_type"}),
    "meeting_list_without_type": (_call(lambda b: b["layouts"]["Meeting"]["list"].pop(2)),
                                  {"layouts"}),
    "legacy_panel_expanded": (_del(["layouts", "Call", "detail", 1, "collapsed"]),
                              {"layouts"}),
    "legacy_field_in_main_panel": (
        _call(lambda b: b["layouts"]["Task"]["detail"][0]["rows"].append([{"name": "sfId"}])),
        {"layouts"}),
    "legacy_field_in_list": (_call(lambda b: b["layouts"]["Meeting"]["list"].append(
        {"name": "sfOwnerId"})), {"layouts"}),
    "layout_unknown_field": (_call(lambda b: b["layouts"]["Meeting"]["list"].append(
        {"name": "nosuchField"})), {"layouts"}),
    "email_layout_overridden": (_set(["layouts", "Email", "detail"], [{"rows": []}]),
                                {"layouts"}),
    "label_missing": (_del(["i18n", "Email", "fields", "sfEmailMessageId"]), {"labels"}),
    "no_my_open_tasks": (_set(["dashboards", 0, "dashletsOptions", "d0000501", "title"],
                              "Tasks"), {"dashboard_template"}),
    "no_calendar_dashlet": (_call(lambda b: b["dashboards"][0]["layout"][0]["layout"].pop(1)),
                            {"dashboard_template"}),
    "dashboard_unknown_team": (_set(["dashboards", 0, "deployToTeams"], ["ER Staff"]),
                               {"dashboard_template"}),
    "hook_wrong_interface": (_hook("ProtectArchivedEmail implements BeforeSave",
                                   "ProtectArchivedEmail implements AfterSave"),
                             {"hook_shape"}),
    "hook_bad_request": (_hook("use Espo\\Core\\Exceptions\\Forbidden;",
                               "use Espo\\Core\\Exceptions\\BadRequest;"), {"hook_shape"}),
    "hook_no_throw": (_hook("throw new Forbidden('An archived email is read-only history.');",
                            ""), {"hook_body"}),
    "hook_commented_throw": (_hook("throw new Forbidden(", "// throw new Forbidden("),
                             {"hook_body"}),
    "hook_current_status": (_hook("$entity->getFetched('status')", "$entity->get('status')"),
                            {"hook_body"}),
    "hook_any_api_user": (_hook("User::TYPE_API &&\n"
                                "            $this->user->getUserName() === 'er-import';",
                                "User::TYPE_API;"), {"hook_body"}),
    "hook_other_user_name": (_hook("=== 'er-import'", "=== 'sync-bot'"), {"hook_body"}),
    "hook_body_unprotected": (_hook("        'bodyPlain',\n", ""),
                              {"hook_body", "protected_attributes"}),
    "hook_reply_to_ids_unprotected": (_hook("        'replyToEmailAddressesIds',\n", ""),
                                      {"hook_body", "protected_attributes"}),
    "hook_parent_protected": (_hook("        'status',\n", "        'status',\n        'parentId',\n"),
                              {"hook_body", "protected_attributes"}),
    "hook_duplicate_attribute": (_hook("        'status',\n", "        'status',\n        'name',\n"),
                                 {"hook_body", "protected_attributes"}),
    "task_detail_no_date_completed": (_call(lambda b: b["layouts"]["Task"]["detail"][0]["rows"]
                                            .pop(3)), {"layouts"}),
    "hook_wrong_status": (_hook("!== 'Archived'", "!== 'Sent'"), {"hook_body"}),
    "api_user_renamed": (_set(["apiUsers", 0, "userName"], "er-loader"), {"hook_body"}),
    # CRM-008-G: Task.sfCompletedAt and the completion-date hook.
    "task_completed_at_read_only": (_set(["defs", "Task", "fields", "sfCompletedAt", "readOnly"],
                                         True), {"legacy_fields"}),
    "task_completed_at_missing": (_del(["defs", "Task", "fields", "sfCompletedAt"]),
                                  {"legacy_fields", "layouts"}),
    "task_completed_at_unlabelled": (_del(["i18n", "Task", "fields", "sfCompletedAt"]), {"labels"}),
    "task_completed_at_not_in_legacy": (_set(["layouts", "Task", "detail", 1, "rows", 1, 1], False),
                                        {"layouts"}),
    "completed_hook_core_order": (_completed("$order = 20;", "$order = 9;"),
                                  {"completed_hook_shape"}),
    "completed_hook_after_save": (_completed("CompletedDate implements BeforeSave",
                                            "CompletedDate implements AfterSave"),
                                  {"completed_hook_shape"}),
    "completed_hook_any_status": (_completed("!== 'Completed'", "=== 'Never'"),
                                  {"completed_hook_body"}),
    "completed_hook_every_save": (_completed("if (!$entity->isNew() && "
                                             "!$entity->isAttributeChanged('sfCompletedAt')) {\n"
                                             "            return;\n        }", ""),
                                  {"completed_hook_body"}),
    "completed_hook_new_only": (_completed(" && !$entity->isAttributeChanged('sfCompletedAt')", ""),
                                {"completed_hook_body"}),
    "completed_hook_null_copied": (_completed("if (!$sfCompletedAt) {\n            return;\n        }",
                                              ""), {"completed_hook_body"}),
    "completed_hook_wrong_target": (_completed("set('dateCompleted'", "set('dateEnd'"),
                                    {"completed_hook_body"}),
}


class TestRepository(unittest.TestCase):
    def test_every_rule_holds(self):
        result = policy.check(policy.load_bundle())
        self.assertEqual({r: v for r, v in result.items() if v}, {})

    def test_every_entity_has_a_unique_sf_id_index(self):
        b = policy.load_bundle()
        for entity in policy.ENTITIES:
            self.assertEqual(b["defs"][entity]["indexes"]["sfId"],
                             {"type": "unique", "columns": ["sfId"]}, entity)

    def test_no_legacy_field_is_globally_read_only(self):
        b = policy.load_bundle()
        for entity, fields in policy.LEGACY.items():
            for name in fields:
                self.assertNotIn("readOnly", b["defs"][entity]["fields"][name], name)
            self.assertIs(b["defs"][entity]["fields"]["sfId"]["readOnlyAfterCreate"], True)

    def test_role_field_data_covers_every_legacy_field(self):
        roles = {r["name"]: r for r in access_policy.load_access()["roles"]}
        for entity, fields in policy.LEGACY.items():
            for field in fields:
                for name in access_policy.NON_ADMIN_HUMAN_ROLES:
                    acl = roles[name]["fieldData"][entity][field]
                    self.assertEqual(acl["edit"], "no", f"{name} {entity}.{field}")
                    self.assertEqual(acl["read"], "no" if field == "sfId" else "yes")
                self.assertEqual(roles["ER Import"]["fieldData"][entity][field],
                                 {"read": "yes", "edit": "yes"})

    def test_email_edit_levels(self):
        roles = {r["name"]: r for r in access_policy.load_access()["roles"]}
        self.assertEqual({n: roles[n]["data"]["Email"]["edit"] for n in roles},
                         {"ER Staff": "no", "ER Intake": "no", "ER Manager": "all",
                          "ER Import": "all"})

    def test_protected_attributes_cover_the_work_order(self):
        # body, addresses and dates (WO item 2); parent re-linking stays allowed
        for name in ("body", "bodyPlain", "from", "to", "cc", "dateSent", "subject",
                     "replyTo", "fromEmailAddressId", "toEmailAddressesIds", "attachmentsIds",
                     "messageIdInternal", "sendAt", "deliveryDate"):
            self.assertIn(name, policy.PROTECTED_ATTRIBUTES)
        for name in ("parent", "parentId", "parentType", "parentName", "assignedUserId",
                     "assignedUsersIds", "teamsIds", "usersIds"):
            self.assertNotIn(name, policy.PROTECTED_ATTRIBUTES)

    def test_mirrored_list_is_exactly_the_guarded_set(self):
        self.assertEqual(len(policy.PROTECTED_ATTRIBUTES), 30)
        self.assertEqual(len(set(policy.PROTECTED_ATTRIBUTES)), 30)
        self.assertEqual(set(policy.PROTECTED_ATTRIBUTES), policy.EMAIL_GUARDED_ATTRIBUTES)

    def test_task_completed_at_is_in_the_legacy_panel(self):
        panel = policy.load_bundle()["layouts"]["Task"]["detail"][-1]
        self.assertEqual(panel["rows"][-1], [{"name": "sfCreatedAt"}, {"name": "sfCompletedAt"}])
        self.assertEqual(policy.load_bundle()["i18n"]["Task"]["fields"]["sfCompletedAt"],
                         "Completed in Salesforce")

    def test_task_detail_keeps_date_completed_after_date_end(self):
        rows = policy.load_bundle()["layouts"]["Task"]["detail"][0]["rows"]
        names = [[c.get("name") if isinstance(c, dict) else c for c in r] for r in rows]
        i = names.index(["dateStart", "dateEnd"])
        self.assertEqual(names[i + 1], [False, "dateCompleted"])


class TestBrokenFixtures(unittest.TestCase):
    def test_every_rule_is_broken_by_some_fixture(self):
        self.assertEqual(set().union(*(r for _, r in BROKEN.values())), set(policy.RULES))

    def test_hook_and_mirror_shrunk_together_is_caught(self):
        # if the hook and the mirrored list drop an attribute together, hook_body is
        # satisfied and only the exact-set rule notices
        bundle = policy.load_bundle()
        bundle["hook"] = bundle["hook"].replace("        'attachmentsIds',\n", "", 1)
        original = policy.PROTECTED_ATTRIBUTES
        try:
            policy.PROTECTED_ATTRIBUTES = [a for a in original if a != "attachmentsIds"]
            result = policy.check(bundle)
        finally:
            policy.PROTECTED_ATTRIBUTES = original
        self.assertEqual({r for r, v in result.items() if v}, {"protected_attributes"})

    def test_each_fixture_breaks_exactly_its_rules(self):
        base = policy.load_bundle()
        for name, (mutate, expected) in BROKEN.items():
            with self.subTest(fixture=name):
                bundle = copy.deepcopy(base)
                mutate(bundle)
                result = policy.check(bundle)
                self.assertEqual({r for r, v in result.items() if v}, expected)


class TestArchivedEmailTable(unittest.TestCase):
    """The PHP-free spec of ProtectArchivedEmail (WO CRM-005 item 2)."""

    # isNew, fetched status, admin, ER Import, changed attributes -> allowed
    TABLE = [
        (True, None, False, False, {"body", "status"}, True),        # import creates
        (False, "Sent", False, False, {"body"}, True),               # not archived
        (False, "Draft", False, False, {"status"}, True),
        (False, "Archived", False, False, {"body"}, False),          # AC4: Staff refused
        (False, "Archived", False, False, {"bodyPlain"}, False),
        (False, "Archived", False, False, {"to", "cc"}, False),
        (False, "Archived", False, False, {"dateSent"}, False),
        (False, "Archived", False, False, {"status"}, False),        # cannot un-archive
        (False, "Archived", False, False, {"parentId", "parentType"}, True),  # re-link
        (False, "Archived", False, False, set(), True),
        (False, "Archived", True, False, {"body"}, True),            # admin
        (False, "Archived", False, True, {"body", "messageId"}, True),  # ER Import
    ]

    def test_rule_table(self):
        for *args, want in self.TABLE:
            with self.subTest(case=args):
                self.assertIs(policy.archived_save_allowed(*args), want)

    def test_every_protected_attribute_is_refused_for_people(self):
        for attr in policy.PROTECTED_ATTRIBUTES:
            self.assertFalse(policy.archived_save_allowed(False, "Archived", False, False,
                                                          {attr}), attr)

    def test_exemptions_are_only_admin_or_import(self):
        for admin, imp in itertools.product([True, False], repeat=2):
            self.assertIs(policy.archived_save_allowed(False, "Archived", admin, imp, {"body"}),
                          admin or imp)

    def test_harness_detects_a_wrong_table(self):
        original = policy.archived_save_allowed
        try:
            policy.archived_save_allowed = lambda *a: True
            wrong = [args for *args, want in self.TABLE
                     if policy.archived_save_allowed(*args) is not want]
        finally:
            policy.archived_save_allowed = original
        self.assertEqual(len(wrong), 5)


class TestCompletedDateTable(unittest.TestCase):
    """The spec of PreserveSalesforceCompletedDate (WO CRM-008-G item 2)."""

    SF, NOW, OLD = "2025-05-05 10:00:00", "2026-11-10 12:00:00", "2026-01-01 09:00:00"
    # isNew, status, sfCompletedAt, sfCompletedAt changed, core value -> dateCompleted
    TABLE = [
        (True, "Completed", SF, True, NOW, SF),               # import creates Completed
        (True, "Not Started", SF, True, None, None),          # not Completed: core null
        (True, "Completed", None, False, NOW, NOW),           # no Salesforce date: core now
        (False, "Completed", SF, False, SF, SF),              # unrelated PUT: unchanged
        (False, "Not Started", SF, False, None, None),        # reopened: core null
        (False, "Completed", SF, False, NOW, NOW),            # staff re-completes: core now
        (False, "Completed", SF, True, NOW, SF),              # importer corrects the date
        (False, "Completed", OLD, True, SF, OLD),
    ]

    def test_rule_table(self):
        for *args, want in self.TABLE:
            with self.subTest(case=args):
                self.assertEqual(policy.completed_date_after_save(*args), want)

    def test_harness_detects_a_wrong_table(self):
        original = policy.completed_date_after_save
        try:
            # The probe hook without the refinement: every Completed save takes sfCompletedAt.
            policy.completed_date_after_save = (lambda n, st, sf, ch, core:
                                                sf if st == "Completed" and sf else core)
            wrong = [args for *args, want in self.TABLE
                     if policy.completed_date_after_save(*args) != want]
        finally:
            policy.completed_date_after_save = original
        self.assertEqual(len(wrong), 1)


# Minimal stand-ins for Espo\ORM\Entity, SaveOptions and BeforeSave; the hook file runs
# against them for every row of TestCompletedDateTable.TABLE.
COMPLETED_HARNESS = r"""
namespace Espo\ORM { class Entity {
    public $a; public $new; public $changed;
    function __construct($a, $new, $changed) { $this->a = $a; $this->new = $new; $this->changed = $changed; }
    function get($k) { return $this->a[$k] ?? null; }
    function set($k, $v) { $this->a[$k] = $v; }
    function isNew() { return $this->new; }
    function isAttributeChanged($k) { return in_array($k, $this->changed, true); }
} }
namespace Espo\ORM\Repository\Option { class SaveOptions {} }
namespace Espo\Core\Hook\Hook { interface BeforeSave {
    public function beforeSave(\Espo\ORM\Entity $entity, \Espo\ORM\Repository\Option\SaveOptions $options): void;
} }
namespace {
    require $argv[1];
    $rows = json_decode($argv[2], true);
    $cls = 'Espo\Custom\Hooks\Task\PreserveSalesforceCompletedDate';
    $hook = new $cls();
    $out = [$cls::$order];
    foreach ($rows as [$new, $status, $sf, $changed, $core]) {
        $e = new \Espo\ORM\Entity(['status' => $status, 'sfCompletedAt' => $sf, 'dateCompleted' => $core],
                                    $new, $changed ? ['sfCompletedAt'] : []);
        $hook->beforeSave($e, new \Espo\ORM\Repository\Option\SaveOptions());
        $out[] = $e->get('dateCompleted');
    }
    echo json_encode($out);
}
"""


class TestCompletedHookRuns(unittest.TestCase):
    """Runs the real hook file under php against stubs (skipped when php is missing)."""

    def run_hook(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hook.php")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source)
            rows = [args for *args, _want in TestCompletedDateTable.TABLE]
            res = subprocess.run(["php", "-d", "display_errors=stderr", "-r", COMPLETED_HARNESS,
                                  path, json.dumps(rows)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return json.loads(res.stdout)

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_hook_follows_the_table_after_core(self):
        out = self.run_hook(policy.load_bundle()["completedHook"])
        self.assertEqual(out, [20] + [want for *_a, want in TestCompletedDateTable.TABLE])

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_harness_detects_the_unrefined_probe_hook(self):
        source = policy.load_bundle()["completedHook"].replace(
            "!$entity->isNew() && !$entity->isAttributeChanged('sfCompletedAt')", "false", 1)
        out = self.run_hook(source)
        self.assertNotEqual(out[1:], [want for *_a, want in TestCompletedDateTable.TABLE])


if __name__ == "__main__":
    unittest.main()
