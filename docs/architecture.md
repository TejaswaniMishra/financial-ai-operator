# Financial AI Operator - Architecture Specification

## 1. Executive Summary

`financial-ai-operator` is an enterprise financial operations and reconciliation platform designed to ingest multi-source transaction data, normalize disparate formats, balance immutable double-entry ledgers, and detect financial leakage and discrepancies.

The platform is designed around strict separation between **Deterministic Financial Core Services** and **AI Agent Reasoning Operators**.

---

## 2. Core Architectural Invariants

1. **Deterministic Financial Boundary**:
   - Financial math, transaction matching, ledger posting, and balance checks are 100% deterministic and written in Python using `Decimal`.
   - AI agents NEVER perform mathematical computations directly and NEVER mutate financial records without passing through the authoritative deterministic policy and approval gates.
2. **Service-Agent Decoupling**:
   - Backend services (`services/*`) never import or depend on AI agents (`agents/*`).
   - AI agents interact with services via structured tools with strict Pydantic schemas.
3. **Immutable Audit & Ledger**:
   - Financial entries are append-only.
   - Adjustments must be recorded as explicit compensating journal entries.
   - Every operation produces a structured, tamper-resistant audit event.
4. **Source Record Preservation**:
   - Ingested raw source data is preserved in its original form alongside normalized internal records.
   - External provider transaction IDs are stored separately from internal IDs.

---

## 3. Incremental Development Roadmap

```
Milestone 1 (Current):
  Monorepo Foundation & Configuration
  └── FastAPI Async REST Skeleton + Health/System Diagnostics
  └── Next.js 14 Dark-Mode Fintech Dashboard Shell
  └── Strict Decimal Money & Currency Schemas
  └── SQLAlchemy 2.0 Connection Engine (PostgreSQL / Async SQLite)
  └── Docker Compose & Pytest Async Infrastructure

Milestone 2 (Next):
  Financial Data Model & Ingestion Engine
  └── Normalized Transaction Domain Models & Tables
  └── Double-Entry Ledger Schema (Debits/Credits)
  └── Generic Synthetic Adapters (MockPaymentGateway, MockBank, MockERP)
  └── Transaction Ingestion & Invariant Validation

Milestone 3:
  Deterministic Reconciliation & Discrepancy Engine
  └── 1:1, 1:N Rule-Based Transaction Matcher
  └── Fee Leakage & Timing Discrepancy Detectors
  └── Reconciliation Batches & Discrepancy Resolution Queue

Milestone 4:
  Full-Stack Operations Dashboard
  └── Transaction Graph & Ledger Balance View
  └── Discrepancy Analysis & Adjustment Approvals

Milestone 5:
  AI Financial Operator Integration
  └── Agent Tools & Governance Controller
  └── LLM-backed Investigation & Natural Language Ops
```

---

## 4. Generic Synthetic Integration Architecture

To maintain realistic simulation without claiming live bank connections, the system uses generic synthetic adapters:

| Adapter | Description | Purpose |
|---|---|---|
| `MockPaymentGateway` | Synthetic card/digital wallet processor | Generates payment transactions, gateway processing fees, chargebacks |
| `MockBank` | Synthetic banking settlement feed | Generates batched payout credits, wire fees, account balances |
| `MockERP` | Synthetic general ledger / accounting feed | Generates invoice records, revenue recognition entries |

These adapters emit raw records conforming to realistic payment formats and are processed by the deterministic normalization pipeline into canonical `NormalizedTransaction` records.
