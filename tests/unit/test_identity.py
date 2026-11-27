"""CRM-IDINT-001R unit tests: identity integrity.

No EspoCRM, Docker or browser runs here. What is executed:
- the route matrix definition (completeness, consistency with the roles);
- the custom PHP (IdentityPolicy, IdentityAuditor, IdentityGuard, the hooks and the record
  hooks) under php, in the order the platform runs it, with the platform's REAL hook
  interfaces and options loaded from the pinned reference (CRM_PLATFORM_REFERENCE) and
  only the heavy collaborators stood in (tests/unit/php/); gated on php and on that
  variable; mutations of the PHP prove the checks fail when a control is removed;
- the release settings of 3.6 and the deploy step that applies and reads them back
  (a fake docker, like tests/unit/test_beta.py);
- the read-only primary-firm report of 3.3 against a fake transport;
- static checks of the metadata, roles and hook files.
"""

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
CUSTOM = os.path.join(REPO, "custom", "Espo", "Custom")
RES = os.path.join(CUSTOM, "Resources")
PHP_DIR = os.path.join(os.path.dirname(__file__), "php")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(REPO, "tests", "acceptance"))
sys.path.insert(0, os.path.dirname(__file__))

import crm_api  # noqa: E402
import identity_matrix as matrix  # noqa: E402
import identity_report  # noqa: E402
import release_settings  # noqa: E402
import test_beta as tb  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "acceptance_identity_under_test", os.path.join(REPO, "tests", "acceptance", "test_identity.py"))
_module = importlib.util.module_from_spec(_spec)
sys.modules["acceptance_identity_under_test"] = _module
_spec.loader.exec_module(_module)

HAVE_PHP = bool(shutil.which("php"))
REFERENCE = os.environ.get("CRM_PLATFORM_REFERENCE", "")
NEEDS_REFERENCE = unittest.skipUnless(
    HAVE_PHP and REFERENCE, "needs php and CRM_PLATFORM_REFERENCE (the pinned EspoCRM sources)")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def load(*parts):
    return json.loads(read(*parts))


def roles():
    return {r["name"]: r for r in load(REPO, "config", "access", "roles.json")["roles"]}


# ---- A1: the matrix ----------------------------------------------------------------------------------

class TestMatrix(unittest.TestCase):
    def test_the_matrix_is_complete(self):
        self.assertEqual(matrix.problems(), [])
        self.assertEqual(len(matrix.table()), len(matrix.RELATIONSHIPS) * len(matrix.ROUTES) * len(matrix.KINDS))

    def test_a_missing_cell_fails_the_check(self):
        table = matrix.table()
        del table[("parentFirm", "delete", "admin")]
        self.assertTrue([p for p in matrix.problems(table) if "missing cell" in p])
        table = matrix.table()
        table[("parentFirm", "delete", "admin")] = ("refused", "")
        self.assertTrue([p for p in matrix.problems(table) if "no reason" in p])
        table[("parentFirm", "delete", "admin")] = ("sometimes", "x")
        self.assertTrue([p for p in matrix.problems(table) if "unknown expectation" in p])
        table = matrix.table()
        table[("parentFirm", "delete", "root")] = ("refused", "x")
        self.assertTrue([p for p in matrix.problems(table) if "unknown cell" in p])

    def test_an_unknown_axis_member_is_refused(self):
        for cell in (("nope", "delete", "admin"), ("parentFirm", "nope", "admin"), ("parentFirm", "delete", "nope")):
            with self.assertRaises(KeyError):
                matrix.expectation(*cell)

    def test_the_axes_are_those_of_the_work_order(self):
        self.assertEqual(set(matrix.RELATIONSHIPS), {"parentFirm", "primaryFirm", "contactFirmLink",
                                                     "enquiryFirm", "successor"})
        for route in ("record_create", "record_edit", "link_owner_side", "link_other_side", "unlink_owner_side",
                      "unlink_other_side", "bulk_link", "mass_update", "delete", "mass_delete", "merge",
                      "csv_import", "supplied_id", "retire", "supersede", "cleanup_job"):
            self.assertIn(route, matrix.ROUTES)
        self.assertEqual(matrix.KINDS, ["admin", "staff", "intake", "manager", "import"])

    def test_kinds_are_the_roles_of_the_access_config(self):
        by_name = roles()
        for kind, role in matrix.ROLE_OF_KIND.items():
            self.assertIn(role, by_name, kind)
        self.assertEqual(set(matrix.HUMAN_KINDS) | {"import"}, set(matrix.ROLE_OF_KIND))
        allowed = {kind for kind, role in matrix.ROLE_OF_KIND.items()
                   if kind in matrix.HUMAN_KINDS and by_name[role]["massUpdatePermission"] == "yes"}
        self.assertEqual(set(matrix.MASS_UPDATE_KINDS), {"admin"} | allowed)
        self.assertEqual(by_name["ER Import"]["massUpdatePermission"], "no")

    def test_destructive_routes_are_refused_for_every_cell(self):
        for rel in matrix.RELATIONSHIPS:
            for kind in matrix.KINDS:
                for route in ("delete", "mass_delete", "merge", "csv_import", "bulk_link", "cleanup_job"):
                    self.assertEqual(matrix.expectation(rel, route, kind)[0], "refused", (rel, route, kind))

    def test_a_supplied_identifier_is_refused_or_performed_with_its_own_identifier_never_used(self):
        for rel in matrix.RELATIONSHIPS:
            for kind in matrix.KINDS:
                self.assertEqual(matrix.expectation(rel, "supplied_id", kind)[0], "either", (rel, kind))
        ev = _module.evaluate
        self.assertEqual(ev("either", 1, 2, 0, 1, [], ["new"], refusals=None, identifier_used=True)[0], False)
        self.assertEqual(ev("either", 1, 2, 0, 1, [], ["new"], identifier_used=False)[0], True)

    def test_every_editing_kind_has_a_performing_route_for_each_relationship(self):
        for rel in matrix.RELATIONSHIPS:
            for kind in matrix.KINDS:
                self.assertTrue([r for r in matrix.ROUTES if matrix.expectation(rel, r, kind)[0] == "performed"],
                                (rel, kind))

    def test_the_acceptance_suite_drives_every_route(self):
        source = read(REPO, "tests", "acceptance", "test_identity.py")
        for route in matrix.ROUTES:
            self.assertIn(f'"{route}"', source.replace("'", '"') + ' "cleanup_job" ', route)
        self.assertIn("matrix.cells()", source)
        for name in ("test_a01", "test_a02", "test_a03", "test_a04", "test_a05", "test_a06", "test_a07",
                     "test_a08", "test_a09", "test_a10"):
            self.assertIn(f"def {name}", source)


# ---- the access roles ----------------------------------------------------------------------------------

class TestRoles(unittest.TestCase):
    def test_no_role_deletes_a_firm_or_a_contact(self):
        for name, role in roles().items():
            for scope in ("Account", "Contact"):
                self.assertEqual(role["data"][scope]["delete"], "no", f"{name} {scope}")

    def test_the_manager_still_deletes_enquiries_and_activities(self):
        data = roles()["ER Manager"]["data"]
        self.assertEqual(data["Opportunity"]["delete"], "all")
        for scope in ("Call", "Meeting", "Task"):
            self.assertEqual(data[scope]["delete"], "all")

    def test_no_other_role_level_of_the_manager_changed(self):
        data = roles()["ER Manager"]["data"]
        self.assertEqual({k: data["Contact"][k] for k in ("create", "read", "edit", "stream")},
                         {"create": "yes", "read": "all", "edit": "all", "stream": "all"})

    def test_every_role_reads_the_audit_and_nobody_changes_it(self):
        for name, role in roles().items():
            self.assertEqual(role["data"]["IdentityAudit"],
                             {"create": "no", "read": "all", "edit": "no", "delete": "no", "stream": "all"}, name)

    def test_import_scope_is_off_for_every_human_role(self):
        for kind in matrix.HUMAN_KINDS:
            self.assertIs(roles()[matrix.ROLE_OF_KIND[kind]]["data"]["Import"], False)


# ---- metadata ---------------------------------------------------------------------------------------

class TestMetadata(unittest.TestCase):
    def test_csv_import_and_merge_are_off_in_the_scopes(self):
        for entity in ("Account", "Contact", "Opportunity"):
            self.assertIs(load(RES, "metadata", "scopes", f"{entity}.json")["importable"], False, entity)
        for entity in ("Account", "Contact"):
            self.assertIs(load(RES, "metadata", "scopes", f"{entity}.json")["mergeable"], False, entity)

    def test_the_audit_entity_is_an_acl_controlled_custom_entity_with_a_controller(self):
        scope = load(RES, "metadata", "scopes", "IdentityAudit.json")
        self.assertTrue(scope["entity"] and scope["acl"] and scope["isCustom"])
        self.assertIs(scope["importable"], False)
        self.assertIs(scope["stream"], False)
        self.assertTrue(os.path.isfile(os.path.join(CUSTOM, "Controllers", "IdentityAudit.php")))

    def test_audit_fields(self):
        fields = load(RES, "metadata", "entityDefs", "IdentityAudit.json")["fields"]
        for name in ("occurredAt", "actorId", "actorName", "relationship", "recordType", "recordId",
                     "previousValue", "newValue"):
            self.assertIn(name, fields)
        self.assertEqual(set(fields["relationship"]["options"]),
                         {"parentFirm", "primaryFirm", "contactFirmLink", "enquiryFirm", "successor", "status"})
        policy = read(CUSTOM, "Classes", "Identity", "IdentityPolicy.php")
        for rel in fields["relationship"]["options"]:
            self.assertRegex(policy, rf"= '{rel}';")

    def test_status_and_successor_on_firms_and_contacts(self):
        for entity in ("Account", "Contact"):
            defs = load(RES, "metadata", "entityDefs", f"{entity}.json")
            self.assertEqual(defs["fields"]["identityStatus"]["options"], ["active", "retired", "superseded"])
            self.assertEqual(defs["fields"]["identityStatus"]["default"], "active")
            self.assertEqual(defs["links"]["successor"], {"type": "belongsTo", "entity": entity,
                                                          "foreign": "predecessors", "isCustom": True})
            self.assertEqual(defs["links"]["predecessors"]["foreign"], "successor")

    def test_wip_item_and_its_handler_are_unchanged(self):
        client = read(RES, "metadata", "clientDefs", "Account.json")
        self.assertIn('"openWip"', client)
        self.assertIn("custom:handlers/account-open-wip", client)

    # The hooks the platform really calls (Core/Hook/Hook): before hooks only for save and remove,
    # after hooks for the relations. CRM-IDINT-001R: no before-relation hook exists for custom code.
    IDENTITY_HOOKS = {
        "Account": ("BeforeSave", "AfterSave", "BeforeRemove", "AfterRelate", "AfterUnrelate", "AfterMassRelate"),
        "Contact": ("BeforeSave", "AfterSave", "BeforeRemove", "AfterRelate", "AfterUnrelate", "AfterMassRelate"),
        "Opportunity": ("BeforeSave", "AfterSave", "AfterRelate", "AfterUnrelate"),
    }

    def test_the_hook_files_are_present_for_every_route_that_changes_an_identity(self):
        for entity, kinds in self.IDENTITY_HOOKS.items():
            for kind in kinds:
                path = os.path.join(CUSTOM, "Hooks", entity, f"Identity{kind}.php")
                self.assertTrue(os.path.isfile(path), path)
                self.assertRegex(read(path), rf"class Identity{kind} implements {kind}\b")
            present = sorted(f for f in os.listdir(os.path.join(CUSTOM, "Hooks", entity)) if f.startswith("Identity"))
            self.assertEqual(present, sorted(f"Identity{k}.php" for k in kinds), entity)
        self.assertTrue(os.path.isfile(os.path.join(CUSTOM, "Hooks", "IdentityAudit", "ProtectIdentityAudit.php")))

    def test_no_hook_names_a_before_relation_interface_the_platform_lacks(self):
        for root, _, files in os.walk(CUSTOM):
            for name in files:
                if name.endswith(".php"):
                    text = read(root, name)
                    for missing in ("BeforeRelate", "BeforeUnrelate", "BeforeMassRelate"):
                        self.assertNotRegex(text, rf"Hook\\{missing}\b|\b{missing}\b", f"{name}: {missing}")

    def test_hook_order_runs_save_hooks_last_and_relation_hooks_first(self):
        for entity, kinds in self.IDENTITY_HOOKS.items():
            for kind in kinds:
                text = read(CUSTOM, "Hooks", entity, f"Identity{kind}.php")
                match = re.search(r"public static int \$order = (\d+);", text)
                if kind in ("BeforeSave", "AfterSave"):
                    self.assertTrue(match and int(match.group(1)) > 9, f"{entity} {kind}")
                elif kind.startswith("After") and kind != "AfterSave":
                    self.assertTrue(match and int(match.group(1)) < 9, f"{entity} {kind}")

    def test_r2_entity_definitions_declare_the_transaction_the_repository_and_the_system_write_restriction(self):
        for entity in ("Account", "Contact", "Opportunity"):
            defs = load(RES, "metadata", "entityDefs", f"{entity}.json")
            self.assertIs(defs["transactionalSave"], True, entity)
            self.assertEqual(defs["repositoryClassName"], "Espo\\Custom\\Classes\\Identity\\IdentityRepository", entity)
        for entity in ("Account", "Contact", "Opportunity", "AccountContact"):
            self.assertEqual(load(RES, "metadata", "entityAcl", f"{entity}.json"), {"systemWriteForbidden": True}, entity)
        self.assertEqual(load(RES, "metadata", "recordDefs", "Opportunity.json")["actions"]["merge"], {"disabled": True})

    def test_record_defs_wire_the_record_hooks_and_the_platform_switches(self):
        hooks = "Espo\\Custom\\Classes\\Identity\\RecordHooks\\"
        for entity in ("Account", "Contact"):
            defs = load(RES, "metadata", "recordDefs", f"{entity}.json")
            self.assertEqual(defs["actions"]["merge"], {"disabled": True}, entity)
            self.assertEqual(defs["massActions"]["delete"], {"disabled": True}, entity)
            self.assertEqual(defs["beforeLinkHookClassNameList"], [hooks + "BeforeLink"])
            self.assertEqual(defs["beforeUnlinkHookClassNameList"], [hooks + "BeforeUnlink"])
            self.assertEqual(defs["beforeDeleteHookClassNameList"], [hooks + "BeforeDelete"])
            self.assertEqual(defs["beforeCreateHookClassNameList"], [hooks + "BeforeCreateInput"])
            self.assertEqual(defs["beforeUpdateHookClassNameList"], [hooks + "BeforeUpdateInput"])
            self.assertIn("duplicateWhereBuilderClassName", defs)
            for link, rel in defs["relationships"].items():
                self.assertIs(rel["massLink"], False, f"{entity}.{link}")
        links = {e: set(load(RES, "metadata", "recordDefs", f"{e}.json")["relationships"])
                 for e in ("Account", "Contact")}
        self.assertEqual(links["Account"], {"branches", "parent", "contacts", "contactsPrimary", "opportunities",
                                            "successor", "predecessors"})
        self.assertEqual(links["Contact"], {"accounts", "account", "successor", "predecessors"})
        audit = load(RES, "metadata", "recordDefs", "IdentityAudit.json")
        self.assertEqual(audit["massActions"], {"delete": {"disabled": True}, "update": {"disabled": True}})
        self.assertEqual(audit["beforeDeleteHookClassNameList"], [hooks + "BeforeDelete"])

    def test_the_cleanup_job_cannot_remove_audit_history_of_identity_scopes(self):
        for scope in ("Account", "Contact", "Opportunity", "IdentityAudit"):
            self.assertIs(load(RES, "metadata", "scopes", f"{scope}.json")["preserveAuditLog"], True, scope)

    def test_the_old_merge_controllers_are_gone(self):
        # Merge is refused by recordDefs actions.merge.disabled (Core/Action/ActionFactory), not by a controller.
        for name in ("Account.php", "Contact.php"):
            self.assertFalse(os.path.exists(os.path.join(CUSTOM, "Controllers", name)), name)

    def test_no_identity_php_has_an_administrator_or_service_account_exemption(self):
        files = [os.path.join(r, f) for r, _, fs in os.walk(CUSTOM) for f in fs
                 if f.endswith(".php") and ("Identity" in r or f.startswith("Identity")
                                            or f in ("ProtectIdentityAudit.php",))]
        self.assertGreaterEqual(len(files), 25)
        for path in files:
            code = re.sub(r"/\*.*?\*/", "", read(path), flags=re.S)
            for forbidden in ("isAdmin", "isApi", "getType()", "er-import", "skipHooks", "SKIP_HOOKS"):
                self.assertNotIn(forbidden, code, f"{os.path.basename(path)}: {forbidden}")

    def test_the_audit_option_is_never_set_outside_the_auditor(self):
        for root, _, files in os.walk(CUSTOM):
            for name in files:
                if name.endswith(".php") and name not in ("IdentityAuditor.php", "IdentityPolicy.php",
                                                           "ProtectIdentityAudit.php"):
                    self.assertNotIn("AUDIT_WRITE_OPTION", read(root, name), name)
                    self.assertNotIn("identityAuditWrite", read(root, name), name)

    @unittest.skipUnless(HAVE_PHP, "php not installed")
    def test_every_identity_php_lints(self):
        count = 0
        for root, _, files in os.walk(CUSTOM):
            for name in files:
                if name.endswith(".php"):
                    count += 1
                    res = subprocess.run(["php", "-l", os.path.join(root, name)], capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertGreaterEqual(count, 30)


# ---- the PHP, executed -------------------------------------------------------------------------------

def run_harness(custom_dir):
    res = subprocess.run(["php", "-d", "display_errors=stderr", os.path.join(PHP_DIR, "identity_harness.php"),
                          REFERENCE, custom_dir], capture_output=True, text=True, timeout=300)
    return res.returncode, res.stdout, res.stderr


def parse(stdout):
    return dict(line.split("=", 1) for line in stdout.splitlines() if "=" in line)


@NEEDS_REFERENCE
class TestIdentityPhp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, out, err = run_harness(CUSTOM)
        assert code == 0 and not err.strip(), err
        cls.out = out
        cls.result = parse(out)
        cls.expected = parse(read(PHP_DIR, "identity_expected.txt"))

    def test_every_scenario_is_as_expected(self):
        self.assertEqual(set(self.result), set(self.expected))
        for name in sorted(self.expected):
            with self.subTest(scenario=name):
                self.assertEqual(self.result[name], self.expected[name])

    def outcome(self, name):
        return self.result[name].split("|")[0]

    def audits(self, name):
        return [a for a in self.result[name].split("|", 1)[1].split(",") if a]

    def test_delete_mass_delete_and_merge_routes_are_refused_even_for_an_administrator(self):
        for name in ("remove.Account", "remove.Account_admin", "remove.Account_record_route",
                     "remove.Account_record_hook_on_its_own", "remove.Contact", "remove.Contact_admin",
                     "remove.Contact_record_route", "remove.Contact_record_hook_on_its_own"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertEqual(self.result["remove_Account_rows_left"], "1")
        self.assertEqual(self.result["remove_Contact_rows_left"], "1")
        self.assertEqual(self.outcome("remove.Opportunity_is_not_an_identity_record"), "ok")

    def test_creation_works_for_every_account_and_a_supplied_identifier_is_never_used(self):
        # P4: the platform has assigned the identifier before the before-save hook runs; creating must work.
        for name in ("create.plain_account", "create.plain_contact", "create.plain_enquiry",
                     "create.plain_account_admin", "create.plain_contact_admin"):
            self.assertEqual(self.outcome(name), "ok", name)
        for entity in ("Account", "Contact", "Opportunity"):
            self.assertEqual(self.outcome(f"create.supplied_id_is_never_used_{entity}"), "ok")
            self.assertEqual(self.result[f"supplied_id_used_{entity}"], "no")
            self.assertEqual(self.result[f"supplied_id_created_{entity}"], "one-with-its-own-id")

    def test_import_is_refused_for_every_kind_of_record(self):
        for name in ("create.import_option", "create.import_option_contact_admin", "create.import_option_enquiry",
                     "create.import_with_identifier"):
            self.assertEqual(self.outcome(name), "Forbidden", name)

    def test_every_change_is_audited_with_previous_and_new(self):
        self.assertEqual(self.audits("edit.parent_change"), ["parentFirm:Account:a1:p1>p2"])
        self.assertEqual(self.audits("edit.parent_clear"), ["parentFirm:Account:a1:p1>"])
        self.assertEqual(self.audits("create.with_parent"), ["parentFirm:Account:a1:>p1"])
        self.assertEqual(self.audits("edit.contact_primary"),
                         ["primaryFirm:Contact:c1:a1>a2", "contactFirmLink:Contact:c1:>a2"])
        self.assertEqual(self.audits("edit.enquiry_firm"), ["enquiryFirm:Opportunity:o1:a1>a2"])
        self.assertEqual(self.audits("link.contact_link"), ["contactFirmLink:Contact:c1:>a2"])
        self.assertEqual(self.audits("link.firm_side_unlink_other"), ["contactFirmLink:Contact:c1:a2>"])
        self.assertEqual(self.audits("link.branch_link"), ["parentFirm:Account:b1:p0>p1"])
        self.assertEqual(self.audits("link.branch_unlink"), ["parentFirm:Account:b1:p1>"])
        self.assertEqual(self.audits("link.enquiry_link"), ["enquiryFirm:Opportunity:o1:a0>a1"])
        self.assertEqual(self.audits("link.enquiry_unlink"), ["enquiryFirm:Opportunity:o1:a1>"])
        self.assertEqual(self.audits("link.primary_firm_from_firm"), ["primaryFirm:Contact:c1:>a1"])
        self.assertEqual(self.audits("status.retire"), ["status:Account:a1:active>retired"])
        self.assertEqual(self.audits("status.supersede"), ["successor:Account:a1:>a2",
                                                           "status:Account:a1:active>superseded"])
        self.assertEqual(self.audits("edit.parent_same_value"), [])

    def test_the_final_primary_firm_is_audited_after_the_platforms_own_hook_has_run(self):
        # The platform's Contact hook makes the first linked firm primary when none is given: the
        # identity hook runs after it (order 99), so the audit names the value that is stored.
        self.assertEqual(self.audits("edit.contact_clears_primary_and_drops_its_link"),
                         ["primaryFirm:Contact:c1:a1>a2", "contactFirmLink:Contact:c1:a1>"])
        self.assertEqual(self.result["links_after_clear"], "a2")

    def test_every_firm_link_of_a_new_contact_is_audited_once(self):
        a1 = "contactFirmLink:Contact:c1:>a1"
        a2 = "contactFirmLink:Contact:c1:>a2"
        primary = "primaryFirm:Contact:c1:>a1"
        self.assertEqual(self.audits("create.contact_primary_linked"), [a1, a2, primary])
        self.assertEqual(self.audits("create.contact_links_without_primary"), [a1, a2, primary])
        self.assertEqual(self.audits("create.contact_links_duplicate_ids"), [a1, primary])
        self.assertEqual(self.audits("create.contact_with_primary"), [a1, primary])

    def test_clearing_a_primary_and_its_links_audits_each_change_once(self):
        # The platform reports the unlink twice (link-multiple save, then its own hook): one record.
        self.assertEqual(self.audits("edit.contact_clears_primary_and_all_links"),
                         ["primaryFirm:Contact:c1:a1>", "contactFirmLink:Contact:c1:a1>"])
        self.assertEqual(self.result["links_after_clear_all"], "none")
        self.assertEqual(self.result["primary_after_clear_all"], "none")

    def test_a_create_whose_audit_cannot_be_stored_leaves_no_record_and_no_link_rows(self):
        for name in ("create.contact_links_audit_unwritable", "create.contact_links_audit_fails_on_second_link",
                     "create.contact_links_undo_cannot_delete", "create.with_parent_audit_unwritable"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        for line in ("create_links_contacts_left=0", "create_links_link_rows_left=0",
                     "create_links2_contacts_left=0", "create_links2_link_rows_left=0",
                     "accounts_left_after_failed_create=1"):    # only the seeded parent remains
            self.assertIn(line, self.out)
        # R2: even when every compensating write would fail, nothing remains (there is none to fail)
        self.assertIn("create_undo_fail_contacts_left=0", self.out)
        self.assertIn("create_undo_fail_link_rows_left=0", self.out)
        self.assertEqual(self.audits("create.contact_links_undo_cannot_delete"), [])

    def test_r2_failed_changes_leave_nothing_and_the_memory_of_a_rolled_back_audit_is_forgotten(self):
        # R2 and S3. A failed change is rolled back completely, partial audit records included; the same change
        # made again in the same request is audited again (no in-request memory of a rolled-back audit record).
        self.assertIn("enquiries_left_after_failed_create=0", self.out)
        self.assertEqual(self.outcome("create.enquiry_with_firm_audit_unwritable"), "Forbidden")
        for line in ("memory.relation.rolled_back=nothing-left", "memory.relation.links_after_second_change=a2",
                     "memory.save.rolled_back=nothing-left", "memory.save.links_after_second_change=a1"):
            self.assertIn(line, self.out)
        self.assertEqual(self.audits("memory.relation_failed_then_changed_again"),
                         ["contactFirmLink:Contact:c1:>a2", "primaryFirm:Contact:c1:>a2"])
        self.assertEqual(self.audits("memory.save_failed_then_changed_again"),
                         ["contactFirmLink:Contact:c1:>a1", "primaryFirm:Contact:c1:>a1"])

    def test_s4_scripts_cannot_write_identity_records_and_a_record_save_refuses_link_lists_of_the_link_routes(self):
        for type_ in ("Account", "Contact", "Opportunity", "AccountContact"):
            self.assertIn(f"script_may_write_{type_}=no", self.out)
        self.assertIn("script_may_write_Task=yes", self.out)   # the restriction is not wider than the identity records
        for name in ("script.save_with_branches_on_edit", "script.save_with_predecessors_on_edit",
                     "script.save_with_predecessors_on_edit_contact", "script.save_with_branches_on_create"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertEqual(self.outcome("script.save_with_empty_branches_on_create"), "ok")

    def test_s5_enquiry_merge_is_disabled_like_firm_and_contact_merge(self):
        for type_ in ("Account", "Contact", "Opportunity"):
            self.assertIn(f"merge_disabled_{type_}=yes", self.out)

    def test_no_change_succeeds_when_the_audit_cannot_be_stored_and_each_is_put_back(self):
        for name in ("edit.parent_audit_unwritable", "edit.enquiry_firm_audit_unwritable", "status.audit_unwritable",
                     "link.contact_link_audit_unwritable", "link.contact_unlink_audit_unwritable",
                     "link.firm_side_link_audit_unwritable", "link.branch_link_audit_unwritable",
                     "link.branch_unlink_audit_unwritable", "link.enquiry_link_audit_unwritable",
                     "link.enquiry_belongs_to_audit_unwritable", "link.primary_firm_from_firm_audit_unwritable",
                     "link.orm_link_audit_unwritable_is_put_back", "edit.contact_adds_link_audit_unwritable",
                     "edit.parent_audit_readback_differs"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        state = {
            "parent_after_refused_edit": "p1", "links_after_refused_link": "none",
            "links_after_refused_unlink": "a1,a2", "links_after_refused_firm_side_link": "a1",
            "parent_after_refused_link": "p0", "parent_after_refused_unlink": "p1",
            "enquiry_firm_after_refused_link": "a0", "enquiry_firm_after_refused_relate": "none",
            "primary_after_refused_link": "a0", "links_after_refused_orm_link": "a1",
            "links_after_refused_add": "a1",
        }
        for key, value in state.items():
            self.assertEqual(self.result[key], value, key)
        # R2: when every compensating write would fail the link is still not there: nothing was committed
        self.assertEqual(self.result["links_when_put_back_fails"], "a1")
        self.assertEqual(self.audits("link.put_back_cannot_run"), [])
        self.assertEqual(self.outcome("link.put_back_cannot_run"), "Forbidden")

    def test_the_primary_firm_stays_one_of_the_linked_firms(self):
        for name in ("link.contact_unlink_primary", "link.contact_unlink_primary_admin",
                     "link.firm_side_unlink_primary", "link.orm_unlink_primary_is_put_back",
                     "link.record_unlink_hook_refuses_the_primary_on_its_own",
                     "link.orm_firm_side_unlink_primary_is_put_back_before_the_platform_clears_it"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertEqual(self.outcome("link.record_unlink_hook_allows_another_firm_on_its_own"), "ok")
        self.assertEqual(self.result["links_after_orm_unlink"], "a1")
        self.assertEqual(self.result["primary_after_orm_firm_side_unlink"], "a1")
        self.assertEqual(self.result["links_after_orm_firm_side_unlink"], "a1")
        for name in ("edit.contact_drops_primary_link", "create.contact_primary_not_linked"):
            self.assertEqual(self.outcome(name), "BadRequest", name)
        for name in ("edit.contact_moves_primary_and_link", "edit.contact_clears_primary_and_drops_its_link",
                     "edit.contact_clears_primary_and_all_links", "link.contact_unlink_other",
                     "edit.exception_primary_unlinked_then_other_edit", "create.contact_primary_linked"):
            self.assertEqual(self.outcome(name), "ok", name)

    def test_successor_rules(self):
        for name in ("status.supersede_self", "status.supersede_missing", "status.supersede_wrong_kind",
                     "status.supersede_cycle", "status.supersede_long_cycle", "status.superseded_without_successor",
                     "status.retired_with_successor", "status.active_with_successor", "status.unknown_value",
                     "create.retired_new", "create.successor_new"):
            self.assertEqual(self.outcome(name), "BadRequest", name)
            self.assertEqual(self.audits(name), [], name)
        for name in ("status.retire", "status.retire_contact", "status.retire_admin", "status.supersede",
                     "status.supersede_contact", "status.supersede_into_a_chain", "status.reactivate"):
            self.assertEqual(self.outcome(name), "ok", name)
        for name in ("link.successor_link", "link.successor_link_admin", "link.contact_predecessors_unlink",
                     "link.successor_orm_relate_is_put_back", "link.successor_orm_belongs_to_relate",
                     "link.record_link_hook_refuses_a_successor_on_its_own",
                     "link.record_unlink_hook_refuses_a_successor_on_its_own"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertEqual(self.result["successor_after_refused_relate"], "a9")
        self.assertEqual(self.result["successor_after"], "none")

    def test_link_lists_only_the_link_routes_may_change_are_refused_in_a_record_save(self):
        for name in ("create.branches_input_refused", "create.predecessors_input_refused",
                     "edit.branches_input_refused", "edit.predecessors_input_refused"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertEqual(self.outcome("edit.plain_input_allowed"), "ok")

    def test_bulk_links_of_identity_relationships_are_refused_and_undone(self):
        for name in self.result:
            if name.startswith("bulk."):
                self.assertEqual(self.outcome(name), "ok" if name == "bulk.Account.documents" else "Forbidden", name)
        self.assertEqual(self.result["link_rows_left_after_bulk"], "0")
        self.assertEqual(self.result["link_rows_left_after_bulk_contact"], "0")

    def test_over_length_input_is_a_validation_error_and_stores_nothing(self):
        for name in ("length.title_over_limit", "length.title_over_limit_multibyte", "length.account_name_over_limit",
                     "length.title_over_limit_on_edit", "length.nothing_stored_when_refused"):
            self.assertEqual(self.outcome(name), "BadRequest", name)
        self.assertEqual(self.result["contacts_stored_after_refused_title"], "0")
        for name in ("length.title_at_limit", "length.title_multibyte_at_limit",
                     "length.legacy_long_value_untouched_on_other_edit"):
            self.assertEqual(self.outcome(name), "ok", name)

    def test_audit_records_are_written_only_by_the_server_and_never_changed(self):
        self.assertEqual(self.outcome("audit.create_without_option"), "Forbidden")
        self.assertEqual(self.outcome("audit.create_with_wrong_option_value"), "Forbidden")
        self.assertEqual(self.outcome("audit.create_with_option"), "ok")
        for name in ("audit.edit", "audit.delete", "audit.edit_admin", "audit.delete_admin"):
            self.assertEqual(self.outcome(name), "Forbidden", name)

    def test_policy_helpers(self):
        self.assertEqual(json.loads(self.result["policy.primary_broken"]), [True, False, False, False])
        self.assertEqual(json.loads(self.result["policy.unlink_primary"]), [True, False, False])
        self.assertEqual(json.loads(self.result["policy.chain"]), [True, False, True, False])
        self.assertEqual(json.loads(self.result["policy.resolve"]), ["c", "c", None])


# Each mutation removes one control from a copy of the PHP; the harness output must change.
MUTATIONS = {
    "csv import accepted": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$options->get\('import'\)\) \{", "if (false) {"),
    "firm delete allowed": (
        "Classes/Identity/IdentityGuard.php",
        r"(public function beforeRemove\(Entity \$entity\): void\s*\{\s*)throw \$this->removalRefusal\(\);", r"\1return;"),
    "record delete route allowed": (
        "Classes/Identity/RecordHooks/BeforeDelete.php", r"throw \$this->guard->removalRefusal\(\);", "return;"),
    "primary unlink allowed": (
        "Classes/Identity/IdentityPolicy.php",
        r"return !self.{2}isEmpty\(\$primaryId\) && \$primaryId === \$unlinkedFirmId;", "return false;"),
    "primary unlink backstop removed": (
        "Classes/Identity/IdentityGuard.php", r"!\$relate &&\s*\$relationship === IdentityPolicy::REL_CONTACT_FIRM_LINK",
        "false && $relationship === IdentityPolicy::REL_CONTACT_FIRM_LINK"),
    "primary not required among links": (
        "Classes/Identity/IdentityPolicy.php", r"return !in_array\(\$primaryId, \$linkedIds, true\);", "return false;"),
    "audit failure swallowed": (
        "Classes/Identity/IdentityAuditor.php", r"throw new Forbidden\(\s*'The identity audit record", "return; new Forbidden('x"),
    "audit not read back": (
        "Classes/Identity/IdentityAuditor.php",
        r"\(string\) \$stored->get\('newValue'\) !== \(string\) \$new \|\|", "false ||"),
    "audit records editable": (
        "Hooks/IdentityAudit/ProtectIdentityAudit.php", r"if \(!\$entity->isNew\(\)\) \{", "if (false) {"),
    "audit records deletable": (
        "Hooks/IdentityAudit/ProtectIdentityAudit.php",
        r"(public function beforeRemove\(Entity \$entity, RemoveOptions \$options\): void\s*\{\s*)throw new Forbidden\(",
        r"\1return; new Forbidden("),
    "forged audit records accepted": (
        "Hooks/IdentityAudit/ProtectIdentityAudit.php",
        r"\$options->get\(IdentityPolicy[:][:]AUDIT_WRITE_OPTION\) !== true", "false"),
    "bulk link allowed": (
        "Classes/Identity/IdentityGuard.php",
        r"if \(!in_array\(\$link, IdentityPolicy.{2}BULK_REFUSED_LINKS\[\$type\] \?\? \[\], true\)\) \{", "if (true) {"),
    "successor cycle allowed": (
        "Classes/Identity/IdentityPolicy.php", r"\$current === \$selfId \|\| isset\(\$seen\[\$current\]\)", "false"),
    "wrong-kind successor allowed": (
        "Classes/Identity/IdentityPolicy.php", r"if \(!\$successorExists\) \{", "if (false) {"),
    "over-length input accepted": (
        "Classes/Identity/IdentityGuard.php", r"mb_strlen\(\$value\) > \$limit", "false"),
    "successor set by linking allowed (record hook)": (
        "Classes/Identity/IdentityGuard.php",
        r"if \(isset\(IdentityPolicy[:][:]EDIT_ONLY_LINKS\[\$type\]\[\$link\]\)\) \{\s*throw new Forbidden", "if (false) {\n throw new Forbidden"),
    "successor set by linking allowed (after hook)": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$editOnly !== null\) \{", "if (false) {"),
    "update change not audited": (
        "Classes/Identity/IdentityGuard.php",
        r"foreach \(\$this->changes\(\$entity, \$type\) as \[\$relationship, \$previous, \$new\]\) \{", "foreach ([] as [$relationship, $previous, $new]) {"),
    "link change not audited": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$previous === \$new\) \{", "if (true) {"),
    # CRM-IDINT-001R2: the compensating writes are gone; these remove what replaces them.
    "save not one transaction (firm)": (
        "Resources/metadata/entityDefs/Account.json", r'"transactionalSave": true', '"transactionalSave": false'),
    "save not one transaction (contact)": (
        "Resources/metadata/entityDefs/Contact.json", r'"transactionalSave": true', '"transactionalSave": false'),
    "save not one transaction (enquiry)": (
        "Resources/metadata/entityDefs/Opportunity.json", r'"transactionalSave": true', '"transactionalSave": false'),
    "repository class not declared (contact)": (
        "Resources/metadata/entityDefs/Contact.json", r'"repositoryClassName": "[^"]*",', ""),
    "relate not atomic": (
        "Classes/Identity/IdentityRelation.php",
        r"\$this->atomically\(function \(\) use \(\$entity, \$columnData, \$options\): void \{\s*parent::relate\(\$entity, \$columnData, \$options\);\s*\}\);",
        "parent::relate($entity, $columnData, $options);"),
    "unrelate not atomic": (
        "Classes/Identity/IdentityRelation.php",
        r"\$this->atomically\(function \(\) use \(\$entity, \$options\): void \{\s*parent::unrelate\(\$entity, \$options\);\s*\}\);",
        "parent::unrelate($entity, $options);"),
    "mass relate not atomic": (
        "Classes/Identity/IdentityRelation.php",
        r"\$this->atomically\(function \(\) use \(\$query, \$options\): void \{\s*parent::massRelate\(\$query, \$options\);\s*\}\);",
        "parent::massRelate($query, $options);"),
    "memory of an audit survives a failed save": (
        "Classes/Identity/IdentityRepository.php", r"IdentityGuard[:][:]resetRequestState\(\);", ""),
    "memory of an audit survives a failed relation change": (
        "Classes/Identity/IdentityRelation.php", r"IdentityGuard[:][:]resetRequestState\(\);", ""),
    "script may write firms": (
        "Resources/metadata/entityAcl/Account.json", r'"systemWriteForbidden": true', '"systemWriteForbidden": false'),
    "script may write contacts": (
        "Resources/metadata/entityAcl/Contact.json", r'"systemWriteForbidden": true', '"systemWriteForbidden": false'),
    "script may write enquiries": (
        "Resources/metadata/entityAcl/Opportunity.json", r'"systemWriteForbidden": true', '"systemWriteForbidden": false'),
    "script may write firm links": (
        "Resources/metadata/entityAcl/AccountContact.json", r'"systemWriteForbidden": true', '"systemWriteForbidden": false'),
    "link list accepted in a record save": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$carried\) \{", "if (false) {"),
    "enquiry merge enabled": (
        "Resources/metadata/recordDefs/Opportunity.json", r'"disabled": true', '"disabled": false'),
    "repeated link change audited twice": (
        "Classes/Identity/IdentityGuard.php", r"if \(\(self[:][:]\$linkState\[\$ledgerKey\] \?\? null\) === \$state\) \{", "if (false) {"),
    "link-list input accepted": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$entity->has\(\$attribute\)\) \{", "if (false) {"),
    "save hook runs before the platform's own": (
        "Hooks/Contact/IdentityBeforeSave.php", r"public static int \$order = 99;", "public static int $order = 1;"),
    "relation hook runs after the platform's own": (
        "Hooks/Account/IdentityAfterUnrelate.php", r"public static int \$order = 1;", "public static int $order = 99;"),
}


@NEEDS_REFERENCE
class TestIdentityPhpMutations(unittest.TestCase):
    """Non-vacuity: with any one control removed, the PHP scenarios no longer match."""

    @classmethod
    def setUpClass(cls):
        cls.expected = read(PHP_DIR, "identity_expected.txt")

    def mutated_output(self, label):
        rel, pattern, replacement = MUTATIONS[label]
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "Custom")
            shutil.copytree(CUSTOM, dest)
            path = os.path.join(dest, rel)
            text = read(path)
            mutated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
            self.assertEqual(count, 1, f"mutation '{label}' does not apply to {rel}")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(mutated)
            return run_harness(dest)

    def test_every_mutation_is_detected(self):
        for label in MUTATIONS:
            with self.subTest(mutation=label):
                code, out, err = self.mutated_output(label)
                self.assertFalse((code, out) == (0, self.expected), f"'{label}' went unnoticed")

    def test_the_unmutated_copy_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "Custom")
            shutil.copytree(CUSTOM, dest)
            code, out, err = run_harness(dest)
        self.assertEqual((code, out), (0, self.expected), err)


# ---- 3.6: settings that travel with the release ---------------------------------------------------------

class TestReleaseSettings(unittest.TestCase):
    def test_the_file_is_valid_and_as_required(self):
        found = {n: (k, v) for n, k, v in release_settings.load()}
        self.assertEqual(found["cleanupDeletedRecords"], ("bool", False))
        self.assertEqual(found["cleanupAudit"], ("bool", False))
        self.assertEqual(found["cleanupActionHistoryPeriod"], ("string", "6 months"))
        self.assertEqual(found["cleanupAuthLogPeriod"], ("string", "13 months"))

    def test_a_relaxed_or_malformed_file_is_refused(self):
        good = load(REPO, "config", "release-settings.json")

        def mutate(fn):
            doc = copy.deepcopy(good)
            fn(doc)
            return doc

        cases = {
            "cleanup on": mutate(lambda d: d["settings"][0].update(value=True)),
            "audit cleanup on": mutate(lambda d: d["settings"][1].update(value=True)),
            "history 12 months": mutate(lambda d: d["settings"][2].update(value="12 months")),
            "sign-in 6 months": mutate(lambda d: d["settings"][3].update(value="6 months")),
            "setting missing": mutate(lambda d: d["settings"].pop(0)),
            "setting twice": mutate(lambda d: d["settings"].append(dict(d["settings"][0]))),
            "wrong type": mutate(lambda d: d["settings"][0].update(type="string")),
            "extra key": mutate(lambda d: d["settings"][0].update(secret="x")),
            "bad name": mutate(lambda d: d["settings"].append({"name": "a;b", "type": "bool", "value": True})),
            "unquoted-unsafe value": mutate(lambda d: d["settings"][2].update(value="6 months'; x")),
            "top level key": dict(good, extra=1),
            "not an object": [],
        }
        for label, doc in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(release_settings.SettingsError):
                    release_settings.validate(doc)

    def test_output_lines(self):
        lines = list(release_settings.lines(release_settings.load()))
        self.assertIn("cleanupDeletedRecords\tbool\tfalse\tfalse", lines)
        self.assertIn("cleanupAuthLogPeriod\tstring\t13 months\t'13 months'", lines)

    def test_a_missing_file_fails_loudly(self):
        with self.assertRaises(release_settings.SettingsError):
            release_settings.load(os.path.join(tempfile.gettempdir(), "does-not-exist-identity.json"))
        self.assertEqual(release_settings.main([os.path.join(tempfile.gettempdir(), "does-not-exist-identity.json")]), 1)

    def test_the_file_carries_no_secret_or_address(self):
        text = read(REPO, "config", "release-settings.json")
        self.assertNotRegex(text, r"https?://|\b\d{1,3}(\.\d{1,3}){3}\b|password|token|secret", "release-settings.json")


FAKE_SETTINGS_DOCKER = r"""#!/usr/bin/env bash
cat > /dev/null  # `docker compose exec -T` forwards, and so consumes, its standard input
echo "$*" >> "$FAKE_DOCKER_LOG"
name=""
if [[ "$*" =~ array_key_exists\(\'([A-Za-z0-9]+)\' ]]; then name=${BASH_REMATCH[1]}
elif [[ "$*" =~ \[\'([A-Za-z0-9]+)\'\] ]]; then name=${BASH_REMATCH[1]}; fi
case "$*" in
    *"config:set ${FAKE_SET_FAILS:-%none%} "*) exit 1 ;;
    *array_key_exists*)
        if [ "$name" = "${FAKE_UNKNOWN:-%none%}" ]; then printf false; else printf true; fi ;;
    *"data/config.php"*)
        case "$name" in
            cleanupDeletedRecords|cleanupAudit) val=false ;;
            cleanupActionHistoryPeriod) val="'6 months'" ;;
            cleanupAuthLogPeriod) val="'13 months'" ;;
            *) val=NULL ;;
        esac
        if [ "$name" = "${FAKE_WRONG:-%none%}" ]; then val=${FAKE_WRONG_VALUE-NULL}; fi
        printf '%s' "$val" ;;
esac
exit 0
"""


class TestApplyReleaseSettings(tb.ShellEnv):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.bin, "docker"), "w") as fh:
            fh.write(FAKE_SETTINGS_DOCKER)
        self.env_file = os.path.join(self.runtime, "env")
        with open(self.env_file, "w") as fh:
            fh.write(tb.env_text())
        os.chmod(self.env_file, 0o600)

    def step(self, code, extra=None):
        script = (f"set -euo pipefail; . {tb.SCRIPTS}/deploy_release.sh; "
                  f"load_env_names {tb.REPO}/deploy/beta/env.example; "
                  'CRM_BETA_ENV_NAMES=("${CRM_ENV_NAMES[@]}"); export CRM_RUNTIME_DIR; ' + code)
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "CRM_RUNTIME_DIR": self.runtime,
               "CRM_TEST_ROOT": os.path.join(self.tmp, "runtime"), "REAL_STAT": shutil.which("stat"),
               "FAKE_ROOT_DIR": os.path.join(self.tmp, "runtime"), "FAKE_DOCKER_LOG": self.log,
               "HOME": self.tmp, "TMPDIR": self.tmp}
        env.update(extra or {})
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, timeout=60,
                              stdin=subprocess.DEVNULL)

    def test_each_setting_is_set_with_its_type_and_read_back(self):
        res = self.step(f"apply_release_settings {REPO}")
        self.assertEqual(res.returncode, 0, res.stderr)
        calls = self.docker_calls()
        sets = [c.split("config:set ", 1)[1] for c in calls if "config:set" in c]
        self.assertEqual(sets, ["cleanupDeletedRecords false --type=bool", "cleanupAudit false --type=bool",
                                "cleanupActionHistoryPeriod 6 months --type=string",
                                "cleanupAuthLogPeriod 13 months --type=string"])
        self.assertEqual(len([c for c in calls if "array_key_exists" in c]), 4)
        self.assertEqual(len([c for c in calls if "data/config.php" in c and "array_key_exists" not in c]), 4)

    def test_a_wrong_read_back_fails_the_deploy(self):
        for name, wrong in (("cleanupDeletedRecords", "true"), ("cleanupDeletedRecords", "'false'"),
                            ("cleanupAudit", "NULL"), ("cleanupActionHistoryPeriod", "'15 months'"),
                            ("cleanupAuthLogPeriod", "'2 months'"), ("cleanupAuthLogPeriod", "")):
            with self.subTest(setting=name, read_back=wrong):
                res = self.step(f"apply_release_settings {REPO}; echo NOT-REACHED",
                                extra={"FAKE_WRONG": name, "FAKE_WRONG_VALUE": wrong})
                self.assertEqual(res.returncode, 1)
                self.assertIn(f"setting {name} read back as", res.stderr)
                self.assertNotIn("NOT-REACHED", res.stdout)

    def test_an_unknown_setting_name_fails_the_deploy(self):
        res = self.step(f"apply_release_settings {REPO}; echo NOT-REACHED", extra={"FAKE_UNKNOWN": "cleanupAudit"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("setting cleanupAudit is not a known EspoCRM setting", res.stderr)
        self.assertNotIn("NOT-REACHED", res.stdout)

    def test_a_failing_config_set_fails_the_deploy(self):
        res = self.step(f"apply_release_settings {REPO}; echo NOT-REACHED", extra={"FAKE_SET_FAILS": "cleanupAuthLogPeriod"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("config:set cleanupAuthLogPeriod failed", res.stderr)

    def test_invalid_release_settings_fail_before_any_docker_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "config"))
            shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(tmp, "scripts"))
            bad = load(REPO, "config", "release-settings.json")
            bad["settings"][0]["value"] = True
            with open(os.path.join(tmp, "config", "release-settings.json"), "w") as fh:
                json.dump(bad, fh)
            res = self.step(f"apply_release_settings {tmp}; echo NOT-REACHED")
        self.assertEqual(res.returncode, 1)
        self.assertIn("release settings are invalid", res.stderr)
        self.assertEqual([c for c in self.docker_calls() if "config:set" in c], [])

    def test_the_step_runs_after_the_site_settings_and_before_access_provisioning(self):
        source = read(REPO, "scripts", "deploy_release.sh")
        main = source[source.index("\nmain() {"):]
        self.assertLess(main.index('configure_site "$dest"'), main.index('apply_release_settings "$dest"'))
        self.assertLess(main.index('apply_release_settings "$dest"'), main.index('provision_and_accept "$dest"'))
        self.assertIn("set -euo pipefail", source)


# ---- the live suite's own verdict logic ------------------------------------------------------------------

class TestAcceptanceSuiteLogic(unittest.TestCase):
    """The live suite cannot run here; its verdict function and its configuration check can."""

    @classmethod
    def setUpClass(cls):
        cls.ti = sys.modules["acceptance_identity_under_test"]

    def test_a_refused_cell_that_changed_something_fails(self):
        ev = self.ti.evaluate
        self.assertEqual(ev("refused", 1, 1, 0, 0, [], [])[0], True)
        self.assertEqual(ev("refused", 1, 2, 0, 1, [], [])[0], False)
        self.assertEqual(ev("refused", 1, 1, 0, 0, [], ["new"])[0], False)

    def test_a_performed_cell_needs_the_change_and_its_audit_record(self):
        ev = self.ti.evaluate
        self.assertEqual(ev("performed", 1, 2, 0, 1, [], [])[0], True)
        self.assertEqual(ev("performed", 1, 2, 0, 0, [], [])[0], False)   # changed, no audit record
        self.assertEqual(ev("performed", 1, 1, 0, 0, [], [])[0], False)   # not performed
        self.assertEqual(ev("performed", 1, 1, 0, 1, [], ["new"])[0], True)

    def test_an_either_cell_is_refused_unchanged_or_performed_audited(self):
        ev = self.ti.evaluate
        self.assertEqual(ev("either", 1, 1, 0, 0, [], [])[0], True)
        self.assertEqual(ev("either", 1, 2, 0, 1, [], [])[0], True)
        self.assertEqual(ev("either", 1, 2, 0, 0, [], [])[0], False)

    def test_missing_configuration_fails_loudly_and_names_every_missing_variable(self):
        saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("CRM_")}
        try:
            with self.assertRaises(AssertionError) as ctx:
                self.ti.setUpModule()
        finally:
            os.environ.update(saved)
        for name in self.ti.REQUIRED_ENV:
            self.assertIn(name, str(ctx.exception))

    def test_a_refusal_must_come_from_a_control_on_a_route_that_exists(self):
        """A18: a 404, a 405 or a server error is never a refusal; only a refusal status proves a refusal, an import that answers success included (F-4)."""
        proved = self.ti.refusal_proved
        self.assertTrue(proved([("status", 403)]))
        self.assertTrue(proved([("status", 400), ("status", 403)]))
        for bad in (404, 405, 500, 409):
            self.assertFalse(proved([("status", bad)]), bad)
        self.assertFalse(proved([("status", 403), ("status", 404)]))
        self.assertFalse(proved([("ok", {"id": "x"})]))
        self.assertFalse(proved([]))
        self.assertFalse(proved([("ok", {"importRefused": True})]))   # F-4: a success answer is never a refusal
        self.assertFalse(proved([("ok", {"importRefused": False})]))
        self.assertFalse(proved([("ok", {"countError": 1, "countCreated": 0})]))
        self.assertTrue(proved([("status", 403), ("status", 400)]))

    def test_an_unchanged_cell_refused_by_a_missing_route_fails_the_verdict(self):
        ev = self.ti.evaluate
        self.assertEqual(ev("refused", 1, 1, 0, 0, [], [], refusals=True)[0], True)
        self.assertEqual(ev("refused", 1, 1, 0, 0, [], [], refusals=False)[0], False)
        self.assertEqual(ev("either", 1, 1, 0, 0, [], [], refusals=False)[0], False)
        self.assertEqual(ev("either", 1, 2, 0, 1, [], [], refusals=False)[0], True)    # performed, with its record
        self.assertEqual(ev("performed", 1, 2, 0, 1, [], [], refusals=False)[0], True)

    def test_the_suite_uses_the_platforms_own_merge_and_import_routes(self):
        source = read(REPO, "tests", "acceptance", "test_identity.py")
        self.assertIn('"POST", "Action"', source)                    # Core/Action/Api/PostProcess
        self.assertIn('"action": "merge"', source)
        self.assertNotIn("action/merge", source)                      # the controller route of CRM-IDINT-001
        self.assertIn("Import/file", source)                          # Tools/Import/Api/PostFile
        self.assertIn('client.call("POST", "Import"', source)         # Tools/Import/Api/Post
        self.assertNotIn('client.create("Import"', source)

    def test_the_cleanup_observation_counts_audit_history_too(self):
        source = read(REPO, "tests", "acceptance", "test_identity.py")
        self.assertIn("must print four integers", source)
        self.assertIn('CLEANUP["before"][3], 0', source)

    def test_every_matrix_cell_has_a_driver(self):
        for route in matrix.ROUTES:
            self.assertIn(f'"{route}"', read(REPO, "tests", "acceptance", "test_identity.py") +
                          ' "retire" "supersede" "cleanup_job" ')


# ---- 3.3: the read-only report ----------------------------------------------------------------------

class FakeEspo:
    """contacts: {id: primary firm id}; links: {firm id: [contact ids linked to it]}."""

    def __init__(self, contacts, links):
        self.contacts, self.links, self.methods = contacts, links, []

    def request(self, method, url, headers, body):
        import urllib.parse
        self.methods.append(method)
        parts = urllib.parse.urlsplit(url)
        path = parts.path.split("/api/v1/", 1)[1]
        if path == "Contact":
            rows = [{"id": c, "accountId": f} for c, f in sorted(self.contacts.items())]
        elif path.startswith("Account/") and path.endswith("/contacts"):
            rows = [{"id": c} for c in self.links.get(path.split("/")[1], [])]
        else:
            return 404, b"{}"
        return 200, json.dumps({"total": len(rows), "list": rows}).encode()


class TestIdentityReport(unittest.TestCase):
    ENV = {crm_api.ENV_BASE_URL: "http://crm.example.invalid:8180", crm_api.ENV_USERNAME: "u",
           crm_api.ENV_PASSWORD: "p"}

    def run_main(self, fake, env=None):
        import io
        out = io.StringIO()
        code = identity_report.main([], transport=fake, environ=env or self.ENV, out=out)
        return code, out.getvalue()

    def test_it_lists_exactly_the_contacts_whose_primary_firm_is_not_linked(self):
        fake = FakeEspo({"c1": "a1", "c2": "a1", "c3": "a2", "c4": None, "c5": "a3"},
                        {"a1": ["c1"], "a2": ["c3"], "a3": []})
        code, out = self.run_main(fake)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"count": 2, "contactIds": ["c2", "c5"]})

    def test_it_reports_nothing_when_every_primary_is_linked(self):
        code, out = self.run_main(FakeEspo({"c1": "a1", "c2": None}, {"a1": ["c1"]}))
        self.assertEqual((code, json.loads(out)), (0, {"count": 0, "contactIds": []}))

    def test_it_sends_only_get_requests_and_cannot_write(self):
        fake = FakeEspo({"c1": "a1"}, {"a1": []})
        self.run_main(fake)
        self.assertTrue(fake.methods and set(fake.methods) == {"GET"})
        wrapped = identity_report.ReadOnlyTransport(fake)
        for method in ("POST", "PUT", "DELETE"):
            with self.assertRaises(RuntimeError):
                wrapped.request(method, "http://x/api/v1/Contact", {}, None)
        with self.assertRaises(RuntimeError):
            wrapped.request("GET", "http://x/api/v1/Contact", {}, b"{}")

    def test_missing_configuration_fails_loudly(self):
        code, out = self.run_main(FakeEspo({}, {}), env={crm_api.ENV_BASE_URL: "http://crm.example.invalid"})
        self.assertEqual((code, out), (2, ""))

    def test_the_report_names_no_credential(self):
        code, out = self.run_main(FakeEspo({"c1": "a1"}, {"a1": []}))
        self.assertNotIn("p", set(json.loads(out)) - {"count", "contactIds"})
        self.assertNotIn(self.ENV[crm_api.ENV_PASSWORD] + "@", out)


if __name__ == "__main__":
    unittest.main()
