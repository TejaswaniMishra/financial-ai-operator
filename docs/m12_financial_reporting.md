# M12 — Financial Reporting & CFO Analytics Workspace

## Overview

M12 provides a deterministic management-level view of the financial operation. It is a **read-only analytics layer** built on top of the authoritative M1–M11 data models. No financial state is mutated by any reporting operation.

---

## Core Architectural Principle

> **Backend owns all authoritative calculations. The frontend only visualizes backend results.**

All financial figures originate from direct SQL aggregations against the authoritative source tables. LLMs are not involved in any financial calculation.

---

## Architecture: Read-Model Pattern

```
Authoritative Tables (Payment, Settlement, Discrepancy, etc.)
        ↓
Reporting Query Service (services/reporting.py)
        ↓
Typed Pydantic Schemas (packages/schemas/reporting.py)
        ↓
Reporting API (apps/api/routes/reports.py — GET only)
        ↓
CFO Analytics UI (apps/web/app/(authenticated)/reports/page.tsx)
```

The service layer queries source tables directly using SQLAlchemy aggregation (`func.sum`, `func.count`, `GROUP BY`). No separate reporting tables are introduced.

---

## Metric Definitions

Every financial metric is defined precisely. No informal accounting terms are used.

| Metric | Source Table | Formula / Query Semantics | Currency | Date Boundary |
|---|---|---|---|---|
| `payment_volume` | `payments` | `SUM(amount) GROUP BY currency` | Per ISO 4217 currency code | `processed_at` |
| `refund_volume` | `refunds` | `SUM(amount) GROUP BY currency` | Per currency | `processed_at` |
| `fee_volume` | `fees` | `SUM(amount) GROUP BY currency` | Per currency | Linked via payment `processed_at` or settlement `settlement_date` |
| `settlement_volume` | `settlements` | `SUM(gross_amount) GROUP BY currency` | Per currency | `settlement_date` |
| `bank_transaction_volume` | `bank_transactions` | `SUM(amount) GROUP BY currency` | Per currency | `transaction_date` |
| `reconciled_count` | `reconciliation_relationships` | `COUNT WHERE financial_status = RECONCILED AND source_entity_type = PAYMENT` | N/A (count) | All time (relationships are immutable) |
| `unreconciled_count` | `payments` | `COUNT WHERE id NOT IN (reconciled payment IDs)` | N/A | Filtered by payment `processed_at` |
| `reconciliation_rate` | Derived | `reconciled_count / total_payments_eligible` | N/A | Same as payment window |
| `discrepancy_count` | `discrepancies` | `COUNT(DISTINCT id)` | N/A | `created_at` |
| `exception_state` | `discrepancies` + joins | Same CASE expression as `services/exceptions.py` | N/A | N/A |
| `unresolved_exception_count` | Same join | `COUNT WHERE state NOT IN [RESOLVED]` | N/A | N/A |

> **Important naming rules:**
> - `payment_volume` is NOT called "revenue"
> - `settlement_volume` is NOT called "cash balance"
> - No derived metric is called "profit" or "net income"

---

## Currency Semantics

**Currencies are never aggregated across ISO codes.**

- Every endpoint that returns monetary amounts groups by `currency` and returns a list of `AmountByCurrency` objects.
- A `currency_filter` query parameter allows narrowing to a single currency.
- The UI explicitly renders each currency independently.
- Cross-currency comparison is handled by the `/reports/comparison` endpoint, which only compares currencies that appear in both periods.

---

## Double-Counting Safeguards

The relationship `Payment → SettlementItem (1:N) → Settlement` creates a risk of double-counting payment amounts if joins are used naively.

**Guards implemented:**

1. `payment_volume` queries `Payment` table directly via `SELECT currency, SUM(amount) FROM payments GROUP BY currency`. `SettlementItem` is never joined when computing payment totals.
2. `settlement_volume` queries `Settlement.gross_amount` directly — not the sum of `SettlementItem.amount`.
3. For breakdown analysis, refund amounts are derived from the `Refund` table (joined via `payment_id`), not from payment records, to avoid mixing amounts.
4. Integration test `test_no_double_counting_payment_via_settlement_items` explicitly creates 1 Payment → 3 SettlementItems and verifies `payment_count = 1`, not 3.

---

## Reconciliation Semantics

M12 reuses the authoritative M3 reconciliation model:

- **`ReconciliationRelationship.financial_status`** is the single source of truth:
  - `RECONCILED` → matched
  - `DISCREPANCY` → mismatch found
  - `UNRESOLVED` → not yet evaluated
- M12 does NOT create an alternative reconciliation interpretation.
- Discrepancy amounts come from `Discrepancy.difference_amount`.

---

## Exception Semantics

M12 reuses the identical `CASE` expression from `services/exceptions.py` (`_determine_overall_state`) to derive `OverallExceptionState` from the investigation/policy/action/execution chain.

- No alternative exception-state logic is introduced.
- Exception counts by state are computed via the same SQL subquery pattern used by the M10 workspace.

---

## Period Semantics

M12 reuses M11's `FinancialPeriod` and `PeriodCloseEvaluation`:

- When `period_id` is provided to a reporting endpoint, the period's exact `start_date` and `end_date` are fetched and used as the query boundaries.
- Period readiness is read from the latest `PeriodCloseEvaluation` — no close logic is re-evaluated.
- The `/reports/periods` endpoint is a read-only view of period metadata and associated counts.

---

## Date Semantics

- All timestamps stored in the database are UTC.
- All date boundaries in API parameters must be ISO 8601 UTC strings.
- Trend analytics buckets are UTC date strings (`%Y-%m-%d` for day, `%Y-W%W` for week, `%Y-%m` for month).
- The `TrendResponse` object always includes `"timezone": "UTC"`.

---

## Trend Calculations

Time-series aggregations use `func.strftime(format, date_column)` — SQLite-compatible date bucketing.

Supported granularities:
- `day` → `%Y-%m-%d`
- `week` → `%Y-W%W` (ISO week number)
- `month` → `%Y-%m`

Supported metrics:
- `payment_count`, `payment_volume`
- `refund_count`, `refund_volume`
- `settlement_count`, `settlement_volume`
- `exception_count`

Invalid metrics and granularities return HTTP 400.

---

## Period Comparison Logic

The `/reports/comparison` endpoint:

1. Queries `payment_volume` and `refund_volume` for both periods independently.
2. Identifies the union of currencies appearing in either period.
3. For each currency: computes `current_value`, `previous_value`, `absolute_delta = current - previous`.
4. `percentage_delta = (delta / previous_value) × 100` — returns `null` if `previous_value = 0` (zero-denominator safe).
5. **Never subtracts USD from INR or any cross-currency comparison.**

---

## RBAC

New permission: `VIEW_REPORTS`

| Role | VIEW_REPORTS |
|---|---|
| `OPERATOR` | ✅ |
| `FINANCE_MANAGER` | ✅ (inherited) |
| `ADMIN` | ✅ (inherited) |

All 8 reporting endpoints enforce this permission. Unauthenticated requests → 401. Authenticated without permission → 403.

---

## API Reference

Base prefix: `/api/v1/reports`

| Method | Path | Description | Permission |
|---|---|---|---|
| GET | `/summary` | Executive KPI summary | VIEW_REPORTS |
| GET | `/financial-flow` | Pipeline stage volumes | VIEW_REPORTS |
| GET | `/reconciliation` | Reconciliation analytics | VIEW_REPORTS |
| GET | `/exceptions` | Exception state/type/root-cause analytics | VIEW_REPORTS |
| GET | `/operations` | Operational risk indicators (counts only) | VIEW_REPORTS |
| GET | `/periods` | Per-period metrics table | VIEW_REPORTS |
| GET | `/trends` | Time-series aggregation | VIEW_REPORTS |
| GET | `/comparison` | Two-period comparison | VIEW_REPORTS |
| GET | `/breakdowns` | Breakdown by provider/method/merchant | VIEW_REPORTS |

All endpoints are GET-only. No POST/PUT/PATCH/DELETE exists on `/reports/*`.

---

## Frontend

Route: `/reports`

Sections:
1. **Executive KPIs** — currency-isolated payment/refund/settlement volume cards + operational counts. Each card links to the relevant operational workspace.
2. **Payment Volume Trend** — Recharts AreaChart with daily aggregation from `/reports/trends`.
3. **Financial Flow** — Recharts BarChart showing volumes at each pipeline stage per currency.
4. **Reconciliation** — Reconciled/unreconciled counts, rate progress bar, discrepancy count link.
5. **Exception States** — PieChart of exception state distribution with links to `/exceptions`.
6. **Operational Risk Indicators** — KPI cards linking to `/investigations`, `/action-requests`, `/periods`.
7. **Period Performance** — Table of recent periods with readiness, blocker count, and transaction/exception counts.

Filters:
- Date preset: Last 7d / 30d / 90d / All time
- Currency (dynamically populated from returned data)

---

## Performance Considerations

- All aggregations are performed in SQL (`SUM`, `COUNT`, `GROUP BY`) — no Python-side iteration over raw records.
- Multiple dashboard sections are loaded in parallel via `Promise.all`.
- `COUNT(DISTINCT id)` prevents phantom counts from multi-join scenarios.
- Trend queries use indexed date columns for efficient range filtering.

---

## Known Limitations

1. **Trend granularity uses `strftime`** — this works correctly on SQLite (development). On PostgreSQL (production), `func.date_trunc` would be more idiomatic but is not used here to maintain DB-agnostic code. This should be revisited if the production database is Postgres.
2. **Trend data is not currency-aware for `exception_count`** — exceptions do not have a single canonical currency (the discrepancy amount may be null), so this metric is returned without currency grouping.
3. **Fee date boundary** — fees do not have a direct `processed_at`; they are linked via `payment_id` or `settlement_id`. When filtering by date, fees are included if any linked payment/settlement falls within the window.
4. **Breakdown performance on large datasets** — the `/breakdowns` endpoint issues one subquery per dimension value to count refunds and exceptions. This should be refactored to a single group-by query for high-cardinality dimensions (e.g., `merchant_id`) at scale.
