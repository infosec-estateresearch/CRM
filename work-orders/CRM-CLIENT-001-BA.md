WO: CRM-CLIENT-001-BA
REPO: infosec-estateresearch/CRM
HOST: DOCKER1
ROOT: /srv/CRM/main
WORKTREES: /srv/CRM/worktrees
BASE: forge/CRM-CLIENT-001
KNOWN_COMMIT: <C — the CRM-CLIENT-001 delivered candidate; filled in the final version>

# CRM-CLIENT-001-BA: independent assessment of the CRM-CLIENT-001 real-browser evidence

- **Version:** v0.1 **TEMPLATE**, 2026-11-16. It is part of CRM-CLIENT-001 v1.2 (CL-D7) for approval *of its structure*. **It is not dispatchable.**
- **Final version.** Before dispatch, Rogue commits a final version that fills only the two placeholders, `C` and `<run>`/`<SUMS-SHA256>`. CGPT must approve that exact version on Issue #59 (FOUNDRY WO contract, *Approval provenance*).
- **Why this WO exists:** CRM-CLIENT-001 §2 F10 and §9 S5–S7. The installed ForgeV2 cannot pause one WO for an operator step, so the real-browser verdicts are given in this companion WO, after the operator evidence exists.

## 1. Inputs (immutable)

- **Candidate `C`.** It was delivered by CRM-CLIENT-001, with Auditor, Tester and DevSecOps PASS on `C` and an unchanged worktree. `BASE` is `forge/CRM-CLIENT-001` at its delivery-record commit, whose code tree equals `C`.
- **Evidence package.** `/srv/CRM/evidence/CRM-CLIENT-001/<run>/`, root-owned and read-only to specialists. The sha256 of its `SHA256SUMS` is `<SUMS-SHA256>`, and it was produced by annex B S3–S4 with `cleanup.json` all-true.
- **Acceptance contract.** CRM-CLIENT-001 v1.2 **AC6b** and **AC12**, plus annex B2.3, B4, B6, B8 and B9, verbatim from the approved commit.

## 2. The only permitted change (Engineer)

- Copy the package's text evidence into `docs/evidence/CRM-CLIENT-001/<run>/`, byte for byte:
  - `SHA256SUMS`, `invocation.txt`, `identity.json`, `isolation.json` and `timestamps.json`;
  - `beta-before.json`, `beta-after.json`, `crmdev-before.json` and `cleanup.json`;
  - `scan/*.json` and `scan/triage.json`;
  - `journeys/<J>/result.json`, `requests.jsonl`, `console.jsonl` and `csp.jsonl`.
- `trace.zip` and the screenshots stay in the store. Their hashes are already covered by the committed `SHA256SUMS`.
- **Allowlist:** `docs/evidence/CRM-CLIENT-001/<run>/**` only.
  - Any change to any CRM-CLIENT-001 §4 path, or to anything else, is a **stop**.
  - A code defect found here is ESCALATED to CGPT and is never corrected in this WO.

## 3. Acceptance and roles

| Role | PASS only if |
|---|---|
| Engineer | The committed files are byte-identical to the store, and `sha256sum -c SHA256SUMS` passes for the committed subset |
| Auditor | The diff from `BASE` touches only the allowlist. The tree of every non-evidence path equals `C`. The committed files match the store |
| Tester | It verifies `<SUMS-SHA256>` and then `SHA256SUMS` over the full store package. It runs `C`'s `verify_evidence.py` on a scratch copy and issues its **own** verdict per journey J1–J5 (AC6b) and on AC12, from the raw files and the trace, never from `result.json` or screenshots alone. A challenge uses the finding key `browser-rerun-<journey>` (annex B6.4) |
| DevSecOps | The final unchanged `C` against the actual security evidence:<br>• `identity.json` (digests, B2.3 versions, container flags: uid 65534, read-only, CapDrop ALL, `no-new-privileges`, no socket or host network);<br>• `isolation.json` (all forbidden targets failed);<br>• the CSP log;<br>• the scan reports, triage and the recorded B8.4 acceptance;<br>• `cleanup.json` and beta before/after equality;<br>• gitleaks clean |

## 4. Gates and stop conditions

- **Gates:** CGPT exact-version approval of the final version; `C` and `<SUMS-SHA256>` re-verified by Rogue at dispatch; the CRM-CLIENT-001 PL result validated.
- **Stop for any of these:** a hash mismatch; a change outside §2; any specialist request for Docker, network or Git; any contact with beta, Salesforce or real data; an exhausted execution limit.
- **Counters.** This WO has its own four-execution counters. Because it can change no §4 path, it cannot be used to bypass CRM-CLIENT-001's limits. A bounded repeat (annex B6.4) is a separately approved `CRM-CLIENT-001-BA2`, and no further repeat is allowed without a new CGPT decision.

## 5. Reporting

- On PL `DELIVERED`, Rogue validates the PL JSON and the ledger, then returns **READY_FOR_CGPT for CRM-CLIENT-001** with: `C`, the BA head, the evidence manifest sha256, the per-journey Tester verdicts, the DevSecOps verdict and the cleanup result.
- The merge candidate is the `forge/CRM-CLIENT-001-BA` PR, which contains `C`. CGPT acceptance comes first, and Matt merges. **No beta deployment.**
