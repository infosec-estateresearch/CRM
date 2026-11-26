"""CRM-IDINT-001: the route matrix (WO section 3.0), the unit of acceptance.

For each identity relationship, each route that can reach it and each account
kind, the result is either "refused, with nothing changed" or "performed, with
its identity audit record". This module is the single definition of the cells and
what each must do. It has no network and no EspoCRM dependency:

- tests/unit/test_identity.py checks the definition is complete (a missing cell
  fails the unit suite) and consistent with config/access/roles.json;
- tests/acceptance/test_identity.py drives every cell against a live stack.

Expectation values:
  refused    the server must refuse and change nothing, for every kind
  performed  the change must succeed and leave its identity audit record
  either     a route the product may or may not expose for this cell: refused with
             nothing changed, or performed with its audit record; anything else fails
  na         the route cannot reach the relationship; the reason is recorded
"""

RELATIONSHIPS = ["parentFirm", "primaryFirm", "contactFirmLink", "enquiryFirm", "successor"]

ROUTES = [
    "record_create", "record_edit",
    "link_owner_side", "link_other_side", "unlink_owner_side", "unlink_other_side",
    "bulk_link", "mass_update", "delete", "mass_delete", "merge", "csv_import",
    "supplied_id", "retire", "supersede", "cleanup_job",
]

KINDS = ["admin", "staff", "intake", "manager", "import"]

# Human roles of config/access/roles.json (the kinds above are admin, these three, and the importer).
HUMAN_KINDS = ["staff", "intake", "manager"]
ROLE_OF_KIND = {"staff": "ER Staff", "intake": "ER Intake", "manager": "ER Manager", "import": "ER Import"}

# The record kind each relationship's record belongs to (the record that changes).
RECORD_OF = {"parentFirm": "Account", "primaryFirm": "Contact", "contactFirmLink": "Contact",
             "enquiryFirm": "Opportunity", "successor": "Account"}

# Kinds allowed mass update (massUpdatePermission in config/access/roles.json).
MASS_UPDATE_KINDS = ["admin", "manager"]

REFUSED_ROUTES = {
    "bulk_link": "bulk linking would change many identity relationships without a per-record audit",
    "delete": "firms and contacts are never deleted (3.4)",
    "mass_delete": "firms and contacts are never deleted (3.4)",
    "merge": "a merge ends by deleting the source records (3.4)",
    "csv_import": "identifiers are issued only by ERm; import is unavailable (3.7)",
    "supplied_id": "identifiers are issued only by ERm (3.7)",
    "cleanup_job": "the cleanup job removes no firm, contact or audit record (3.6, 3.4)",
}

NA = {
    ("parentFirm", "link_other_side"): "the child's parent is a belongsTo link with no link endpoint; covered by record_edit",
    ("parentFirm", "unlink_other_side"): "the child's parent is a belongsTo link with no link endpoint; covered by record_edit",
    ("primaryFirm", "link_other_side"): "a contact's primary firm is a belongsTo link with no link endpoint; covered by record_edit",
    ("primaryFirm", "unlink_other_side"): "a contact's primary firm is a belongsTo link with no link endpoint; covered by record_edit",
    ("enquiryFirm", "link_other_side"): "an enquiry's firm is a belongsTo link with no link endpoint; covered by record_edit",
    ("enquiryFirm", "unlink_other_side"): "an enquiry's firm is a belongsTo link with no link endpoint; covered by record_edit",
    ("contactFirmLink", "mass_update"): "mass update changes fields, and the firm links are not a mass-updatable field",
    ("parentFirm", "retire"): "retiring changes the identity status only",
    ("primaryFirm", "retire"): "retiring changes the identity status only",
    ("contactFirmLink", "retire"): "retiring changes the identity status only",
    ("enquiryFirm", "retire"): "an enquiry has no identity status",
    ("parentFirm", "supersede"): "superseding sets a successor, not a parent",
    ("primaryFirm", "supersede"): "superseding sets a successor, not a primary firm",
    ("contactFirmLink", "supersede"): "superseding sets a successor, not a firm link",
    ("enquiryFirm", "supersede"): "an enquiry has no successor",
}


def expectation(relationship, route, kind):
    """(expectation, reason) for one cell. Raises KeyError on an unknown axis member."""
    if relationship not in RELATIONSHIPS or route not in ROUTES or kind not in KINDS:
        raise KeyError((relationship, route, kind))
    if route in REFUSED_ROUTES:
        return "refused", REFUSED_ROUTES[route]
    if (relationship, route) in NA:
        return "na", NA[(relationship, route)]
    if route == "mass_update":
        if kind in MASS_UPDATE_KINDS:
            return "either", "mass update is allowed to this kind; it must still be audited"
        return "refused", "this kind has no mass update permission"
    if relationship == "successor":
        if route in ("link_owner_side", "link_other_side", "unlink_owner_side", "unlink_other_side"):
            return "refused", "a successor is changed by editing the record, not by linking"
        if route == "record_create":
            return "refused", "a new record is active and has no successor"
        return "performed", "retire and supersede are open to every role that may edit the record"
    if route in ("record_create", "record_edit"):
        return "performed", "every kind may create and edit this record"
    if relationship == "contactFirmLink":
        return "performed", "a contact's firm links can be linked and unlinked from either side"
    return "either", "a link route the product may or may not expose for this relationship"


def cells():
    """Every (relationship, route, kind) of the matrix, in a stable order."""
    return [(r, route, k) for r in RELATIONSHIPS for route in ROUTES for k in KINDS]


def table():
    """{cell: (expectation, reason)} for every cell."""
    return {c: expectation(*c) for c in cells()}


def problems(definition=None):
    """What is wrong with a matrix definition ({cell: (expectation, reason)}); [] when complete."""
    definition = table() if definition is None else definition
    out = []
    for cell in cells():
        if cell not in definition:
            out.append(f"missing cell {cell}")
            continue
        expect, reason = definition[cell]
        if expect not in ("refused", "performed", "either", "na"):
            out.append(f"{cell}: unknown expectation {expect!r}")
        if not reason:
            out.append(f"{cell}: no reason recorded")
    for cell in definition:
        if cell not in set(cells()):
            out.append(f"unknown cell {cell}")
    return out
