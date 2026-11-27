"""CRM-IDINT-001R, A16 and rule 3C: the custom PHP and the unit-test stand-ins against the REAL
pinned EspoCRM sources.

CRM-IDINT-001 named hook interfaces the platform does not have (BeforeRelate, BeforeUnrelate,
BeforeMassRelate), so the application died at start. These tests load every custom PHP class
through the platform's own autoloader and fail on any missing class or interface or incompatible
signature, on a class named in custom metadata that does not exist, and on a test stand-in that
declares a platform symbol the platform lacks.

They need php and the reference in the environment variable CRM_PLATFORM_REFERENCE (the
directory that holds application/ and vendor/). They are skipped only when that variable is
unset; when it is set to something that is not the pinned sources they FAIL (never skip):

    CRM_PLATFORM_REFERENCE=/path/to/espocrm python3 -m unittest discover -s tests/unit

The reference is read-only and never copied into the repository.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CUSTOM = os.path.join(REPO, "custom", "Espo", "Custom")
RES = os.path.join(CUSTOM, "Resources")
PHP_DIR = os.path.join(os.path.dirname(__file__), "php")
CHECK = os.path.join(PHP_DIR, "platform_check.php")
STUBS = os.path.join(PHP_DIR, "identity_stubs.php")

REFERENCE = os.environ.get("CRM_PLATFORM_REFERENCE", "")
HAVE_PHP = bool(shutil.which("php"))
NEEDS_REFERENCE = unittest.skipUnless(
    HAVE_PHP and REFERENCE, "needs php and CRM_PLATFORM_REFERENCE (the pinned EspoCRM sources)")

# SHA-256 of the sorted `sha256sum` lines ("<hash>  application/<path>") of application/, as pinned by
# the work order (section 2).
PINNED_DIGEST = "c06e7a4650db42d81f90ae2f02e8b5b75aea5631ef4a1fd51088ca9a21e1d187"

# A record hook list in the custom recordDefs, and the interface its classes must implement.
RECORD_HOOK_INTERFACES = {
    "beforeLinkHookClassNameList": "Espo\\Core\\Record\\Hook\\LinkHook",
    "beforeUnlinkHookClassNameList": "Espo\\Core\\Record\\Hook\\UnlinkHook",
    "beforeDeleteHookClassNameList": "Espo\\Core\\Record\\Hook\\DeleteHook",
    "beforeCreateHookClassNameList": "Espo\\Core\\Record\\Hook\\CreateHook",
    "beforeUpdateHookClassNameList": "Espo\\Core\\Record\\Hook\\UpdateHook",
    "duplicateWhereBuilderClassName": "Espo\\Core\\Duplicate\\WhereBuilder",
}

# Platform facts the change relies on (rule 3C.1): (file under application/Espo, a pattern that must match, the fact).
CITATIONS = [
    ("Core/Hook/Hook/BeforeSave.php", r"interface BeforeSave\b[\s\S]*function beforeSave\(Entity \$entity, SaveOptions \$options\): void",
     "BeforeSave is a hook interface custom code may implement"),
    ("Core/Hook/Hook/BeforeRemove.php", r"interface BeforeRemove\b[\s\S]*function beforeRemove\(Entity \$entity, RemoveOptions \$options\): void",
     "BeforeRemove is a hook interface"),
    ("Core/Hook/Hook/AfterSave.php", r"interface AfterSave\b", "AfterSave is a hook interface"),
    ("Core/Hook/Hook/AfterRelate.php", r"interface AfterRelate\b[\s\S]*RelateOptions \$options", "AfterRelate is a hook interface"),
    ("Core/Hook/Hook/AfterUnrelate.php", r"interface AfterUnrelate\b[\s\S]*UnrelateOptions \$options", "AfterUnrelate is a hook interface"),
    ("Core/Hook/Hook/AfterMassRelate.php", r"interface AfterMassRelate\b[\s\S]*Select \$query[\s\S]*MassRelateOptions", "AfterMassRelate is a hook interface"),
    ("Core/ORM/Repository/HookMediator.php", r"public function afterRelate\([\s\S]*public function afterUnrelate\([\s\S]*public function afterMassRelate\(",
     "the platform's hook mediator overrides only the after-relation methods"),
    ("Core/HookManager.php", r"private const DEFAULT_ORDER = 9;[\s\S]*\$className[:][:]\$order \?\? self[:][:]DEFAULT_ORDER",
     "a hook's public static $order sorts hooks; the default is 9"),
    ("Core/HookManager.php", r"\$this->hookExists\(\$className, \$entityHookData\)",
     "a hook class whose short name repeats is skipped, so hook class names must be unique per scope"),
    ("Core/Repositories/Database.php", r"\$this->prepareSaveInternal\(\$entity, \$options\);\s*parent[:][:]save\(\$entity, \$options\);[\s\S]*\$entity->set\(self[:][:]ATTR_ID, \$this->recordIdGenerator->generate\(\)\)",
     "the identifier of a new record is generated before the parent save, which runs the before-save hooks (P4)"),
    ("Core/Record/Service.php", r"unset\(\$data->id\);", "an API client's supplied identifier is discarded on create"),
    ("Core/Record/Service.php", r"processBeforeLink\(\$entity, \$link, \$foreignEntity\);[\s\S]*->relate\(\$foreignEntity, null, \[SaveOption[:][:]API => true\]\)",
     "single link runs the record link hooks, then relates through the ORM"),
    ("Core/Record/Service.php", r"processBeforeUnlink\(\$entity, \$link, \$foreignEntity\);[\s\S]*->unrelate\(\$foreignEntity, \[SaveOption[:][:]API => true\]\)",
     "single unlink runs the record unlink hooks, then unrelates through the ORM"),
    ("Core/Record/Service.php", r'recordDefs\.\$this->entityType\.relationships\.\$link\.massLink',
     "mass link is available only where recordDefs.<Entity>.relationships.<link>.massLink is set"),
    ("Core/Record/Service.php", r"Only manyMany, hasMany & hasChildren relations are allowed",
     "a belongsTo link has no link route"),
    *[("Core/Utils/Metadata/Builder.php", rf"\['recordDefs', self[:][:]ANY_KEY, '{key}'\]",
       f"recordDefs.<Entity>.{key} is a list appended across modules")
      for key in ("beforeLinkHookClassNameList", "beforeUnlinkHookClassNameList", "beforeDeleteHookClassNameList",
                  "beforeCreateHookClassNameList", "beforeUpdateHookClassNameList")],
    ("Core/Record/Hook/LinkHook.php", r"interface LinkHook\b[\s\S]*function process\(Entity \$entity, string \$link, Entity \$foreignEntity\): void", "LinkHook"),
    ("Core/Record/Hook/UnlinkHook.php", r"interface UnlinkHook\b[\s\S]*function process\(Entity \$entity, string \$link, Entity \$foreignEntity\): void", "UnlinkHook"),
    ("Core/Record/Hook/DeleteHook.php", r"interface DeleteHook\b[\s\S]*function process\(Entity \$entity, DeleteParams \$params\): void", "DeleteHook"),
    ("Core/Record/Hook/CreateHook.php", r"interface CreateHook\b[\s\S]*function process\(Entity \$entity, CreateParams \$params\): void", "CreateHook"),
    ("Core/Record/Hook/UpdateHook.php", r"interface UpdateHook\b[\s\S]*function process\(Entity \$entity, UpdateParams \$params\): void", "UpdateHook"),
    ("Core/Action/ActionFactory.php", r"\['recordDefs', \$entityType, 'actions', \$action, 'disabled'\]",
     "recordDefs.<Entity>.actions.<action>.disabled disables an action such as merge"),
    ("Core/Action/Service.php", r"\$this->factory->create\(\$action, \$entityType\)", "POST /Action runs the action through the factory"),
    ("Core/MassAction/MassActionFactory.php", r"\['recordDefs', \$entityType, 'massActions', \$action, 'disabled'\]",
     "recordDefs.<Entity>.massActions.<action>.disabled disables a mass action"),
    ("Core/MassAction/Actions/MassDelete.php", r"\} catch \(Exception \$e\) \{[\s\S]*continue;",
     "mass delete swallows a refusal per record, so the switch above is the refusal that answers"),
    ("Core/Action/Actions/Merge.php", r"\$this->merger->process", "the platform's merge is the Merge action"),
    ("Tools/Import/Import.php", r"SaveOption::IMPORT => true", "an imported record is saved with the import option, hooks active"),
    ("Core/ORM/Repository/Option/SaveOption.php", r"public const IMPORT = 'import';", "the import save option"),
    ("Core/FieldProcessing/Relation/LinkMultipleSaver.php", r"relateById\(\$id, \$data, \[\s*SaveOption::SKIP_HOOKS => \$skipHooks",
     "link-multiple values are saved by relating, with hooks unless skipLinkMultipleHooks"),
    ("ORM/Repository/Option/Traits/Options.php", r"public function get\(string \$option\): mixed", "options are read with get()"),
    ("ORM/Repository/RDBRelation.php", r"\$result = \$this->getMapper\(\)->relate[\s\S]*if \(!\$result\) \{\s*return;\s*\}[\s\S]*\$this->afterRelate",
     "the mapper changes the relation first; the after hook runs after it"),
    ("Modules/Crm/Hooks/Contact/Accounts.php", r"class Accounts implements BeforeSave, AfterSave, AfterRelate",
     "the platform's own Contact hook sets the primary firm and the firm links as a side effect"),
    ("Binding.php", r"'Espo\\\\Entities\\\\User',\s*'user'", "a hook receives the signed-in user by the type Espo\\Entities\\User"),
    ("Binding.php", r"'Espo\\\\ORM\\\\EntityManager'", "a hook receives the entity manager by the type Espo\\ORM\\EntityManager"),
    ("Classes/Jobs/Cleanup.php", r"get\('cleanupAuthLogPeriod'", "the sign-in record period is read by the cleanup job"),
    ("Classes/Jobs/Cleanup.php", r"get\('cleanupActionHistoryPeriod'", "the action history period is read by the cleanup job"),
    ("Classes/Jobs/Cleanup.php", r"get\('cleanupDeletedRecords'\)", "deleted-record cleanup is the switch cleanupDeletedRecords"),
    ("Classes/Cleanup/Audit.php", r"get\('cleanupAudit'\)[\s\S]*preserveAuditLog", "audit-history cleanup is the switch cleanupAudit; a scope can preserve its log"),
    ("Resources/defaults/config.php", r"'cleanupAudit' => true,", "audit cleanup is on by default under the name cleanupAudit"),
    ("Resources/defaults/config.php", r"'cleanupDeletedRecords' => true,", "deleted-record cleanup is on by default"),
    ("Resources/metadata/app/consoleCommands.json", r'"config:set": \{', "bin/command config:set exists"),
    ("Classes/ConsoleCommands/SetConfigParam.php", r"TYPE_STRING = 'string'[\s\S]*TYPE_BOOL = 'bool'", "config:set takes --type=bool and --type=string"),
    ("Resources/routes.json", r'"route": "/Action",\s*"method": "post"', "the merge route is POST /Action"),
    ("Resources/routes.json", r'"route": "/Import",\s*"method": "post"', "CSV import is POST /Import"),
    # CRM-IDINT-001R2 (S1 to S5)
    ("Core/Repositories/Database.php", r'metadata->get\("entityDefs\.\$entityType\.transactionalSave"\)',
     "entityDefs.<Entity>.transactionalSave is read by the platform's repository"),
    ("ORM/Repository/RDBRepository.php", r"if \(\$this->transactionalSave\) \{\s*\$this->entityManager->getTransactionManager\(\)->run\(function \(\) use \(\$entity, \$options\) \{\s*\$this->saveInternal",
     "a transactional save runs the whole save, hooks included, in one transaction"),
    ("ORM/TransactionManager.php", r"if \(\$this->level > 0\) \{\s*\$this->createSavepoint\(\);",
     "a nested transaction is a savepoint, so a failed inner change rolls back to it"),
    ("Core/ORM/ClassNameProvider.php", r'entityDefs\.\$entityType\.repositoryClassName',
     "entityDefs.<Entity>.repositoryClassName selects the repository class"),
    ("ORM/Repository/RDBRepository.php", r"public function getRelation\(Entity \$entity, string \$relationName\): RDBRelation\s*\{\s*return new RDBRelation\(",
     "every ORM relation operation goes through the relation object the repository returns"),
    ("ORM/Repository/RDBRelation.php", r"\nclass RDBRelation\b",
     "the relation class is not final, so the product's relation class can extend it"),
    ("Core/Acl/SystemRestriction.php", r'entityAcl\.\$entityType\.systemWriteForbidden',
     "entityAcl.<Entity>.systemWriteForbidden forbids system writes of an entity type"),
    ("Core/Formula/Utils/EntityUtil.php", r"systemRestriction", "the script entity and record functions use the system restriction"),
    ("Tools/Import/Import.php", r"systemRestriction", "CSV import uses the system restriction"),
    ("Core/FieldProcessing/Relation/LinkMultipleSaver.php", r"class LinkMultipleSaver\b",
     "a link list set on the record in hand is persisted by that record's save"),
    ("Modules/Crm/Resources/metadata/recordDefs/TargetList.json", r'"massLink": true', "only TargetList enables mass link in the platform"),
]

# Files that must NOT exist or must NOT say something (the absences the failed candidate relied on).
ABSENT_FILES = [
    "Core/Hook/Hook/BeforeRelate.php", "Core/Hook/Hook/BeforeUnrelate.php", "Core/Hook/Hook/BeforeMassRelate.php",
]
ABSENT_TEXT = [
    ("Core/ORM/Repository/HookMediator.php", r"function beforeRelate|function beforeUnrelate|function beforeMassRelate"),
    ("Resources/defaults/config.php", r"cleanupAuthLogPeriod|cleanupAuditLog"),
]


def reference_problem(path):
    """Why a path is not the pinned reference, or None."""
    if not path or not os.path.isdir(os.path.join(path, "application", "Espo")) \
            or not os.path.isfile(os.path.join(path, "vendor", "autoload.php")):
        return "CRM_PLATFORM_REFERENCE must name the directory that holds application/ and vendor/"
    lines = []
    for root, _, files in os.walk(os.path.join(path, "application")):
        for name in files:
            full = os.path.join(root, name)
            with open(full, "rb") as fh:
                lines.append((os.path.relpath(full, path), hashlib.sha256(fh.read()).hexdigest()))
    text = "".join(f"{digest}  {rel}\n" for rel, digest in sorted(lines))
    if hashlib.sha256(text.encode()).hexdigest() != PINNED_DIGEST:
        return "the reference is not the pinned EspoCRM sources (digest of application/ differs)"
    return None


def php(*args, cwd=None, timeout=120):
    return subprocess.run(["php", "-d", "display_errors=stderr", *args], capture_output=True, text=True,
                          timeout=timeout, cwd=cwd)


def custom_php_files(root=CUSTOM):
    return sorted(os.path.join(r, f) for r, _, fs in os.walk(root) for f in fs if f.endswith(".php"))


def named_classes(res_dir=RES):
    """[class, required interface or None, where] for every class named in the custom metadata."""
    out = []

    def walk(node, key, where):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k, where)
        elif isinstance(node, list):
            for v in node:
                walk(v, key, where)
        elif isinstance(node, str) and re.fullmatch(r"Espo\\[A-Za-z0-9_\\]+", node):
            out.append([node, RECORD_HOOK_INTERFACES.get(key), f"{where} ({key})"])

    for root, _, files in os.walk(res_dir):
        for name in files:
            if name.endswith(".json") and os.sep + "metadata" + os.sep in root + os.sep:
                with open(os.path.join(root, name), encoding="utf-8") as fh:
                    walk(json.load(fh), None, os.path.relpath(os.path.join(root, name), res_dir))
    return out


@NEEDS_REFERENCE
class TestPlatformReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        problem = reference_problem(REFERENCE)
        if problem:
            raise AssertionError(problem)   # set but wrong: a failure, never a skip

    def load_one(self, file, custom=CUSTOM):
        res = php(CHECK, "load", REFERENCE, custom, file)
        return res.returncode, res.stdout.strip(), res.stderr.strip()

    # ---- every custom class loads against the real platform ------------------------------------

    def test_every_custom_php_class_loads_against_the_platform_sources(self):
        files = custom_php_files()
        self.assertGreaterEqual(len(files), 36)
        for file in files:
            with self.subTest(file=os.path.relpath(file, CUSTOM)):
                code, out, err = self.load_one(file)
                self.assertEqual(code, 0, err or out)
                self.assertTrue(out.startswith("OK Espo\\Custom\\"), out)

    def test_every_hook_has_exactly_the_methods_of_the_hook_interfaces_it_implements(self):
        hooks = [f for f in custom_php_files() if os.sep + "Hooks" + os.sep in f]
        self.assertGreaterEqual(len(hooks), 21)
        for file in hooks:
            with self.subTest(file=os.path.relpath(file, CUSTOM)):
                code, out, err = self.load_one(file)
                self.assertEqual(code, 0, err or out)
                self.assertRegex(out, r"^OK \S+ [a-zA-Z,]+$")

    def test_a_class_named_in_custom_metadata_exists_and_has_the_right_interface(self):
        named = named_classes()
        self.assertGreaterEqual(len(named), 14)
        with tempfile.TemporaryDirectory() as tmp:
            listing = os.path.join(tmp, "named.json")
            with open(listing, "w") as fh:
                json.dump(named, fh)
            res = php(CHECK, "named", REFERENCE, CUSTOM, listing)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "")
        # the record hooks are among them, each with its interface
        self.assertIn(["Espo\\Custom\\Classes\\Identity\\RecordHooks\\BeforeLink",
                       "Espo\\Core\\Record\\Hook\\LinkHook", "metadata/recordDefs/Account.json (beforeLinkHookClassNameList)"],
                      named)

    # ---- the stand-ins ------------------------------------------------------------------------

    def compare_stubs(self, stub_file):
        dump = php(CHECK, "dump", stub_file)
        self.assertEqual(dump.returncode, 0, dump.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dump.json")
            with open(path, "w") as fh:
                fh.write(dump.stdout)
            res = php(CHECK, "compare", REFERENCE, path)
        self.assertEqual(res.returncode, 0, res.stderr)
        return [line for line in res.stdout.splitlines() if line], json.loads(dump.stdout)

    def test_the_stand_ins_declare_only_platform_symbols_with_the_platform_signatures(self):
        problems, declared = self.compare_stubs(STUBS)
        self.assertEqual(problems, [])
        self.assertTrue({"Espo\\ORM\\Entity", "Espo\\ORM\\EntityManager", "Espo\\Entities\\User",
                         "Espo\\Core\\Utils\\Metadata"} <= set(declared), sorted(declared))

    def test_the_fake_platform_declares_no_symbol_in_a_platform_namespace(self):
        for name in ("identity_fake.php", "identity_harness.php"):
            with open(os.path.join(PHP_DIR, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotRegex(text, r"(?m)^\s*namespace\s+Espo\b(?!\\Custom)", name)

    def stub_file(self, tmp, body):
        path = os.path.join(tmp, "stubs.php")
        with open(path, "w") as fh:
            fh.write("<?php\n" + body)
        return path

    def test_a_stand_in_for_a_symbol_the_platform_lacks_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.stub_file(tmp, "namespace Espo\\Core\\Hook\\Hook {\n    interface BeforeRelate {\n"
                                       "        public function beforeRelate(): void;\n    }\n}\n")
            problems, _ = self.compare_stubs(path)
        self.assertEqual(problems, ["stand-in declares Espo\\Core\\Hook\\Hook\\BeforeRelate, which the platform does not have"])

    def test_a_stand_in_with_another_signature_or_an_unknown_method_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.stub_file(tmp, (
                "namespace Espo\\ORM {\n    interface Entity {}\n    class EntityManager {\n"
                "        public function getEntityById(string $entityType): ?Entity { return null; }\n"
                "        public function getNewEntity(string $entityType): string { return ''; }\n"
                "        public function noSuchMethod(): void {}\n    }\n}\n"))
            problems, _ = self.compare_stubs(path)
        self.assertTrue(any("getEntityById() takes 1 parameters, the platform 2" in p for p in problems), problems)
        self.assertTrue(any("getNewEntity() returns 'string'" in p for p in problems), problems)
        self.assertTrue(any("noSuchMethod(), which the platform does not have" in p for p in problems), problems)

    # ---- the check itself fails on the failure it exists to catch -------------------------------

    def test_a_hook_implementing_an_interface_the_platform_lacks_fails_to_load(self):
        # CRM-IDINT-001's hooks implemented Espo\Core\Hook\Hook\BeforeRelate: the application did not start.
        with tempfile.TemporaryDirectory() as tmp:
            custom = os.path.join(tmp, "Custom")
            os.makedirs(os.path.join(custom, "Hooks", "Account"))
            file = os.path.join(custom, "Hooks", "Account", "IdentityBeforeRelate.php")
            with open(file, "w") as fh:
                fh.write("<?php\nnamespace Espo\\Custom\\Hooks\\Account;\n"
                         "use Espo\\Core\\Hook\\Hook\\BeforeRelate;\nuse Espo\\ORM\\Entity;\n"
                         "class IdentityBeforeRelate implements BeforeRelate {\n"
                         "    public function beforeRelate(Entity $entity, string $relationName, Entity $foreignEntity, "
                         "array $columnData, mixed $options): void {}\n}\n")
            code, out, err = self.load_one(file, custom)
        self.assertNotEqual(code, 0)
        self.assertIn("BeforeRelate", out + err)

    def test_a_hook_with_an_incompatible_signature_fails_to_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom = os.path.join(tmp, "Custom")
            os.makedirs(os.path.join(custom, "Hooks", "Account"))
            file = os.path.join(custom, "Hooks", "Account", "IdentityBeforeSave.php")
            with open(file, "w") as fh:
                fh.write("<?php\nnamespace Espo\\Custom\\Hooks\\Account;\n"
                         "use Espo\\Core\\Hook\\Hook\\BeforeSave;\nuse Espo\\ORM\\Entity;\n"
                         "class IdentityBeforeSave implements BeforeSave {\n"
                         "    public function beforeSave(Entity $entity, array $options): void {}\n}\n")
            code, out, err = self.load_one(file, custom)
        self.assertNotEqual(code, 0)
        self.assertIn("beforeSave", out + err)

    def test_a_hook_with_a_public_method_that_is_no_hook_fails_the_check(self):
        # The platform registers every public method of a hook class as a hook type.
        with tempfile.TemporaryDirectory() as tmp:
            custom = os.path.join(tmp, "Custom")
            os.makedirs(os.path.join(custom, "Hooks", "Account"))
            file = os.path.join(custom, "Hooks", "Account", "IdentityBeforeSave.php")
            with open(file, "w") as fh:
                fh.write("<?php\nnamespace Espo\\Custom\\Hooks\\Account;\n"
                         "use Espo\\Core\\Hook\\Hook\\BeforeSave;\nuse Espo\\ORM\\Entity;\n"
                         "use Espo\\ORM\\Repository\\Option\\SaveOptions;\n"
                         "class IdentityBeforeSave implements BeforeSave {\n"
                         "    public function beforeSave(Entity $entity, SaveOptions $options): void {}\n"
                         "    public function helper(): void {}\n}\n")
            code, out, err = self.load_one(file, custom)
        self.assertEqual(code, 1)
        self.assertIn("are not exactly those of the Espo\\Core\\Hook\\Hook interfaces", err)

    def test_metadata_naming_a_missing_class_or_the_wrong_interface_is_reported(self):
        listing = [["Espo\\Custom\\Classes\\Identity\\RecordHooks\\DoesNotExist", "Espo\\Core\\Record\\Hook\\LinkHook", "x"],
                   ["Espo\\Custom\\Classes\\Identity\\RecordHooks\\BeforeDelete", "Espo\\Core\\Record\\Hook\\LinkHook", "y"]]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "named.json")
            with open(path, "w") as fh:
                json.dump(listing, fh)
            res = php(CHECK, "named", REFERENCE, CUSTOM, path)
        self.assertEqual(res.stdout.splitlines(), [
            "x names Espo\\Custom\\Classes\\Identity\\RecordHooks\\DoesNotExist, which does not exist",
            "y names Espo\\Custom\\Classes\\Identity\\RecordHooks\\BeforeDelete, which does not implement "
            "Espo\\Core\\Record\\Hook\\LinkHook"])

    # ---- the facts the change relies on (rule 3C.1) ----------------------------------------------

    def test_every_cited_platform_fact_is_in_the_reference(self):
        for rel, pattern, fact in CITATIONS:
            with self.subTest(file=rel, fact=fact):
                path = os.path.join(REFERENCE, "application", "Espo", rel)
                self.assertTrue(os.path.isfile(path), rel)
                with open(path, encoding="utf-8") as fh:
                    self.assertTrue(re.search(pattern, fh.read()), f"{rel}: {fact}")

    def test_the_absences_the_failed_candidate_relied_on_are_confirmed(self):
        for rel in ABSENT_FILES:
            self.assertFalse(os.path.exists(os.path.join(REFERENCE, "application", "Espo", rel)), rel)
        for rel, pattern in ABSENT_TEXT:
            with open(os.path.join(REFERENCE, "application", "Espo", rel), encoding="utf-8") as fh:
                self.assertIsNone(re.search(pattern, fh.read()), rel)

    def test_no_platform_recorddefs_enable_mass_link_on_the_identity_scopes(self):
        for scope in ("Account", "Contact", "Opportunity"):
            path = os.path.join(REFERENCE, "application", "Espo", "Modules", "Crm", "Resources", "metadata",
                                "recordDefs", f"{scope}.json")
            with open(path, encoding="utf-8") as fh:
                self.assertNotIn("massLink", fh.read(), scope)

    # ---- the release settings are settings the platform knows (P5) -------------------------------

    def known(self, name):
        script = f'set -euo pipefail; . "{REPO}/scripts/deploy_release.sh"; php -r "$(known_setting_php {name})"'
        res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60,
                             cwd=REFERENCE, env={**os.environ, "HOME": os.environ.get("HOME", "/")})
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def test_every_release_setting_is_one_the_platform_defines_or_reads(self):
        with open(os.path.join(REPO, "config", "release-settings.json"), encoding="utf-8") as fh:
            names = [s["name"] for s in json.load(fh)["settings"]]
        self.assertEqual(names, ["cleanupDeletedRecords", "cleanupAudit", "cleanupActionHistoryPeriod",
                                 "cleanupAuthLogPeriod"])
        for name in names:
            with self.subTest(setting=name):
                self.assertEqual(self.known(name), "true")

    def test_the_known_setting_check_still_refuses_an_unknown_or_wrong_name(self):
        for name in ("cleanupAuditLog", "cleanupAuditPeriodX", "nope"):
            with self.subTest(setting=name):
                self.assertEqual(self.known(name), "false")


class TestReferenceGate(unittest.TestCase):
    """The gate itself: a wrong path is a failure, and the pinned digest is the work order's."""

    def test_a_path_that_is_not_the_reference_is_reported(self):
        self.assertIsNotNone(reference_problem(""))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNotNone(reference_problem(tmp))
            os.makedirs(os.path.join(tmp, "application", "Espo"))
            os.makedirs(os.path.join(tmp, "vendor"))
            with open(os.path.join(tmp, "vendor", "autoload.php"), "w") as fh:
                fh.write("<?php\n")
            self.assertIn("not the pinned", reference_problem(tmp))

    @unittest.skipUnless(HAVE_PHP and REFERENCE, "needs CRM_PLATFORM_REFERENCE")
    def test_the_reference_in_use_is_the_pinned_one(self):
        self.assertIsNone(reference_problem(REFERENCE))

    def test_the_reference_is_never_inside_the_repository(self):
        if REFERENCE:
            self.assertFalse(os.path.abspath(REFERENCE).startswith(REPO + os.sep))
        self.assertFalse(os.path.exists(os.path.join(REPO, "vendor")))
        self.assertFalse(os.path.exists(os.path.join(REPO, "application")))


if __name__ == "__main__":
    unittest.main()
