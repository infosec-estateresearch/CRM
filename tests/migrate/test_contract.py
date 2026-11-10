"""Contract v3 content and the contract-to-SOQL rule (WO Change 1, AC2)."""

import copy
import datetime as dt
import json
import unittest

from crm_migrate.contract import (ContractError, effective_object, parse_soql, soql_count, soql_datetime,
                                  soql_id_only, soql_select)

from .fake_salesforce import TempDirMixin, contract, contract_bytes, contract_from_doc, make_fake

ADDR = ["Street", "City", "State", "PostalCode", "Country"]
WO_TABLE = {
    "User": "Id FirstName LastName Name Email Username Alias IsActive ProfileId UserRoleId UserType CreatedDate "
            "LastLoginDate SystemModstamp",
    "Profile": "Id Name UserLicenseId SystemModstamp",
    "UserRole": "Id Name ParentRoleId SystemModstamp",
    "Account": "Id Name ParentId MasterRecordId Type Industry Phone Website Description AccountSource OwnerId "
               + " ".join("Shipping" + a for a in ADDR) + " " + " ".join("Billing" + a for a in ADDR)
               + " NumberOfEmployees LastActivityDate TLP__c Interested_in_integration__c "
                 "Bankruptcy_Special_Rate__c IsDeleted CreatedDate CreatedById LastModifiedDate SystemModstamp",
    "Contact": "Id AccountId MasterRecordId FirstName LastName Salutation Title Department Email Phone MobilePhone "
               + " ".join("Mailing" + a for a in ADDR)
               + " OwnerId IsDeleted CreatedDate CreatedById LastModifiedDate SystemModstamp",
    "Opportunity": "Id AccountId Name StageName Amount Probability CloseDate Type LeadSource Description OwnerId "
                   "IsClosed IsWon Loss_Reason__c Paid_geneology_enquiry__c Opportunity_Service__c IsDeleted CreatedDate CreatedById LastModifiedDate SystemModstamp",
    "OpportunityContactRole": "Id OpportunityId ContactId Role IsPrimary IsDeleted CreatedDate SystemModstamp",
    "Task": "Id AccountId WhoId WhatId OwnerId Subject Status Priority ActivityDate Description TaskSubtype CallType "
            "CallDurationInSeconds CallDisposition CompletedDateTime IsClosed IsArchived IsRecurrence IsDeleted "
            "CreatedDate CreatedById LastModifiedDate SystemModstamp",
    "Event": "Id AccountId WhoId WhatId OwnerId Subject Type Location Description StartDateTime EndDateTime "
             "ActivityDateTime IsAllDayEvent DurationInMinutes IsArchived IsRecurrence IsDeleted CreatedDate "
             "CreatedById LastModifiedDate SystemModstamp",
    "EmailMessage": "Id ParentId ActivityId RelatedToId Subject TextBody FromName FromAddress ToAddress CcAddress "
                    "MessageDate Incoming Status MessageIdentifier ThreadIdentifier HasAttachment IsDeleted "
                    "CreatedDate CreatedById LastModifiedDate SystemModstamp",
    "EmailMessageRelation": "Id EmailMessageId RelationId RelationType RelationAddress RelationObjectType "
                            "CreatedDate SystemModstamp",
    "Note": "Id ParentId Title Body OwnerId IsPrivate IsDeleted CreatedDate LastModifiedDate SystemModstamp",
}
OPTIONAL = {("Opportunity", "Opportunity_Service__c"), ("Task", "IsArchived"), ("Event", "IsArchived"),
            ("Account", "MasterRecordId"), ("Contact", "MasterRecordId"),
            ("EmailMessage", "MessageIdentifier"), ("EmailMessage", "ThreadIdentifier")}
OWNER_CHECK = {"Account", "Contact", "Opportunity", "Task", "Event", "Note"}


class ContractContentTest(unittest.TestCase):
    def test_objects_and_fields_match_the_work_order_table(self):
        c = contract()
        self.assertEqual(c.version, 3)
        self.assertEqual(list(c.object_names), list(WO_TABLE))
        for obj in c.objects:
            self.assertEqual(list(obj.field_names), WO_TABLE[obj.name].split(), obj.name)

    def test_required_false_exactly_the_listed_fields(self):
        actual = {(o.name, f.name) for o in contract().objects for f in o.fields if not f.required}
        self.assertEqual(actual, OPTIONAL)

    def test_owner_check_soft_delete_and_change_key(self):
        for obj in contract().objects:
            self.assertEqual(obj.owner_check, obj.name in OWNER_CHECK, obj.name)
            self.assertEqual(obj.soft_delete, "IsDeleted" in obj.field_names, obj.name)
            self.assertEqual(obj.change_key, "SystemModstamp")

    def test_every_field_has_purpose_type_and_references(self):
        for obj in contract().objects:
            for f in obj.fields:
                self.assertRegex(f.purpose, r"^[RM]\d+")
                if f.type == "reference":
                    self.assertTrue(f.reference_to, f"{obj.name}.{f.name}")
                else:
                    self.assertEqual(f.reference_to, ())

    def test_excluded_and_compound_fields_absent(self):
        names = {f.name for o in contract().objects for f in o.fields}
        for banned in ("HtmlBody", "BccAddress", "ShippingAddress", "BillingAddress", "MailingAddress"):
            self.assertNotIn(banned, names)


class ContractValidationTest(unittest.TestCase):
    """Broken contract fixtures must each be refused."""

    def setUp(self):
        self.doc = json.loads(contract_bytes())

    def mutate(self, fn):
        doc = copy.deepcopy(self.doc)
        fn(doc)
        return doc

    def obj(self, doc, name):
        return next(o for o in doc["objects"] if o["name"] == name)

    def fld(self, doc, obj, name):
        return next(f for f in self.obj(doc, obj)["fields"] if f["name"] == name)

    def test_real_contract_parses(self):
        self.assertEqual(contract_from_doc(self.doc).version, 3)

    def test_broken_contracts_are_refused(self):
        cases = {
            "version": lambda d: d.update(contractVersion=1),
            "wildcard": lambda d: self.obj(d, "Account")["fields"].append(
                {"name": "*", "type": "string", "purpose": "M1", "required": False}),
            "fields_function": lambda d: self.obj(d, "Account")["fields"].append(
                {"name": "FIELDS(ALL)", "type": "string", "purpose": "M1", "required": False}),
            "compound_name": lambda d: self.obj(d, "Account")["fields"].append(
                {"name": "ShippingAddress", "type": "string", "purpose": "R4", "required": False}),
            "compound_type": lambda d: self.obj(d, "Account")["fields"].append(
                {"name": "Shipping", "type": "address", "purpose": "R4", "required": False}),
            "html_body": lambda d: self.obj(d, "EmailMessage")["fields"].append(
                {"name": "HtmlBody", "type": "textarea", "purpose": "R11", "required": False}),
            "bcc": lambda d: self.obj(d, "EmailMessage")["fields"].append(
                {"name": "BccAddress", "type": "string", "purpose": "R11", "required": False}),
            "bad_object_name": lambda d: self.obj(d, "Note").update(name="Note;DROP"),
            "no_purpose": lambda d: self.fld(d, "Account", "Name").update(purpose="because"),
            "bad_type": lambda d: self.fld(d, "Account", "Name").update(type="blob"),
            "reference_without_targets": lambda d: self.fld(d, "Account", "ParentId").pop("referenceTo"),
            "required_not_bool": lambda d: self.fld(d, "Account", "Name").update(required="yes"),
            "isdeleted_optional": lambda d: self.fld(d, "Account", "IsDeleted").update(required=False),
            "softdelete_mismatch": lambda d: self.obj(d, "User").update(softDelete=True),
            "owner_without_ownerid": lambda d: self.obj(d, "EmailMessage").update(ownerCheck=True),
            "change_key": lambda d: self.obj(d, "Account").update(changeKey="LastModifiedDate"),
            "duplicate_field": lambda d: self.obj(d, "Profile")["fields"].append(
                dict(self.fld(d, "Profile", "Name"))),
            "unapproved_waiver": lambda d: d.update(waivers=[{"object": "User", "flag": "updateable",
                                                              "approvedBy": "PL", "record": "x"}]),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                with self.assertRaises(ContractError):
                    contract_from_doc(self.mutate(fn))

    def test_architect_waiver_is_accepted(self):
        doc = self.mutate(lambda d: d.update(waivers=[{"object": "User", "flag": "updateable",
                                                       "approvedBy": "Architect", "record": "Issue 9"}]))
        self.assertEqual(contract_from_doc(doc).waivers, (("User", "updateable"),))


class SoqlTest(unittest.TestCase):
    def test_select_is_exactly_the_contract_fields(self):
        acc = contract().object("Account")
        q = soql_select(acc, acc.field_names)
        self.assertEqual(q, "SELECT " + ", ".join(WO_TABLE["Account"].split()) + " FROM Account ORDER BY Id")

    def test_catch_up_literal_is_typed_utc(self):
        acc = contract().object("Account")
        since = dt.datetime(2026, 11, 10, 9, 30, 5, 999, tzinfo=dt.timezone(dt.timedelta(hours=1)))
        q = soql_select(acc, ("Id", "SystemModstamp"), since=since)
        self.assertEqual(q, "SELECT Id, SystemModstamp FROM Account WHERE SystemModstamp >= 2026-11-10T08:30:05Z "
                            "ORDER BY Id")

    def test_count_and_id_only(self):
        self.assertEqual(soql_count(contract().object("Task")), "SELECT COUNT() FROM Task")
        self.assertEqual(soql_id_only(contract().object("Task")),
                         "SELECT Id, IsDeleted, SystemModstamp FROM Task ORDER BY Id")
        self.assertEqual(soql_id_only(contract().object("User")), "SELECT Id, SystemModstamp FROM User ORDER BY Id")

    def test_refusals(self):
        acc = contract().object("Account")
        for fields in (["*"], ["FIELDS(ALL)"], ["ShippingAddress"], ["HtmlBody"], ["NotInContract__c"],
                       ["Name; DELETE"], ["Id", "Id"], [], ["Id, Name"], ["Name FROM User"]):
            with self.subTest(fields=fields), self.assertRaises(ContractError):
                soql_select(acc, fields)
        with self.assertRaises(ContractError):
            soql_datetime(dt.datetime(2026, 11, 10, 9, 0))           # naive
        with self.assertRaises(ContractError):
            soql_select(acc, ["Id"], since="2026-11-10T00:00:00Z")   # string, not a typed value

    def test_parse_soql_accepts_only_generated_shapes(self):
        acc = contract().object("Account")
        for q in (soql_select(acc, acc.field_names), soql_count(acc), soql_id_only(acc),
                  soql_select(acc, ["Id"], since=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))):
            self.assertIsNotNone(parse_soql(q), q)
        for q in ("SELECT Id FROM Account", "select Id from Account ORDER BY Id",
                  "SELECT Id FROM Account WHERE Name = 'x' ORDER BY Id", "SELECT FIELDS(ALL) FROM Account ORDER BY Id",
                  "SELECT * FROM Account ORDER BY Id", "SELECT COUNT() FROM Account ORDER BY Id",
                  "SELECT Id FROM Account ORDER BY Id LIMIT 1", "SELECT Id FROM Account ORDER BY Id; DELETE"):
            self.assertIsNone(parse_soql(q), q)

    def test_effective_object_refuses_missing_required(self):
        acc = contract().object("Account")
        with self.assertRaises(ContractError):
            effective_object(acc, [n for n in acc.field_names if n != "Name"])
        eff = effective_object(acc, [n for n in acc.field_names if n != "MasterRecordId"])
        self.assertEqual(eff.unavailable, ("MasterRecordId",))


class EffectiveSoqlTest(TempDirMixin, unittest.TestCase):
    """AC2: generated SOQL equals the effective contract exactly."""

    def test_unavailable_optional_field_left_out_of_soql(self):
        fake = make_fake(contract(), org_kwargs={"unavailable": ("Opportunity.Opportunity_Service__c",)})
        _, man = self.extract(fake)
        expected_fields = [f for f in WO_TABLE["Opportunity"].split() if f != "Opportunity_Service__c"]
        p0 = man["passes"][0]["objects"]["Opportunity"]["soql"]
        self.assertEqual(p0, "SELECT " + ", ".join(expected_fields) + " FROM Opportunity ORDER BY Id")
        self.assertEqual(man["contract"]["effective"]["Opportunity"]["unavailable"], ["Opportunity_Service__c"])
        for name, spec in man["contract"]["effective"].items():
            self.assertEqual(man["passes"][0]["objects"][name]["soql"],
                             "SELECT " + ", ".join(spec["fields"]) + f" FROM {name} ORDER BY Id")
            since = man["passes"][1]["since"]
            self.assertEqual(man["passes"][1]["objects"][name]["soql"],
                             "SELECT " + ", ".join(spec["fields"]) +
                             f" FROM {name} WHERE SystemModstamp >= {since} ORDER BY Id")


if __name__ == "__main__":
    unittest.main()
