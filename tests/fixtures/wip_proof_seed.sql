-- CRM-WIP-INT-001R2 proof seed (step P2). SYNTHETIC AND OBVIOUSLY FAKE.
-- Load into a DISPOSABLE database AFTER WIP's own migrations 001-023 have been
-- applied in order. Not for any real, beta or production database.
-- Firm S1 (SYNTHFIRM0000000S1): case A (two periods, different values; the latest
--   is 2026-05-31), case B (null yield amounts), closed case C (must not show).
-- Firm S2 (SYNTHFIRM0000000S2): no cases.
-- Firm D  (SYNTHFIRM00000000D): one case, must never appear for S1 or S2.
-- A third id (SYNTHFIRM0000000S3) is deliberately absent.

INSERT INTO wip_company
    (salesforce_account_id, salesforce_account_name, last_seen_in_salesforce_at,
     last_salesforce_sync_at, created_at, updated_at)
VALUES
    ('SYNTHFIRM0000000S1', 'Synthetic Firm S1 LLP', '2026-06-01 00:00:00.000000',
     '2026-06-01 00:00:00.000000', '2026-01-01 00:00:00.000000', '2026-06-01 00:00:00.000000'),
    ('SYNTHFIRM0000000S2', 'Synthetic Firm S2 LLP', '2026-06-01 00:00:00.000000',
     '2026-06-01 00:00:00.000000', '2026-01-01 00:00:00.000000', '2026-06-01 00:00:00.000000'),
    ('SYNTHFIRM00000000D', 'Synthetic Firm D LLP', '2026-06-01 00:00:00.000000',
     '2026-06-01 00:00:00.000000', '2026-01-01 00:00:00.000000', '2026-06-01 00:00:00.000000');

INSERT INTO wip_case
    (wip_company_id, salesforce_account_id, case_reference, case_name, case_type, status,
     opened_at, closed_at, created_at, updated_at)
SELECT c.id, c.salesforce_account_id, v.ref, v.nm, v.typ, v.st, v.opened, v.closed,
       '2026-01-01 00:00:00.000000', '2026-06-01 00:00:00.000000'
FROM wip_company c
JOIN (
    SELECT 'SYNTHFIRM0000000S1' AS sf, 'SYN-A' AS ref, 'Synthetic Matter A' AS nm,
           'Advisory' AS typ, 'open' AS st, DATE '2026-01-12' AS opened, NULL AS closed
    UNION ALL SELECT 'SYNTHFIRM0000000S1', 'SYN-B', 'Synthetic Matter B', 'Advisory', 'open',
           DATE '2026-02-03', NULL
    UNION ALL SELECT 'SYNTHFIRM0000000S1', 'SYN-C', 'Synthetic Matter C (closed)', 'Advisory',
           'closed', DATE '2025-06-01', DATE '2026-03-31'
    UNION ALL SELECT 'SYNTHFIRM00000000D', 'SYN-D', 'Synthetic Matter D', 'Advisory', 'open',
           DATE '2026-03-01', NULL
) v ON v.sf = c.salesforce_account_id;

INSERT INTO wip_case_financial
    (wip_case_id, as_of_date, period_year, period_month, wip_value, fees_invoiced,
     actual_yield, estimated_yield, created_at, updated_at)
SELECT cs.id, f.as_of, f.py, f.pm, f.wip, f.fees, f.act, f.est,
       '2026-06-01 00:00:00.000000', '2026-06-01 00:00:00.000000'
FROM wip_case cs
JOIN (
    SELECT 'SYN-A' AS ref, DATE '2026-04-30' AS as_of, 2026 AS py, 4 AS pm,
           8000.00 AS wip, 1000.00 AS fees, NULL AS act, 12000.00 AS est
    UNION ALL SELECT 'SYN-A', DATE '2026-05-31', 2026, 5, 10250.00, 2500.00, NULL, 12000.00
    UNION ALL SELECT 'SYN-B', DATE '2026-05-31', 2026, 5, 300.50, NULL, NULL, NULL
    UNION ALL SELECT 'SYN-C', DATE '2026-02-28', 2026, 2, 999.00, 1.00, 999.00, 999.00
    UNION ALL SELECT 'SYN-D', DATE '2026-05-31', 2026, 5, 777.00, 7.00, NULL, 777.00
) f ON f.ref = cs.case_reference;
