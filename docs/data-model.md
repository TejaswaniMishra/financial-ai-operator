# Financial Domain Data Model Specification

## 1. Monetary Handling Principles

1. **Strict Decimal Precision**:
   - All financial amounts use Python `Decimal` and SQL `NUMERIC(18, 4)` / `NUMERIC(12, 2)`.
   - Floating-point representations (`float`, `double`) are strictly prohibited in models and schemas.
2. **Explicit Currency**:
   - Every monetary figure must specify an ISO-4217 currency code (e.g. `USD`, `EUR`, `GBP`, `INR`).
   - Cross-currency operations are blocked unless an explicit exchange rate model is supplied.
3. **Rounding Rules**:
   - Financial operations use Banker's Rounding (`ROUND_HALF_EVEN`) to minimize statistical bias across high volumes of transactions.

---

## 2. Core Entities (Planned & Incremental)

### A. Money Value Object (`packages.schemas.money.Money`)
- `amount: Decimal`
- `currency: Currency`

### B. Normalized Transaction (`database.models.transaction.TransactionModel`)
- `id: str` (e.g., `tx_18d9f482a91a4f0b`)
- `external_id: str` (e.g., `pg_ch_9841284712`)
- `source: TransactionSource` (`MOCK_PAYMENT_GATEWAY`, `MOCK_BANK`, `MOCK_ERP`, `MANUAL`)
- `type: TransactionType` (`PAYMENT`, `REFUND`, `FEE`, `PAYOUT`, `ADJUSTMENT`)
- `amount: Decimal`
- `currency: Currency`
- `status: TransactionStatus` (`SETTLED`, `PENDING`, `FAILED`, `DISPUTED`)
- `timestamp: datetime` (UTC)
- `raw_payload: JSON` (Immutable snapshot of raw ingested record)
- `fingerprint: str` (SHA-256 hash for idempotent deduplication)

### C. Double-Entry Ledger (`database.models.ledger`)
- **Ledger Account**: `id`, `name`, `type` (`ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`), `currency`, `balance`
- **Journal Entry**: `id`, `reference_id`, `description`, `timestamp`, `posted_by`
- **Ledger Line Item**: `id`, `entry_id`, `account_id`, `type` (`DEBIT`, `CREDIT`), `amount`
- *Invariant*: `SUM(DEBIT) == SUM(CREDIT)` for every journal entry.

### D. Audit Log (`database.models.audit.AuditLogModel`)
- `id: str` (e.g., `aud_18d9f482a91a4f0b`)
- `actor_type: ActorType` (`SYSTEM`, `USER`, `AGENT`, `WORKFLOW`)
- `actor_id: str`
- `action: str`
- `entity_type: str`
- `entity_id: str`
- `previous_state: JSON`
- `new_state: JSON`
- `timestamp: datetime` (UTC)
- `hash: str` (SHA-256 integrity hash chaining)
