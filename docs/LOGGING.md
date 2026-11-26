# ERm logging and audit

**Status:** direction accepted (Architect ruling relayed 2026-11-26, [Issue #91](https://github.com/infosec-estateresearch/CRM/issues/91)). Delivered only by approved Work Orders; nothing here is evidence of implementation.

## Principles

1. Use EspoCRM's native audit, history, sign-in log and application log first.
2. Add structured ERm events only where native records do not cover a required event.
3. Complete coverage, integrity and sensible retention; no unnecessary duplication into the database.
4. UTC timestamps; synchronised time; named individual identities.
5. No passwords, tokens or unnecessary personal data in logs. Debug and SQL logging are off in production.
6. Storage is bounded; security records are protected from ordinary alteration and deletion.
7. **Identity audit is mandatory:** an identity relationship change does not succeed unless its audit record is durably stored.
8. Ordinary diagnostic logging failures may be non-blocking but must be visible.
9. People with host or database access can alter records outside the application. That risk is recorded, and access is restricted.

## Coverage

Firm, contact, group and enquiry lifecycle; every identity relationship change; sign-in success and failure; refused access; user, role and privilege changes; password, key and second-factor changes; external integration access; application errors; imports and exports; backup and restore outcomes; deployments; scheduled job failures; configuration changes.

## Retention (accepted initial values)

| Data | Retention |
|---|---|
| Identity and business audit | life of the record; records are not purged |
| Sign-in records and ERm events | 13 months |
| User action history | 6 months |
| Application log files | 90 days |
| Container logs | size-bounded rotation per service |

A deployment check fails if cleanup settings would remove identity audit records or retention is shorter than stated.

## Structured events

One JSON object per line, written to files by the application. Fields: `ts` (UTC, ISO 8601), `event` (`erm.<area>.<object>.<action>`), `severity`, `outcome`, `app`, `env`, `release`, `actorId`, `actorType`, `firmId`, `groupId`, `contactId`, previous and new identifiers for relationship changes, `requestId`, `method`, `route`. A failure to write a diagnostic event does not break the user's action and is itself reported; principle 7 applies to identity audit records, which are not diagnostic events.

## Graylog (post-MVP architectural requirement)

Estate Research's existing Graylog is the destination for ERm events after MVP.

- MVP: native logging and audit, structured events, secure bounded local storage and this interface. **No forwarding is implemented.**
- ERm does not install or reconfigure Graylog.
- Interface: a host-side forwarder reads the event and application log files and sends them over TLS syslog or GELF, adding application and environment identification. The application never sends to Graylog directly, so Graylog being unavailable cannot affect ERm.
- Post-MVP acceptance: encrypted transport; application, security and operational events; search by FirmID, GroupID, ContactID and actor; dashboards and security alerts; catch-up after an outage; readiness to correlate with other Estate Research applications.
