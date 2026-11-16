WO: CRM-CLIENT-001R2-BA
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-CLIENT-001R2
KNOWN_COMMIT: <C — the CRM-CLIENT-001R2 delivered candidate; filled in the final version>

# CRM-CLIENT-001R2-BA: independent assessment of the CRM-CLIENT-001R2 real-browser evidence

- **Version:** v0.4 **TEMPLATE**, 2026-11-16. It is part of CRM-CLIENT-001R2 v1.5 (CL-D7, accepted). History: v0.1 is in `793f69b0`, v0.2 (as `CRM-CLIENT-001-BA`) is in `323b7a8c`, and v0.3 (as `CRM-CLIENT-001R-BA`) is in `08758cf0`. It is submitted for approval *of its structure*. **It is not dispatchable.**
- **Final version.** Before dispatch, Rogue commits a final version that fills only the two placeholders, `C` and `<run>`/`<SUMS-SHA256>`. CGPT must approve that exact version; Rogue records it on Issue #65 (FOUNDRY WO contract, *Approval provenance*).
- **Why this WO exists:** CRM-CLIENT-001R2 §2 F10 and §9 S5–S7. The installed ForgeV2 cannot pause one WO for an operator step, so the real-browser verdicts are given in this companion WO, after the operator evidence exists.

## 1. Inputs (immutable)

- **Candidate `C`.** It was delivered by CRM-CLIENT-001R2, with Auditor, Tester and DevSecOps PASS on `C` and an unchanged worktree. `BASE` is `forge/CRM-CLIENT-001R2` at its delivery-record commit, whose code tree equals `C`.
- **Evidence package.** `/srv/CRM/evidence/CRM-CLIENT-001R2/<run>/`, root-owned and read-only to specialists. The sha256 of its `SHA256SUMS` is `<SUMS-SHA256>`, and it was produced by annex B S3–S4 with `cleanup.json` all-true.
- **Acceptance contract.** CRM-CLIENT-001R2 **v1.5** **AC6b**, **AC6c** and **AC12**, with AC4c and AC11 *Pre-launch* as evidenced at S4,, plus annex B2.3, B2a, B4, B6, B8 and B9, verbatim from the approved commit.

## 2. The only permitted change (Engineer): public-safe record only (v0.2)

- Run `C`'s `verify_evidence.py --public-summary` on a scratch copy of the restricted package (AC6c). Commit **only** its outputs `public-summary.json` and `EVIDENCE.md`, together with `SHA256SUMS`, to `docs/evidence/CRM-CLIENT-001R2/<run>/`.
  - `SHA256SUMS` lists relative paths and hashes only, and the sanitiser must accept it.
- **No raw file is committed:**
  - `invocation.txt`, `identity.json`, `isolation.json`, `timestamps.json`, `crmdev-*`/`beta-*`/`cleanup.json`, `scan/*`, `journeys/**`, traces and screenshots all stay in the restricted store `/srv/CRM/evidence/CRM-CLIENT-001R2/<run>/` (root-owned, group `forgev2-pl`, read-only);
  - the committed summary and checksums bind to them.
- **Allowlist:** `docs/evidence/CRM-CLIENT-001R2/<run>/{public-summary.json,EVIDENCE.md,SHA256SUMS}` only.
  - Any change to any CRM-CLIENT-001R2 §4 path, or to anything else, is a **stop**.
  - A code defect found here is ESCALATED to CGPT and is never corrected in this WO.
- **Public-record discipline.** Every specialist's final message is committed to `.forge/CRM-CLIENT-001R2-BA/`. Prompts therefore require citing raw evidence only by relative path, line and sha256, never quoting addresses, URLs, container or network details, or log text.

## 3. Acceptance and roles

| Role | PASS only if |
|---|---|
| Engineer | The three committed files are exactly the `--public-summary` output and the package `SHA256SUMS`, and the sanitiser passed |
| Auditor | The diff from `BASE` touches only the allowlist, and the tree of every other path equals `C`. The committed summary is reproducible from the store, contains none of the annex B6 forbidden items, and its hashes match the raw files |
| Tester | It inspects the **raw package directly in the restricted store**. It verifies `<SUMS-SHA256>` and then `SHA256SUMS` over the full package. It runs `C`'s `verify_evidence.py` on a scratch copy and issues its **own** verdict per journey J1–J5 (AC6b) and on AC12, from the raw files and the trace, never from `result.json` or screenshots alone. A challenge uses the finding key `browser-rerun-<journey>` (annex B6.4) |
| DevSecOps | Inspecting the raw package directly, it checks the final unchanged `C` against the actual security evidence, and confirms that the public record and every committed specialist output are public-safe:<br>• `identity.json` (digests, B2.3 versions, container flags: uid 65534, read-only, CapDrop ALL, `no-new-privileges`, no socket or host network);<br>• `isolation.json` (all forbidden targets failed);<br>• the CSP log;<br>• the scan reports and triage, the CfT binary hash and freshness record, and the no-`/ms-playwright`-process proof;<br>• `cleanup.json` and beta before/after equality;<br>• gitleaks clean |

## 4. Gates and stop conditions

- **Gates:** CGPT exact-version approval of the final version; `C` and `<SUMS-SHA256>` re-verified by Rogue at dispatch; the CRM-CLIENT-001R2 PL result validated.
- **Stop for any of these:** a hash mismatch; a change outside §2; any specialist request for Docker, network or Git; any contact with beta, Salesforce or real data; an exhausted execution limit.
- **Counters.** This WO has its own four-execution counters. Because it can change no §4 path, it cannot be used to bypass CRM-CLIENT-001R2's limits. A bounded repeat (annex B6.4) is a separately approved `CRM-CLIENT-001R2-BA2`, and no further repeat is allowed without a new CGPT decision.

## 5. Reporting

- On PL `DELIVERED`, Rogue validates the PL JSON and the ledger, then returns **READY_FOR_CGPT for CRM-CLIENT-001R2** with: `C`, the BA head, the evidence manifest sha256, the per-journey Tester verdicts, the DevSecOps verdict and the cleanup result.
- The merge candidate is the `forge/CRM-CLIENT-001R2-BA` PR, which contains `C`. CGPT acceptance comes first, and Matt merges. **No beta deployment.**
