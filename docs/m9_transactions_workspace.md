# M9 — Transactions & Financial Data Workspace

## Overview

M9 turns the existing financial domain into a unified, read-only operational
workspace. A finance user can inspect every authoritative financial record
(payments, refunds, fees, settlements, bank transactions), understand its
current state, and trace it through the system — from source facts through
reconciliation, discrepancies, investigations, and controlled action flows.

The backend remains the single source of truth. The workspace is strictly
**read-only**: it never mutates financial facts, never bypasses the Policy
Engine, and never invents data. Derived state (reconciliation, discrepancy,
investigation, action) is always computed by the backend and clearly separated
from authoritative financial facts.

## Transaction read architecture

There is deliberately **no new "Transaction" model**. The five authoritative
tables are the domain truth:

| record_type          | table                | status source       |
|----------------------|----------------------|---------------------|
| `PAYMENT`            | `payments`           | `status`            |
| `REFUND`             | `refunds`            | `status`            |
| `FEE`                | `fees`               | `fee_type` (fees have no lifecycle status) |
| `SETTLEMENT`         | `settlements`        | `status`            |
| `BANK_TRANSACTION`   | `bank_transactions`  | `status`            |

The unified list query is a deterministic SQL `UNION ALL` over these tables
with a common column shape (id, record_type, external_id, merchant_id,
provider, amount, currency, status, created_at). Amounts are cast to a common
`Numeric(20,4)`; settlements contribute `expected_net_amount` and bank
transactions contribute `bank_provider` via per-table column maps.

## API endpoints

All endpoints require authentication and `VIEW_TRANSACTIONS` (present for
OPERATOR, FINANCE_MANAGER, ADMIN in the deterministic role matrix; the JWT
never carries roles — authorization is DB-resolved).

| Endpoint | Description |
|---|---|
| `GET /api/v1/transactions` | Paginated, filtered, searchable list |
| `GET /api/v1/transactions/{id}` | Authoritative detail + derived state |
| `GET /api/v1/transactions/{id}/lineage` | SOURCE/DERIVED lineage timeline |

The pre-existing endpoints `GET /api/v1/transactions/payments` and
`GET /api/v1/transactions/payments/{id}/lineage` remain unchanged; static
`/payments*` routes are registered before the dynamic `/{id}` route so there
is no path conflict.

## Filters

All filters are validated server-side; malformed values return 422.

- `record_type` — one of `PAYMENT`, `REFUND`, `FEE`, `SETTLEMENT`, `BANK_TRANSACTION`
- `status` — exact status string; excludes fees (fees have no lifecycle status)
- `currency` — 3-letter code
- `merchant_id` — domain ID (prefixed, ≤ 64 chars)
- `date_from` / `date_to` — ISO-8601 datetimes on `created_at` (`date_from <= date_to` enforced)
- `min_amount` / `max_amount` — inclusive amount bounds (`min <= max` enforced)
- `reconciled` — `true`/`false`; existence of a `ReconciliationRelationship` referencing the record as source or target
- `has_discrepancy` — `true`/`false`; existence of a `Discrepancy` referencing the record
- `search` — case-insensitive substring over record id, external id, and merchant name (OR semantics)

Counts (`summary`) and `total` reflect the exact active filter set, so the
frontend KPI cards always show real backend numbers.

## Pagination and ordering

- `limit` ∈ [1, 200] (default 50), `offset` ≥ 0
- Deterministic ordering: `created_at DESC, id DESC` — applied at the database
  level on the union, so pages never shift or repeat.
- Response shape: `{ items, total, limit, offset, summary }`.

## Lineage

`GET /api/v1/transactions/{id}/lineage` builds the deterministic chain from
the existing relationships only — nothing is implied:

- **SOURCE** nodes (authoritative financial facts): ORDER, PAYMENT, REFUND,
  FEE, SETTLEMENT_ITEM, SETTLEMENT, BANK_TRANSACTION — resolved through the
  real foreign keys (payment → settlement items → settlements → bank
  transactions; refunds and fees on payments; settlement ↔ bank).
- **DERIVED** nodes (state computed by the backend): RECONCILIATION
  relationships, DISCREPANCY, INVESTIGATION, ACTION_REQUEST,
  ACTION_EXECUTION.

Every node carries type, id, status, amount/currency where applicable,
timestamp, and a small safe detail payload. SOURCE nodes always precede
DERIVED nodes in the response so the UI can render them as distinct regions.

## Detail

`GET /api/v1/transactions/{id}` resolves the record across the five tables
(404 if absent) and returns:

- identity: id, record_type, external_id, merchant, provider
- financial facts: amount, currency, status, created_at / updated_at
- relationships that actually exist: order + customer (payments), related
  records (refunds/fees of a payment; payment of a refund; payments + bank
  transactions of a settlement; settlement of a bank transaction; payment/
  settlement of a fee)
- derived state: reconciliation relationships (+ run status), discrepancies,
  investigation, action requests, action executions

## RBAC

- Unauthenticated → 401.
- All fixed roles hold `VIEW_TRANSACTIONS` per the deterministic matrix →
  200.
- The workspace exposes **no mutation endpoints**; POST/PUT/DELETE return 405.
- Roles are never taken from the client or the JWT; the backend resolves them
  from the database on every request.

## Security boundaries

- Read-only contract: no financial mutation, no Policy Engine bypass, no
  investigation-engine duplication.
- Response hygiene: no ORM objects, no password/hash/token/secret fields, no
  LLM internals (`raw_llm_response`, `context_snapshot`, prompts). The test
  suite asserts these strings never appear in any response body.
- Frontend never stores the JWT: session rides the HttpOnly `fao_session`
  cookie through the BFF; `localStorage`/`sessionStorage` are not used for
  authentication.
- No secrets in URLs; filters travel as ordinary query parameters only.

## Query / performance considerations

- Pagination happens at the database level (`LIMIT/OFFSET` on the union) —
  the browser never receives the full table.
- Merchant names and derived reconciliation/discrepancy state are fetched
  with a small constant number of `IN`-queries per page — no N+1.
- Detail/lineage use explicit eager loads and targeted `WHERE id =` queries.
- No new indexes were required for this milestone: the union filters use
  existing primary keys and the existing `created_at`/status columns, and the
  workspace runs on the current dataset scale. If the dataset grows
  materially, the union order-by benefits from composite `(created_at, id)`
  indexes per table.

## Tests

`tests/integration/test_transactions_workspace.py` (25 tests):

- list, empty list, real records, deterministic ordering, pagination
- search by id and by merchant name
- every filter individually, plus combined filters
- malformed-filter rejection (bad type, limits, offsets, date order, amount order)
- RBAC: 401 unauthenticated; 200 for OPERATOR / FINANCE_MANAGER / ADMIN
- read-only guarantee: 405 for POST/PUT/DELETE
- detail: full derived state, refund/settlement records, 404, sensitive-field hygiene
- lineage: SOURCE before DERIVED, real relationships only, 404, 401

## Known limitations

- Fees carry `fee_type` as their displayed status and are excluded from the
  `status` filter (they have no lifecycle status column).
- The `status` filter is exact-match; fuzzy status search is not supported.
- Reconciliation/discrepancy state is resolved per page with IN-queries;
  extremely deep lineages (many hundreds of related records for one record)
  are bounded by the existing domain sizes.
- Search is substring-based (no full-text index); adequate for the current
  scale, with pagination keeping each request bounded.