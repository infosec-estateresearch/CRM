# Estate Research CRM

Estate Research's self-hosted replacement for Salesforce. It is delivered incrementally under [FOUNDRY](https://github.com/maff0000/foundry) governance, starting with law firms (head office and branches) and their contacts.

**Status: initiation.** Nothing is installed or released. EspoCRM is the leading candidate and has not been selected.

| Record | Purpose |
|---|---|
| [PROJECT-INITIATION-MANDATE.md](PROJECT-INITIATION-MANDATE.md) | Identity, execution target, scope, security context, blockers |
| [PRODUCT-VISION.md](PRODUCT-VISION.md) | Why, for whom, and the Product Goal |
| [PRODUCT-BACKLOG.md](PRODUCT-BACKLOG.md) | Ordered increments. These are not Work Orders. |
| [DECISIONS.md](DECISIONS.md) | Proposed and approved decisions |
| [docs/BUILD.md](docs/BUILD.md) | How the CRM is built, where it runs, its isolation boundary and how it is verified |
| [security/EXTERNAL_CODE_REGISTER.yaml](security/EXTERNAL_CODE_REGISTER.yaml) | External code and images |
| [work-orders/](work-orders/) | Work Orders. Each is approved by exact version on its own Issue. |

Rules:
- GitHub is the authoritative record.
- This repository is public, so it must not contain secrets, host addresses, staff names, customer or firm names, or Salesforce identifiers.
- Salesforce is read-only and is never written to.
