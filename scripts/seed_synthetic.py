#!/usr/bin/env python3
"""Deterministic synthetic data for the CRM-001 dev stack (standard library only).

All names are generated from invented syllables, postcodes use the
non-geographic "ZZ" area, phone numbers come from Ofcom's drama ranges and
email addresses use the reserved example.test domain. No real data.

Usage:
    python3 scripts/seed_synthetic.py --base-url http://127.0.0.1:8180
    python3 scripts/seed_synthetic.py --dry-run          # counts only, no HTTP

Credentials come from CRM_ADMIN_USERNAME / CRM_ADMIN_PASSWORD.
"""

import argparse
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crm_api  # noqa: E402

DEFAULT_SEED = 1

# Must match custom/Espo/Custom/Resources/metadata/entityDefs/Account.json
TIERS = ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tier 5", "Prospect", "Closed/Ceased Trading"]
INDUSTRIES = ["Solicitor", "Other Legal Service", "Barrister", "Accountant", "Other"]
LEARNING_PLATFORM_ACCESS = ["No", "TLP", "Full Access", "E-Course"]
PRACTICE_MANAGEMENT_SYSTEMS = ["", "PMS Alpha", "PMS Beta", "PMS Gamma", "PMS Delta", "PMS Epsilon"]

BIG_PARENT_BRANCHES = 34
GROUP_PARENTS = 24
GROUP_BRANCH_RANGE = (1, 8)
STANDALONE_FIRMS = 40
CONTACT_COUNT = 600
HELD_BACK_FIRMS = 3
HELD_BACK_CONTACTS = 2

_ONSETS = ["b", "br", "c", "d", "dr", "f", "g", "gr", "h", "k", "l", "m", "n", "p",
           "qu", "r", "s", "st", "t", "th", "v", "w", "z"]
_VOWELS = ["a", "e", "i", "o", "u", "ae", "ou", "y"]
_CODAS = ["", "n", "r", "l", "m", "s", "th", "x", "rk", "nd", "lt"]
_FIRM_SUFFIXES = ["LLP", "Solicitors", "Legal", "& Co", "Chambers", "Partners", "Associates"]
_FIRST_NAMES = ["Alex", "Sam", "Jo", "Chris", "Robin", "Morgan", "Jamie", "Taylor", "Casey",
                "Jordan", "Riley", "Avery", "Quinn", "Rowan", "Sage", "Drew", "Ellis", "Frankie"]
_UNIT_LETTERS = "ABDEFGHJLNPQRSTUWXYZ"

FIRM_PHONE_PREFIX = "+442079460"   # 020 7946 0000-0999 (Ofcom drama range)
CONTACT_PHONE_PREFIX = "+447700900"  # 07700 900000-900999 (Ofcom drama range)
EMAIL_DOMAIN = "example.test"


def _word(rng, syllables):
    text = "".join(rng.choice(_ONSETS) + rng.choice(_VOWELS) for _ in range(syllables - 1))
    text += rng.choice(_ONSETS) + rng.choice(_VOWELS) + rng.choice(_CODAS)
    return text.capitalize()


def _unique_words(rng, count, syllables, taken):
    words = []
    while len(words) < count:
        word = _word(rng, syllables)
        if word.lower() not in taken and len(word) >= 4:
            taken.add(word.lower())
            words.append(word)
    return words


def _postcode(n):
    district = 1 + n // 200
    sector = (n // 20) % 10
    unit = _UNIT_LETTERS[n % 20] + _UNIT_LETTERS[(n * 7 + district) % 20]
    return f"ZZ{district} {sector}{unit}"


def _phone(prefix, n):
    if not 0 <= n <= 999:
        raise ValueError("synthetic phone range exhausted")
    return f"{prefix}{n:03d}"


def _cycled(rng, values, count):
    """Every value at least once (when count allows), then random; shuffled."""
    out = list(values)[:count] + [rng.choice(values) for _ in range(max(0, count - len(values)))]
    rng.shuffle(out)
    return out


def _prefix_matches(values, prefix):
    p = prefix.lower()
    return sum(1 for v in values if v.lower().startswith(p))


def build_dataset(seed=DEFAULT_SEED):
    """Pure function: the full synthetic dataset for a seed."""
    rng = random.Random(seed)
    taken = set()
    top_names = _unique_words(rng, 1 + GROUP_PARENTS + STANDALONE_FIRMS, 3, taken)
    second_names = _unique_words(rng, 1 + GROUP_PARENTS + STANDALONE_FIRMS, 2, taken)
    towns = _unique_words(rng, 60, 2, taken)
    streets = _unique_words(rng, 40, 2, taken)

    firms = []

    def add_firm(name, role, parent_key=None):
        key = f"F{len(firms):03d}"
        firms.append({"key": key, "name": name, "role": role, "parentKey": parent_key})
        return key

    def base(i):
        return f"{top_names[i]} {second_names[i]}"

    # 1 parent with 34 branches
    big = add_firm(f"{base(0)} {rng.choice(_FIRM_SUFFIXES)}", "parent")
    big_towns = rng.sample(towns, BIG_PARENT_BRANCHES)
    for town in big_towns:
        add_firm(f"{base(0)} - {town}", "branch", big)

    # 24 parents with 1-8 branches each
    group_parents = []
    for g in range(GROUP_PARENTS):
        i = 1 + g
        pkey = add_firm(f"{base(i)} {rng.choice(_FIRM_SUFFIXES)}", "parent")
        group_parents.append(pkey)
        n = rng.randint(*GROUP_BRANCH_RANGE)
        if g == 0:
            n = max(n, 2)  # hosts the same-name pair
        for b, town in enumerate(rng.sample(towns, n)):
            if g == 0 and b < 2:
                name = base(i)  # the two same-name branches
            else:
                name = f"{base(i)} - {town}"
            add_firm(name, "branch", pkey)

    # 40 stand-alone firms
    for s in range(STANDALONE_FIRMS):
        i = 1 + GROUP_PARENTS + s
        add_firm(f"{base(i)} {rng.choice(_FIRM_SUFFIXES)}", "standalone")

    tiers = _cycled(rng, TIERS, len(firms))
    industries = _cycled(rng, INDUSTRIES, len(firms))
    access = _cycled(rng, LEARNING_PLATFORM_ACCESS, len(firms))
    codes = list(range(len(firms)))
    rng.shuffle(codes)
    phones = rng.sample(range(1000), len(firms))
    for idx, firm in enumerate(firms):
        firm.update({
            "type": tiers[idx],
            "industry": industries[idx],
            "learningPlatformAccess": access[idx],
            "practiceManagementSystem": rng.choice(PRACTICE_MANAGEMENT_SYSTEMS),
            "billingAddressStreet": f"{rng.randint(1, 250)} {rng.choice(streets)} Street",
            "billingAddressCity": rng.choice(towns),
            "billingAddressPostalCode": _postcode(codes[idx]),
            "billingAddressCountry": "United Kingdom",
            "phoneNumber": _phone(FIRM_PHONE_PREFIX, phones[idx]),
        })

    # ~600 contacts: one per firm first, then random firms
    surnames = _unique_words(rng, 320, 2, taken)
    contact_firms = [f["key"] for f in firms]
    contact_firms += [rng.choice(firms)["key"] for _ in range(CONTACT_COUNT - len(firms))]
    rng.shuffle(contact_firms)
    contact_phones = rng.sample(range(1000), CONTACT_COUNT)
    contacts = []
    for c, firm_key in enumerate(contact_firms):
        first = rng.choice(_FIRST_NAMES)
        last = rng.choice(surnames)
        contacts.append({
            "key": f"C{c:03d}",
            "firstName": first,
            "lastName": last,
            "emailAddress": f"{first}.{last}.{c:03d}@{EMAIL_DOMAIN}".lower(),
            "phoneNumber": _phone(CONTACT_PHONE_PREFIX, contact_phones[c]),
            "firmKey": firm_key,
        })

    held_back = _held_back(rng, firms, contacts)
    probes = _probes(rng, firms, contacts)
    return {"seed": seed, "firms": firms, "contacts": contacts,
            "heldBack": held_back, "probes": probes}


def _held_back(rng, firms, contacts):
    """Near-duplicates of seeded records, NOT created by the seeder (AC7)."""
    out = []
    standalone = [f for f in firms if f["role"] == "standalone"]
    for firm in rng.sample(standalone, HELD_BACK_FIRMS):
        record = account_payload(firm)
        record["name"] = firm["name"].upper()
        record["billingAddressPostalCode"] = firm["billingAddressPostalCode"].lower()
        record.pop("phoneNumber", None)
        out.append({"entityType": "Account", "originalKey": firm["key"], "record": record})
    for contact in rng.sample(contacts, HELD_BACK_CONTACTS):
        record = {
            "firstName": contact["firstName"][0] + ".",
            "lastName": contact["lastName"],
            "emailAddress": contact["emailAddress"].upper(),
        }
        out.append({"entityType": "Contact", "originalKey": contact["key"], "record": record})
    return out


def _probes(rng, firms, contacts):
    """10 search probes (AC6): 2 each of partial firm name, postcode, phone,
    contact email and surname. Each matches at most 5 records by prefix."""
    names = [f["name"] for f in firms]
    standalone = [f for f in firms if f["role"] == "standalone"]
    probes = []

    candidates = []
    for f in standalone:
        first, second = f["name"].split(" ")[:2]
        prefix = f"{first} {second[:2]}"
        if _prefix_matches(names, prefix) <= 5:
            candidates.append((f, prefix))
    for f, prefix in rng.sample(candidates, 2):
        probes.append({"kind": "partial firm name", "entityType": "Account",
                       "query": prefix, "expectKey": f["key"]})
    for f in rng.sample(firms, 2):
        probes.append({"kind": "postcode", "entityType": "Account",
                       "query": f["billingAddressPostalCode"], "expectKey": f["key"]})
    f = rng.choice(firms)
    probes.append({"kind": "phone", "entityType": "Account",
                   "query": f["phoneNumber"], "expectKey": f["key"]})
    c = rng.choice(contacts)
    probes.append({"kind": "phone", "entityType": "Contact",
                   "query": c["phoneNumber"], "expectKey": c["key"]})
    for c in rng.sample(contacts, 2):
        probes.append({"kind": "contact email", "entityType": "Contact",
                       "query": c["emailAddress"], "expectKey": c["key"]})
    person_names = [c["firstName"] for c in contacts] + [c["lastName"] for c in contacts]
    rare = [c for c in contacts if _prefix_matches(person_names, c["lastName"]) <= 5]
    for c in rng.sample(rare, 2):
        probes.append({"kind": "surname", "entityType": "Contact",
                       "query": c["lastName"], "expectKey": c["key"]})
    return probes


SYNTHETIC_NOTE = "Synthetic test record (CRM-001 seed)."


def account_payload(firm):
    keys = ["name", "type", "industry", "learningPlatformAccess", "practiceManagementSystem",
            "billingAddressStreet", "billingAddressCity", "billingAddressPostalCode",
            "billingAddressCountry", "phoneNumber"]
    data = {k: firm[k] for k in keys}
    data["description"] = SYNTHETIC_NOTE
    return data


def contact_payload(contact):
    keys = ["firstName", "lastName", "emailAddress", "phoneNumber"]
    data = {k: contact[k] for k in keys}
    data["description"] = SYNTHETIC_NOTE
    return data


def summary(dataset):
    firms = dataset["firms"]
    roles = collections.Counter(f["role"] for f in firms)
    return {
        "seed": dataset["seed"],
        "firms": len(firms),
        "parents": roles["parent"],
        "branches": roles["branch"],
        "standalone": roles["standalone"],
        "contacts": len(dataset["contacts"]),
        "heldBack": len(dataset["heldBack"]),
        "probes": len(dataset["probes"]),
        "type": dict(sorted(collections.Counter(f["type"] for f in firms).items())),
        "industry": dict(sorted(collections.Counter(f["industry"] for f in firms).items())),
        "learningPlatformAccess": dict(sorted(
            collections.Counter(f["learningPlatformAccess"] for f in firms).items())),
    }


def seed(client, dataset, log=None):
    """Create every firm (parents before branches) and contact. Returns key->id."""
    log = log or (lambda msg: None)
    ids = {}
    ordered = sorted(dataset["firms"], key=lambda f: f["role"] == "branch")
    for firm in ordered:
        data = account_payload(firm)
        if firm["parentKey"]:
            data["parentId"] = ids[firm["parentKey"]]
        ids[firm["key"]] = client.create("Account", data)["id"]
    log(f"created {len(dataset['firms'])} accounts")
    for contact in dataset["contacts"]:
        data = contact_payload(contact)
        data["accountId"] = ids[contact["firmKey"]]
        ids[contact["key"]] = client.create("Contact", data)["id"]
    log(f"created {len(dataset['contacts'])} contacts")
    return ids


def main(argv=None, transport=None, environ=None):
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=environ.get(crm_api.ENV_BASE_URL, ""))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the dataset summary and make no HTTP calls")
    args = parser.parse_args(argv)

    dataset = build_dataset(args.seed)
    if args.dry_run:
        print(json.dumps(summary(dataset), indent=2))
        return 0
    try:
        username, password = crm_api.credentials_from_env(environ)
        client = crm_api.EspoClient(args.base_url, username, password, transport)
        seed(client, dataset, log=lambda msg: print(msg, file=sys.stderr))
    except crm_api.ConfigError as err:
        print(f"seed_synthetic: {err}", file=sys.stderr)
        return 2
    except crm_api.ApiError as err:
        print(f"seed_synthetic: {err}", file=sys.stderr)
        return 1
    print(json.dumps(summary(dataset), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
