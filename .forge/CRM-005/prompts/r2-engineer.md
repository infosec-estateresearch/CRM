# CRM-005, round 2: Engineer correction

- **Worktree:** `/srv/CRM/worktrees/CRM-005`. The expected HEAD is `5dc1e7f2f147d087097e0799c96a672eee02d44b`; confirm it first. Do not modify `.forge/`. The round-1 brief and scope clarification still apply.
- **Time box:** return by about 20 minutes.

## Blocking (Auditor and Tester): `task-detail-drops-datecompleted`
Put the core `dateCompleted` field back in `layouts/Task/detail.json`, in the same position as the core layout (beside `dateEnd` or on the row after it). Add `dateCompleted` to `activity_policy.CORE_FIELDS["Task"]`. The PL compared all four custom layouts with the core ones in the image: this is the only field that was dropped.

## Archived-email guard: complete attribute coverage (Auditor, Tester and DevSecOps advisories)
These are the core Email fields, verified by the PL in the 10.0.12 image. "(ns)" marks a non-storable field.
- **Varchar:** `name`, `fromString`, `replyToString`, `messageId`, `messageIdInternal`; and, all ns, `subject`, `fromName`, `fromAddress`, `replyToName`, `replyToAddress`, `from`, `to`, `cc`, `bcc`, `replyTo`.
- **Other content:** `addressNameMap` (jsonObject), `bodyPlain` (text), `body` (wysiwyg), `isHtml`, `status`, `hasAttachment`, `dateSent`, `deliveryDate`, `sendAt`.
- **Links:** `fromEmailAddress` (link, so the attribute is `fromEmailAddressId`); `toEmailAddresses`, `ccEmailAddresses`, `bccEmailAddresses`, `replyToEmailAddresses` (linkMultiple, so the attributes are `…Ids`); `attachments` (attachmentMultiple, so `attachmentsIds`).

Extend `PROTECTED_ATTRIBUTES`, in the hook and in the mirrored policy list, to **all** of these attributes:
- `name`, `subject`, `body`, `bodyPlain`, `isHtml`;
- `from`, `to`, `cc`, `bcc`, `replyTo`, `fromString`, `replyToString`, `fromName`, `fromAddress`, `replyToName`, `replyToAddress`, `addressNameMap`;
- `fromEmailAddressId`, `toEmailAddressesIds`, `ccEmailAddressesIds`, `bccEmailAddressesIds`, `replyToEmailAddressesIds`;
- `attachmentsIds`, `hasAttachment`;
- `dateSent`, `deliveryDate`, `sendAt`;
- `messageId`, `messageIdInternal`;
- `status`.

Parent, assignment, teams and users stay editable. Add a static rule that the hook list equals this set exactly, and a broken fixture for it.

## Accepted as documented, not fixed (PL decision)
- **`archived-email-forgeable-on-create`.** Staff can deliberately log a historic email by creating it as Archived. That is legitimate correspondence logging, and the WO does not forbid it. Imported history differs in two ways: it has an `sfId`, and it was created by the ER Import user.

  Add to `docs/ACTIVITIES.md`: "Emails logged by hand are archived, and from then on cannot be changed. They can be told apart from imported Salesforce history by `createdBy` and by the empty `sfId`, which only admins can see."
- **`browser-ac3-ac7-unverified`.** This is the operator stage. No acceptance code is needed in this WO.

Run `python3 -m unittest discover -s tests/unit -v`. Report exact counts and mutation evidence. Finish in the Engineer final message format.
