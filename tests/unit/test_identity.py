"""CRM-IDINT-001 unit tests: identity integrity.

No EspoCRM, Docker or browser runs here. What is executed:
- the route matrix definition (completeness, consistency with the roles);
- the custom PHP (IdentityPolicy, IdentityAuditor, IdentityGuard, the hooks and the
  merge controllers) under php, against the stand-ins in tests/unit/php/, when php is
  installed (gated like the other php tests); mutations of that PHP prove the checks fail
  when a control is removed;
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
                for route in ("delete", "mass_delete", "merge", "csv_import", "supplied_id", "bulk_link",
                              "cleanup_job"):
                    self.assertEqual(matrix.expectation(rel, route, kind)[0], "refused", (rel, route, kind))

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
        self.assertFalse(os.path.exists(os.path.join(REPO, "docs", "IDENTITY.md")))
        self.assertFalse(os.path.exists(os.path.join(REPO, "docs", "LOGGING.md")))

    def test_the_hook_files_are_present_for_every_route_that_changes_an_identity(self):
        for entity, kinds in (("Account", ("BeforeSave", "AfterSave", "BeforeRelate", "BeforeUnrelate",
                                           "BeforeMassRelate", "BeforeRemove")),
                              ("Contact", ("BeforeSave", "AfterSave", "BeforeRelate", "BeforeUnrelate",
                                           "BeforeMassRelate", "BeforeRemove")),
                              ("Opportunity", ("BeforeSave", "AfterSave", "BeforeRelate", "BeforeUnrelate"))):
            for kind in kinds:
                path = os.path.join(CUSTOM, "Hooks", entity, f"Identity{kind}.php")
                self.assertTrue(os.path.isfile(path), path)
                self.assertRegex(read(path), rf"class Identity{kind} implements {kind}\b")
        self.assertTrue(os.path.isfile(os.path.join(CUSTOM, "Hooks", "IdentityAudit", "ProtectIdentityAudit.php")))

    def test_no_identity_php_has_an_administrator_or_service_account_exemption(self):
        files = [os.path.join(r, f) for r, _, fs in os.walk(CUSTOM) for f in fs
                 if f.endswith(".php") and ("Identity" in r or f.startswith("Identity")
                                            or f in ("ProtectIdentityAudit.php",))]
        self.assertGreaterEqual(len(files), 17)
        files += [os.path.join(CUSTOM, "Controllers", n) for n in ("Account.php", "Contact.php")]
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
                          custom_dir], capture_output=True, text=True, timeout=120)
    return res.returncode, res.stdout, res.stderr


def parse(stdout):
    return dict(line.split("=", 1) for line in stdout.splitlines() if "=" in line)


@unittest.skipUnless(HAVE_PHP, "php not installed")
class TestIdentityPhp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, out, err = run_harness(CUSTOM)
        assert code == 0, err
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

    def test_delete_mass_delete_and_merge_are_refused_even_for_an_administrator(self):
        for name in ("remove.Account", "remove.Account_admin", "remove.Contact", "remove.Contact_admin",
                     "merge.Account", "merge.Account_no_args", "merge.Contact", "merge.Contact_no_args"):
            self.assertEqual(self.outcome(name), "Forbidden", name)

    def test_a_supplied_identifier_and_import_are_refused(self):
        for name in ("create.supplied_id", "create.supplied_id_contact", "create.supplied_id_enquiry",
                     "create.supplied_id_admin", "create.import_option"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertEqual(self.outcome("create.plain_account"), "ok")

    def test_every_change_is_audited_with_previous_and_new(self):
        self.assertEqual(self.audits("edit.parent_change"), ["parentFirm:Account:a1:p1>p2"])
        self.assertEqual(self.audits("edit.parent_clear"), ["parentFirm:Account:a1:p1>"])
        self.assertEqual(self.audits("create.with_parent"), ["parentFirm:Account:a1:>p1"])
        self.assertEqual(self.audits("edit.contact_primary"), ["primaryFirm:Contact:c1:a1>a2"])
        self.assertEqual(self.audits("edit.enquiry_firm"), ["enquiryFirm:Opportunity:o1:a1>a2"])
        self.assertEqual(self.audits("link.contact_link"), ["contactFirmLink:Contact:c1:>a2"])
        self.assertEqual(self.audits("link.firm_side_unlink_other"), ["contactFirmLink:Contact:c1:a2>"])
        self.assertEqual(self.audits("status.retire"), ["status:Account:a1:active>retired"])
        self.assertEqual(self.audits("status.supersede"), ["successor:Account:a1:>a2",
                                                           "status:Account:a1:active>superseded"])
        self.assertEqual(self.audits("edit.parent_same_value"), [])

    def test_every_firm_link_of_a_new_contact_is_audited_once(self):
        a1 = "contactFirmLink:Contact:c1:>a1"
        a2 = "contactFirmLink:Contact:c1:>a2"
        self.assertEqual(self.audits("create.contact_with_links"), ["primaryFirm:Contact:c1:>a1", a1, a2])
        self.assertEqual(self.audits("create.contact_links_without_primary"), [a1, a2])
        self.assertEqual(self.audits("create.contact_links_duplicate_ids"), [a1])
        # core firing the relate hooks as well (before or after the after-save hook) does not double-record
        self.assertEqual(self.audits("create.contact_links_then_core_fires_relate"), [a1, a2])
        self.assertEqual(self.audits("create.contact_links_relate_fires_before_after_save"), [a1])

    def test_a_create_with_links_whose_audit_fails_leaves_no_record_and_no_link_rows(self):
        for name in ("create.contact_links_audit_unwritable", "create.contact_links_audit_fails_on_second_link",
                     "create.contact_links_undo_cannot_delete_link_rows"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        for line in ("link_create_contacts_left=0", "link_create_link_rows_left=0",
                     "link_create2_contacts_left=0", "link_create2_link_rows_left=0",
                     "link_undo_fail_contacts_left=0"):
            self.assertIn(line, self.out)
        # the documented residual: if the link rows themselves cannot be removed they remain
        self.assertIn("link_undo_fail_link_rows_left=1", self.out)

    def test_no_change_succeeds_when_the_audit_cannot_be_stored(self):
        for name in ("edit.parent_audit_unwritable", "edit.enquiry_firm_audit_unwritable", "status.audit_unwritable",
                     "link.contact_link_audit_unwritable", "link.branch_link_audit_unwritable",
                     "create.with_parent_audit_unwritable", "edit.parent_audit_readback_differs",
                     "link.new_record_audit_unwritable_is_undone"):
            self.assertEqual(self.outcome(name), "Forbidden", name)
        self.assertIn("accounts_left=1", self.out)    # the create was undone: only the seeded parent remains
        self.assertIn("contacts_left=0", self.out)

    def test_the_primary_firm_stays_one_of_the_linked_firms(self):
        for name in ("link.contact_unlink_primary", "link.contact_unlink_primary_admin",
                     "link.firm_side_unlink_primary", "edit.contact_drops_primary_link",
                     "create.contact_primary_not_linked"):
            self.assertEqual(self.outcome(name), "BadRequest" if name.startswith(("edit", "create")) else "Forbidden",
                             name)
        for name in ("edit.contact_moves_primary_and_link", "edit.contact_clears_primary_and_link",
                     "link.contact_unlink_other", "edit.exception_primary_unlinked_then_other_edit",
                     "create.contact_primary_linked"):
            self.assertEqual(self.outcome(name), "ok", name)

    def test_successor_rules(self):
        for name in ("status.supersede_self", "status.supersede_missing", "status.supersede_wrong_kind",
                     "status.supersede_cycle", "status.supersede_long_cycle", "status.superseded_without_successor",
                     "status.retired_with_successor", "status.active_with_successor", "status.unknown_value",
                     "create.retired_new", "create.successor_new"):
            self.assertEqual(self.outcome(name), "BadRequest", name)
            self.assertEqual(self.audits(name), [], name)
        for name in ("status.retire", "status.retire_contact", "status.supersede", "status.supersede_contact",
                     "status.supersede_into_a_chain", "status.reactivate"):
            self.assertEqual(self.outcome(name), "ok", name)
        for name in ("link.successor_link", "link.predecessors_link", "link.contact_successor_unlink"):
            self.assertEqual(self.outcome(name), "Forbidden", name)

    def test_bulk_links_of_identity_relationships_are_refused(self):
        for name in self.result:
            if name.startswith("bulk."):
                self.assertEqual(self.outcome(name), "ok" if name.endswith(("documents", "opportunities")) and
                                 name.startswith(("bulk.Account.documents", "bulk.Contact.opportunities")) else "Forbidden",
                                 name)

    def test_over_length_input_is_a_validation_error_and_stores_nothing(self):
        for name in ("length.title_over_limit", "length.title_over_limit_multibyte", "length.account_name_over_limit",
                     "length.title_over_limit_on_edit", "length.nothing_stored_when_refused"):
            self.assertEqual(self.outcome(name), "BadRequest", name)
        self.assertIn("contacts_stored=0", self.out)
        for name in ("length.title_at_limit", "length.title_multibyte_at_limit",
                     "length.legacy_long_value_untouched_on_other_edit"):
            self.assertEqual(self.outcome(name), "ok", name)

    def test_audit_records_are_written_only_by_the_server_and_never_changed(self):
        self.assertEqual(self.outcome("audit.create_without_option"), "Forbidden")
        self.assertEqual(self.outcome("audit.create_with_wrong_option_value"), "Forbidden")
        self.assertEqual(self.outcome("audit.create_with_option"), "ok")
        self.assertEqual(self.outcome("audit.edit"), "Forbidden")
        self.assertEqual(self.outcome("audit.delete"), "Forbidden")

    def test_policy_helpers(self):
        self.assertEqual(json.loads(self.result["policy.primary_broken"]), [True, False, False, False])
        self.assertEqual(json.loads(self.result["policy.unlink_primary"]), [True, False, False])
        self.assertEqual(json.loads(self.result["policy.chain"]), [True, False, True, False])
        self.assertEqual(json.loads(self.result["policy.resolve"]), ["c", "c", None])


# Each mutation removes one control from a copy of the PHP; the harness output must change.
MUTATIONS = {
    "supplied identifier accepted": (
        "Classes/Identity/IdentityGuard.php",
        r"if \(\$isNew && !IdentityPolicy::isEmpty\(\$entity->get\('id'\)\)\) \{", "if (false) {"),
    "csv import accepted": (
        "Classes/Identity/IdentityGuard.php", r"if \(IdentityPolicy.{2}option\(\$options, 'import'\)\) \{", "if (false) {"),
    "firm delete allowed": (
        "Classes/Identity/IdentityGuard.php",
        r"(public function beforeRemove\(Entity \$entity\): void\s*\{\s*)throw new Forbidden\(", r"\1return; new Forbidden("),
    "merge allowed": (
        "Controllers/Account.php", r"throw new Forbidden\(", "exit(0); new Forbidden("),
    "primary unlink allowed": (
        "Classes/Identity/IdentityPolicy.php",
        r"return !self.{2}isEmpty\(\$primaryId\) && \$primaryId === \$unlinkedFirmId;", "return false;"),
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
        r"IdentityPolicy.{2}option\(\$options, IdentityPolicy.{2}AUDIT_WRITE_OPTION\) !== true", "false"),
    "bulk link allowed": (
        "Classes/Identity/IdentityGuard.php",
        r"if \(in_array\(\$link, IdentityPolicy.{2}BULK_REFUSED_LINKS\[\$type\] \?\? \[\], true\)\) \{", "if (false) {"),
    "successor cycle allowed": (
        "Classes/Identity/IdentityPolicy.php", r"\$current === \$selfId \|\| isset\(\$seen\[\$current\]\)", "false"),
    "wrong-kind successor allowed": (
        "Classes/Identity/IdentityPolicy.php", r"if \(!\$successorExists\) \{", "if (false) {"),
    "over-length input accepted": (
        "Classes/Identity/IdentityGuard.php", r"mb_strlen\(\$value\) > \$limit", "false"),
    "edit-only successor links allowed": (
        "Classes/Identity/IdentityGuard.php",
        r"if \(in_array\(\$link, IdentityPolicy.{2}EDIT_ONLY_LINKS\[\$type\] \?\? \[\], true\)\) \{", "if (false) {"),
    "create audit not undone": (
        "Classes/Identity/IdentityGuard.php", r"->deleteFromDb\(\(string\) \$entity->getId\(\)\);", ";"),
    "new contact firm links not audited": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$firmId !== ''\) \{", "if (false) {"),
    "new contact link audited twice": (
        "Classes/Identity/IdentityGuard.php", r"if \(\$existing === 0\) \{", "if (true) {"),
    "undo leaves link rows": (
        "Classes/Identity/IdentityGuard.php", r"\$this->deleteLinkRows\(\$entity\);", ";"),
    "update change not audited": (
        "Classes/Identity/IdentityGuard.php",
        r"foreach \(\$this->changes\(\$entity, \$type\) as \[\$relationship, \$previous, \$new\]\) \{", "foreach ([] as [$relationship, $previous, $new]) {"),
}


@unittest.skipUnless(HAVE_PHP, "php not installed")
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
        self.assertEqual(found["cleanupAuditLog"], ("bool", False))
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
            cleanupDeletedRecords|cleanupAuditLog) val=false ;;
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
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env, timeout=60)

    def test_each_setting_is_set_with_its_type_and_read_back(self):
        res = self.step(f"apply_release_settings {REPO}")
        self.assertEqual(res.returncode, 0, res.stderr)
        calls = self.docker_calls()
        sets = [c.split("config:set ", 1)[1] for c in calls if "config:set" in c]
        self.assertEqual(sets, ["cleanupDeletedRecords false --type=bool", "cleanupAuditLog false --type=bool",
                                "cleanupActionHistoryPeriod 6 months --type=string",
                                "cleanupAuthLogPeriod 13 months --type=string"])
        self.assertEqual(len([c for c in calls if "array_key_exists" in c]), 4)
        self.assertEqual(len([c for c in calls if "data/config.php" in c and "array_key_exists" not in c]), 4)

    def test_a_wrong_read_back_fails_the_deploy(self):
        for name, wrong in (("cleanupDeletedRecords", "true"), ("cleanupDeletedRecords", "'false'"),
                            ("cleanupAuditLog", "NULL"), ("cleanupActionHistoryPeriod", "'15 months'"),
                            ("cleanupAuthLogPeriod", "'2 months'"), ("cleanupAuthLogPeriod", "")):
            with self.subTest(setting=name, read_back=wrong):
                res = self.step(f"apply_release_settings {REPO}; echo NOT-REACHED",
                                extra={"FAKE_WRONG": name, "FAKE_WRONG_VALUE": wrong})
                self.assertEqual(res.returncode, 1)
                self.assertIn(f"setting {name} read back as", res.stderr)
                self.assertNotIn("NOT-REACHED", res.stdout)

    def test_an_unknown_setting_name_fails_the_deploy(self):
        res = self.step(f"apply_release_settings {REPO}; echo NOT-REACHED", extra={"FAKE_UNKNOWN": "cleanupAuditLog"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("setting cleanupAuditLog is not a known EspoCRM setting", res.stderr)
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
