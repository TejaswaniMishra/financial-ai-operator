# Financial AI Operator

> **An AI-assisted financial operations platform that combines
> deterministic financial processing, reconciliation, investigation,
> governance, approvals, and controlled execution in one auditable
> workflow.**

Financial AI Operator (`financial-ai-operator`) is an enterprise-style
fintech platform designed around a simple rule:

> **Financial facts are deterministic. AI interprets those facts.
> Policies control what may happen. Humans authorize consequential
> actions.**

Instead of placing an LLM directly in the financial decision path, the
system separates financial correctness from AI interpretation.
Authoritative transaction data is processed by deterministic services;
discrepancies are investigated with structured AI; policy and RBAC gates
control financial actions; and consequential actions require authorized
human approval.

------------------------------------------------------------------------

## Why This Project Exists

Modern businesses often have financial information distributed across
payment systems, settlements, refunds, fees, bank transactions,
accounting systems, and operational workflows.

That creates several recurring problems:

-   Financial records arrive from multiple sources and formats.
-   Payment and settlement records do not always reconcile cleanly.
-   Fees, timing differences, missing records, duplicates, and
    configuration issues create exceptions.
-   Finance teams spend significant time investigating why numbers do
    not match.
-   Closing a financial period requires checking many operational
    conditions.
-   Reporting can become unreliable when one-to-many relationships cause
    accidental double counting.
-   Financial actions require stronger controls than a normal AI
    assistant.
-   Auditability and user authorization matter as much as the AI
    explanation.

A generic AI application might do this:

``` text
Financial Data → LLM → Answer
```

Financial AI Operator instead follows:

``` text
Authoritative Financial Data
            ↓
Deterministic Financial Logic
            ↓
Evidence + Context
            ↓
AI Investigation / Interpretation
            ↓
Policy Evaluation
            ↓
Human Authorization
            ↓
Controlled Execution
            ↓
Audit + Notifications
```

This separation is the central architectural decision of the project.

------------------------------------------------------------------------

# Core Engineering Principles

## 1. Deterministic financial logic never depends on an LLM

The system does not ask an LLM to calculate balances, reconcile
transactions, determine monetary differences, or decide whether
financial records match.

Financial calculations and state evaluation are performed by
deterministic backend services using `Decimal` and explicit currency
handling.

## 2. AI is an investigation and interpretation layer

AI is used where language understanding is valuable:

-   explaining discrepancies
-   identifying plausible root causes
-   interpreting evidence
-   generating evidence-grounded recommendations

The AI does not become the source of truth for financial amounts.

## 3. Financial actions are policy-controlled

An AI-generated recommendation does not automatically become a financial
mutation.

The flow is:

``` text
Investigation
    ↓
Recommendation
    ↓
Action Request
    ↓
Policy Engine
    ↓
Approval Requirement
    ↓
Authorized Human
    ↓
Execution Adapter
```

## 4. Authorization is server-side

Roles and permissions are authoritative in the database.

The browser cannot grant itself a role, and the client cannot choose the
actor recorded for a financial action.

## 5. Auditability is part of the domain

Important security and financial state transitions are designed to
remain traceable through persistent records, investigation attempts,
action requests/executions, period-close evaluations, and security
events.

------------------------------------------------------------------------

# Platform Capabilities

  -----------------------------------------------------------------------
  Area                                Capability
  ----------------------------------- -----------------------------------
  Identity                            Signup, login, profile management,
                                      password management

  Authentication                      JWT-based API authentication with
                                      revocation and credential
                                      versioning

  MFA                                 TOTP enrollment, verification,
                                      recovery codes,
                                      disable/regeneration flows

  Authorization                       Database-authoritative RBAC

  Transactions                        Unified read-only financial
                                      transaction workspace

  Reconciliation                      Deterministic transaction matching
                                      and discrepancy detection

  Investigations                      AI-assisted, evidence-grounded
                                      discrepancy investigation

  Exceptions                          Unified exception workspace and
                                      lifecycle state

  Actions                             Action Requests with policy and
                                      human approval controls

  Execution                           Controlled execution
                                      adapter/simulator

  Period Close                        Financial periods with
                                      deterministic readiness checks

  Reporting                           CFO/executive financial analytics
                                      and operational risk metrics

  Notifications                       In-app notifications, unread state,
                                      deep links

  Administration                      User management, roles, activation,
                                      password reset

  Security Audit                      Persistent security event history
                                      and audit UI

  Integrations                        Financial ingestion/integration
                                      foundation; scope depends on the
                                      currently implemented adapters
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# System Architecture

``` text
┌───────────────────────────────────────────────────────────────┐
│                        USER / FINANCE TEAM                    │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                 Next.js + React Web Application               │
│                                                               │
│ Dashboard │ Transactions │ Reconciliation │ Exceptions       │
│ Investigations │ Reports │ Periods │ Actions │ Admin         │
└───────────────────────────────┬───────────────────────────────┘
                                │
                         BFF / Session Boundary
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                         FastAPI API                           │
│                                                               │
│ Authentication → Authorization → Routers → Services          │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                    Domain / Service Layer                     │
│                                                               │
│ Ingestion │ Reconciliation │ Investigation │ Exceptions      │
│ Period Close │ Reporting │ Policy │ Actions │ Notifications   │
└───────────────────────────────┬───────────────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                ▼                                ▼
┌──────────────────────────────┐   ┌─────────────────────────────┐
│   Deterministic Financial    │   │       AI Investigation      │
│           Core               │   │           Layer             │
│                              │   │                             │
│ Decimal calculations         │   │ Context builder             │
│ Matching                     │   │ Gemini provider              │
│ Reconciliation               │   │ Structured output            │
│ Discrepancy detection        │   │ Schema validation            │
│ Period readiness             │   │ Evidence validation          │
│ Reporting aggregation        │   │ Root-cause interpretation    │
└──────────────┬───────────────┘   └──────────────┬──────────────┘
               │                                  │
               └────────────────┬─────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                   Policy + Human Authorization                │
│                                                               │
│ RBAC → Policy Evaluation → Action Request → Approval          │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                     Controlled Execution                      │
│                                                               │
│ Execution Adapter → Result → Audit / Notification             │
└───────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                    PostgreSQL / Test SQLite                   │
│                                                               │
│ Authoritative source records + derived operational state      │
└───────────────────────────────────────────────────────────────┘
```

------------------------------------------------------------------------

# Financial Data Model

The platform models the financial lifecycle around authoritative domain
entities rather than inventing a single generic transaction table.

Core entities include:

-   `Merchant`
-   `Customer`
-   `Order`
-   `Payment`
-   `Refund`
-   `Fee`
-   `Settlement`
-   `SettlementItem`
-   `BankTransaction`
-   `FinancialEvent`
-   `ReconciliationRun`
-   `ReconciliationRelationship`
-   `Discrepancy`
-   `Investigation`
-   `InvestigationAttempt`
-   `PolicyEvaluation`
-   `ActionRequest`
-   `ActionExecution`
-   `FinancialPeriod`
-   `PeriodCloseEvaluation`
-   `Notification`
-   `User`
-   `Role`
-   `UserCredential`
-   `TokenRevocation`
-   `SecurityEvent`

The important distinction is between **source facts** and **derived
operational state**.

``` text
SOURCE FACTS
Payment
Refund
Fee
Settlement
Bank Transaction
      │
      ▼
DETERMINISTIC DERIVED STATE
Reconciliation
Discrepancy
      │
      ▼
AI / OPERATIONAL STATE
Investigation
      │
      ▼
GOVERNANCE STATE
Policy Evaluation
Action Request
      │
      ▼
EXECUTION STATE
Action Execution
```

This preserves financial lineage instead of hiding the origin of a
number behind an AI-generated response.

------------------------------------------------------------------------

# Deterministic Reconciliation

Reconciliation is one of the core financial engines of the platform.

It is intentionally independent of the LLM.

## Reconciliation flow

``` text
Source Records
     ↓
Candidate Discovery
     ↓
Relationship Evaluation
     ↓
Timing / Evidence Rules
     ↓
Financial Evaluation
     ↓
RECONCILED or DISCREPANCY
     ↓
Lineage
```

The reconciliation engine is designed around:

-   immutable source facts
-   deterministic matching
-   explicit financial evidence
-   timing policies
-   discrepancy classification
-   idempotent relationship creation
-   database constraints
-   atomic transactions
-   rollback safety
-   traceable lineage

The system distinguishes **relationship status** from **financial
evaluation status**, so "these records are related" does not
automatically mean "these records financially reconcile."

### Why not use an LLM for reconciliation?

Because financial reconciliation must be:

-   reproducible
-   explainable
-   testable
-   numerically exact
-   auditable

An LLM may produce a plausible answer. That is not enough for a
financial system.

------------------------------------------------------------------------

# AI Investigation Architecture

AI enters the system **after deterministic discrepancy detection**.

``` text
Discrepancy
    ↓
Deterministic Context Builder
    ↓
Financial Evidence
    ↓
Historical / Operational Context
    ↓
LLM Provider Abstraction
    ↓
Gemini
    ↓
Structured Investigation Output
    ↓
Schema Validation
    ↓
Semantic / Evidence Validation
    ↓
Persisted Investigation
```

## What the AI does

The investigation layer can interpret a discrepancy and produce
structured findings such as:

-   root cause
-   confidence
-   explanation
-   supporting evidence
-   recommendations

Root-cause categories include:

-   `UNEXPECTED_FEE`
-   `TIMING_DELAY`
-   `DATA_INGESTION_ERROR`
-   `CURRENCY_FX_RATE_MISMATCH`
-   `SYSTEMIC_PROVIDER_ISSUE`
-   `MISSING_TRANSACTION`
-   `DUPLICATE_TRANSACTION`
-   `PROVIDER_CONFIGURATION_ERROR`
-   `RECONCILIATION_RULE_ERROR`
-   `UNKNOWN`

## What the AI does not do

The model does **not** own:

-   financial calculations
-   source-of-truth transaction values
-   reconciliation decisions
-   database authorization
-   monetary execution
-   role assignment
-   actor attribution

If the LLM is unavailable, the system can preserve a
deterministic/fallback investigation state rather than pretending that
an AI result exists.

## Provider abstraction

The investigation layer uses a provider abstraction so the orchestration
logic is not tightly coupled to a single model vendor.

The implementation includes a Gemini provider and a mock provider for
deterministic testing and environments without external credentials.

------------------------------------------------------------------------

# Evidence Grounding & Prompt Injection Defense

Financial records can contain arbitrary text originating from external
systems.

That text must be treated as **untrusted data**, not as instructions.

The investigation design therefore separates:

``` text
SYSTEM INSTRUCTIONS
        +
DETERMINISTIC CONTEXT
        +
UNTRUSTED FINANCIAL DATA
        ↓
LLM
        ↓
STRUCTURED RESULT
```

The model receives evidence as data to interpret.

Validation then checks whether the generated result conforms to the
expected contract and remains grounded in the supplied evidence.

The system does not store or expose private model chain-of-thought.

------------------------------------------------------------------------

# Deterministic vs AI Responsibilities

  Responsibility               Deterministic System   AI
  --------------------------- ---------------------- ----
  Monetary calculations                 ✓            
  Currency validation                   ✓            
  Transaction matching                  ✓            
  Reconciliation                        ✓            
  Discrepancy detection                 ✓            
  Historical statistics                 ✓            
  Timing evaluation                     ✓            
  Financial lineage                     ✓            
  Evidence construction                 ✓            
  Root-cause interpretation                           ✓
  Explanation                                         ✓
  Recommendation                                      ✓
  Policy evaluation                     ✓            
  Authorization                         ✓            
  Financial execution                   ✓            

This boundary is intentional.

------------------------------------------------------------------------

# Exception Management

The exception workspace provides a unified operational view without
introducing an unnecessary duplicate "Exception" source table.

It brings together relevant state from:

-   discrepancies
-   investigations
-   policy evaluations
-   action requests
-   action executions

The overall exception state is derived from authoritative records and
precedence rules rather than being manually maintained as another source
of truth.

Conceptually:

``` text
Discrepancy
    │
    ├── Investigation
    │
    ├── Policy Evaluation
    │
    └── Action Request
             │
             └── Action Execution
```

This allows a finance user to move from:

**What is wrong?**

to:

**Why is it wrong?**

to:

**What should we do?**

to:

**Who is authorized to do it?**

to:

**What actually happened?**

------------------------------------------------------------------------

# Action Requests & Controlled Execution

Financial actions are deliberately separated from AI recommendations.

A recommendation can result in an Action Request, but the request still
passes through governance.

Example lifecycle:

``` text
PENDING_APPROVAL
       ↓
APPROVED
       ↓
EXECUTION
       ↓
SUCCEEDED
```

Alternative terminal states include rejection or failed execution where
applicable.

## Security boundary

The client cannot simply submit an arbitrary actor identity.

The backend derives the actor from the authenticated session.

Similarly, the client does not get to decide its own:

-   role
-   permissions
-   approval authority

The execution layer is an adapter boundary. The current implementation
can use a simulator for demonstration rather than pretending to perform
real external monetary transfers.

------------------------------------------------------------------------

# Role-Based Access Control

The platform uses database-authoritative RBAC.

## Operator

Designed for day-to-day financial operations.

Can access operational capabilities such as:

-   Dashboard
-   Transactions
-   Reconciliation
-   Discrepancies
-   Investigations
-   Reports
-   Period visibility according to permission configuration
-   Notifications
-   Profile/preferences
-   Investigation execution

An Operator **cannot** perform privileged financial approval/execution
actions.

## Finance Manager

Includes Operator capabilities plus financial governance permissions
such as:

-   approving Action Requests
-   rejecting Action Requests
-   cancelling eligible Action Requests
-   executing authorized financial actions

## Admin

Includes Finance Manager capabilities plus administrative permissions
such as:

-   user management
-   role management
-   security audit access
-   account administration

Roles are stored and evaluated server-side.

JWT claims identify the authenticated user but are not treated as the
authoritative source of role membership.

------------------------------------------------------------------------

# Authentication & Security

Security is implemented as a first-class part of the application.

## Password security

-   Argon2id password hashing
-   centralized password policy
-   no plaintext password persistence
-   password-change flow
-   administrator password reset flow
-   credential versioning

Credential versioning allows password changes/resets to invalidate
previously issued sessions.

## JWT security

The API uses short-lived JWT access tokens with validation for:

-   expiration
-   issuer
-   audience
-   required claims
-   allowed signing algorithm
-   token revocation
-   credential version/session lifecycle

JWTs do not contain authoritative application roles.

## Browser session security

The web application uses a BFF-style boundary.

The browser receives an HttpOnly session cookie instead of storing an
API JWT in:

-   `localStorage`
-   `sessionStorage`

The BFF forwards authenticated requests to the FastAPI backend.

## MFA

The platform supports TOTP-based MFA.

Security measures include:

-   encrypted TOTP secret storage
-   hashed recovery codes
-   single-use recovery codes
-   separate MFA challenge tokens
-   MFA challenge expiration
-   session invalidation through credential versioning
-   MFA security events

## Audit events

Security-sensitive events are persisted through the `SecurityEvent`
model and exposed through an authorized security-audit workspace.

------------------------------------------------------------------------

# Financial Period Close

Financial close is implemented as a controlled state transition:

``` text
OPEN
  ↓
CLOSING
  ↓
CLOSED
```

Before closing, the platform evaluates deterministic readiness
conditions including:

-   unreconciled transactions
-   unresolved exceptions
-   pending investigations
-   pending action requests
-   running action executions

A dedicated `PeriodCloseEvaluation` record provides an audit trail of
the readiness evaluation.

The close operation re-verifies readiness and uses database locking to
protect the transition against concurrent close attempts.

This keeps period close as a deterministic financial control rather than
an LLM decision.

------------------------------------------------------------------------

# CFO & Financial Reporting

The reporting workspace provides read-only analytics over authoritative
financial data.

Current reporting areas include:

-   executive summary
-   financial flow
-   reconciliation analytics
-   exception analytics
-   operational risk
-   trends
-   period analytics
-   breakdowns/comparisons where supported

The reporting layer is designed to avoid common financial reporting
mistakes such as accidentally multiplying payment volume through
one-to-many joins.

Currency boundaries are also respected so values from different
currencies are not silently combined into a meaningless total.

------------------------------------------------------------------------

# Transaction Workspace

The transaction workspace unifies the major authoritative financial
record types:

-   Payments
-   Refunds
-   Fees
-   Settlements
-   Bank Transactions

It provides:

-   server-side pagination
-   search
-   filtering
-   detail views
-   reconciliation state
-   discrepancy state
-   investigation state
-   action state
-   source/derived lineage

The workspace intentionally does not create a second "transaction"
source of truth merely for UI convenience.

------------------------------------------------------------------------

# Notifications

The notification center provides in-app operational notifications with:

-   unread counts
-   notification lists
-   mark-as-read
-   mark-all-as-read
-   deep links into relevant workspaces
-   event-driven producers for important workflow transitions

Examples include:

-   investigation completion
-   action-request state changes
-   period close/blocking events

------------------------------------------------------------------------

# Admin & Security Operations

Authorized administrators can access:

### User Management

-   list users
-   inspect user details
-   activate/deactivate accounts
-   manage roles
-   reset passwords

Administrative protections include safeguards around the final active
Admin account.

### Security Audit Logs

Administrators can inspect persisted security activity and filter
relevant audit events.

This gives the platform a governance layer beyond normal application
logging.

------------------------------------------------------------------------

# Web Application

The frontend is organized as an operational finance workspace.

Major areas include:

``` text
/dashboard
/transactions
/reconciliation
/discrepancies
/investigations
/exceptions
/action-requests
/periods
/reports
/notifications
/profile
/preferences
/admin
/admin/security-events
```

Exact availability of routes is permission-controlled.

The UI supports both light and dark themes while maintaining an
enterprise-finance visual language rather than an intentionally "AI
neon" aesthetic.

------------------------------------------------------------------------

# API Surface

The backend is organized around versioned FastAPI routes.

Major API groups include:

``` text
/api/v1/auth/*
/api/v1/transactions/*
/api/v1/reconciliation/*
/api/v1/investigations/*
/api/v1/exceptions/*
/api/v1/action-requests/*
/api/v1/periods/*
/api/v1/reports/*
/api/v1/notifications/*
/api/v1/admin/*
```

The exact endpoint contract is defined by the backend Pydantic schemas
and route implementations.

Interactive API documentation is available through FastAPI's OpenAPI
interface during local development.

------------------------------------------------------------------------

# Repository Structure

The repository is organized as a monorepo:

``` text
financial-ai-operator/
│
├── apps/
│   ├── api/                    # FastAPI backend
│   └── web/                    # Next.js frontend
│
├── packages/
│   ├── schemas/                # Shared Pydantic/domain contracts
│   ├── utils/                  # Shared utilities
│   └── rbac/                   # Permission vocabulary and role matrix
│
├── services/                   # Domain and deterministic services
│
├── database/                   # SQLAlchemy models/base/connection
│
├── migrations/                 # Alembic migrations
│
├── workflows/                  # Workflow/orchestration definitions
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── scenarios/
│   ├── security/
│   └── agent evaluations/
│
├── docs/                       # Architecture and feature documentation
│
├── ops/
│   └── docker/                 # Docker/deployment assets
│
├── config/                     # Environment/settings configuration
│
├── .env.example                # Safe environment template
└── README.md
```

The exact directory contents should always be treated as the source of
truth; this tree summarizes the architectural organization.

------------------------------------------------------------------------

# Technology Stack

  ------------------------------------------------------------------------------------
  Technology              Role                    Why it is used
  ----------------------- ----------------------- ------------------------------------
  **Python**              Backend/domain logic    Strong ecosystem for financial
                                                  processing, data work, and AI
                                                  integration

  **FastAPI**             REST API                Typed, async-friendly API framework
                                                  with automatic OpenAPI documentation

  **Pydantic v2**         Contracts/validation    Strong request/response validation
                                                  and explicit domain schemas

  **SQLAlchemy 2**        Persistence             Explicit relational data modeling
                                                  and transaction control

  **Alembic**             Migrations              Versioned, repeatable database
                                                  schema evolution

  **PostgreSQL**          Primary database        Transactional integrity,
                                                  constraints, indexing, concurrency
                                                  support

  **SQLite**              Test/local support      Fast isolated automated test
                                                  execution where appropriate

  **Next.js 14**          Web application         Structured React application with
                                                  routing and server/BFF capabilities

  **React**               UI                      Component-based operational
                                                  interface

  **TypeScript**          Frontend typing         Safer API/UI contracts and fewer
                                                  runtime type mismatches

  **Tailwind CSS**        Styling                 Consistent utility-based enterprise
                                                  UI implementation

  **PyJWT**               JWT handling            Explicit token creation/validation
                                                  and lifecycle controls

  **Argon2id**            Password hashing        Modern memory-hard password hashing

  **PyOTP**               MFA                     Standard TOTP implementation

  **cryptography**        Secret protection       Encryption primitives for sensitive
                                                  MFA material

  **Google GenAI /        AI investigation        Structured language-model
  Gemini**                                        interpretation after deterministic
                                                  financial analysis

  **pytest**              Backend testing         Unit/integration/security/workflow
                                                  testing

  **Docker**              Deployment/local        Reproducible application/database
                          infrastructure          environments
  ------------------------------------------------------------------------------------

------------------------------------------------------------------------

# Why the Architecture Is Different From a Generic AI App

A generic AI finance prototype often looks like:

``` text
Upload CSV
   ↓
Send everything to LLM
   ↓
"Here is what I think happened."
```

That approach has serious limitations for financial operations.

Financial AI Operator instead establishes explicit ownership:

``` text
                     ┌────────────────────┐
                     │ Authoritative Data  │
                     └─────────┬──────────┘
                               ↓
                     ┌────────────────────┐
                     │ Deterministic Core │
                     │                    │
                     │ calculations       │
                     │ matching           │
                     │ reconciliation     │
                     │ policy evaluation  │
                     └─────────┬──────────┘
                               ↓
                     ┌────────────────────┐
                     │ AI Investigation   │
                     │                    │
                     │ explanation        │
                     │ root cause         │
                     │ recommendation     │
                     └─────────┬──────────┘
                               ↓
                     ┌────────────────────┐
                     │ Human + RBAC       │
                     │ + Policy Gate      │
                     └─────────┬──────────┘
                               ↓
                     ┌────────────────────┐
                     │ Controlled Action  │
                     └────────────────────┘
```

This makes the AI useful without making the AI the financial authority.

------------------------------------------------------------------------

# Local Development

## Prerequisites

Recommended local tooling:

-   Python 3.10+
-   Node.js 18+
-   npm
-   PostgreSQL for a production-like local environment
-   Docker and Docker Compose if using the containerized environment

## 1. Clone

``` powershell
git clone https://github.com/TejaswaniMishra/financial-ai-operator.git
cd financial-ai-operator
```

## 2. Environment

Copy the example environment configuration and populate the required
local values.

``` powershell
copy .env.example .env
```

Never commit `.env`.

Do not place API keys, JWT secrets, database passwords, or other
credentials in this README.

## 3. Backend dependencies

``` powershell
pip install -r requirements.txt
```

## 4. Database migrations

Run the project's Alembic migration command against the configured
database before using newly introduced schema features.

``` powershell
alembic upgrade head
```

## 5. Start the backend

From the repository root:

``` powershell
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend:

``` text
http://localhost:8000
```

Health check:

``` text
http://localhost:8000/health
```

Versioned health check:

``` text
http://localhost:8000/api/v1/health
```

OpenAPI:

``` text
http://localhost:8000/docs
```

OpenAPI JSON:

``` text
http://localhost:8000/openapi.json
```

## 6. Start the frontend

``` powershell
cd apps/web
npm install
npm run dev
```

The web application normally runs at:

``` text
http://localhost:3000
```

The frontend communicates through the application's BFF/session boundary
rather than exposing backend authentication tokens to browser storage.

------------------------------------------------------------------------

# Docker

The repository includes Docker assets for running the application stack.

``` powershell
docker compose -f ops/docker/docker-compose.yml up --build
```

The exact ports and environment variables should be taken from the
current Docker Compose configuration.

------------------------------------------------------------------------

# Environment Variables

The project uses environment-based configuration rather than hardcoded
credentials.

Important configuration areas include:

``` text
DATABASE_URL
JWT_SECRET_KEY
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
JWT_ISSUER
JWT_AUDIENCE
LLM_PROVIDER
LLM_API_KEY
LLM_MODEL
```

The exact currently supported variables are defined in the project's
settings/configuration implementation and `.env.example`.

### Security rule

Never commit:

-   `.env`
-   API keys
-   database passwords
-   JWT signing secrets
-   Gemini credentials
-   MFA secrets
-   recovery codes

------------------------------------------------------------------------

# Testing

The backend uses automated unit, integration, scenario, and security
tests.

Run the complete backend suite with:

``` powershell
python -m pytest tests/ -v
```

Focused tests can be run by directory or module, for example:

``` powershell
python -m pytest tests/integration/ -v
```

The project also uses frontend verification such as:

``` powershell
cd apps/web
npx tsc --noEmit
npm run build
```

Where browser/E2E verification is available, important workflows are
tested through the real application boundary rather than relying only on
unit mocks.

Examples of high-value tested behavior include:

-   authentication
-   token revocation
-   RBAC authorization
-   privilege escalation prevention
-   password lifecycle
-   MFA lifecycle
-   reconciliation idempotency
-   investigation validation
-   transaction lineage
-   exception aggregation
-   action approval/execution
-   period close concurrency
-   reporting aggregation
-   notification ownership/isolation

> **Note:** The repository's test count should be treated as a
> point-in-time verification result rather than a permanent README
> claim, because the suite changes as development continues.

------------------------------------------------------------------------

# Security Model

The security model can be summarized as:

``` text
Browser
  │
  │ HttpOnly session
  ▼
Next.js BFF
  │
  │ authenticated request
  ▼
FastAPI
  │
  ├── JWT validation
  ├── token revocation
  ├── active-user validation
  ├── RBAC permission check
  │
  ▼
Domain Service
  │
  ├── deterministic financial rules
  ├── policy checks
  └── controlled state transition
```

Important security boundaries include:

-   no browser-accessible JWT storage
-   HttpOnly session cookie
-   Argon2id password hashing
-   token revocation
-   credential-version invalidation
-   TOTP MFA
-   encrypted MFA secrets
-   hashed recovery codes
-   database-authoritative roles
-   explicit permission gates
-   server-derived action actors
-   security event persistence
-   protection against unauthorized financial execution

------------------------------------------------------------------------

# Data Integrity

## Decimal money

Financial values use `Decimal` rather than binary floating-point
arithmetic.

Conceptually:

``` python
Decimal("10.10") + Decimal("20.20")
```

is preferred over:

``` python
10.10 + 20.20
```

for financial calculations.

## Currency safety

Money values carry explicit ISO-4217 currency information.

Operations across incompatible currencies are rejected instead of
silently producing a meaningless amount.

## Idempotency

Reconciliation and other state-changing workflows use database
constraints and deterministic identifiers to prevent duplicate
relationships and repeated financial effects where appropriate.

## Transaction boundaries

Critical mutations are performed inside explicit database transactions
so partial financial state does not become visible after a failed
operation.

------------------------------------------------------------------------

# Deployment Architecture

A production-style deployment can be organized as:

``` text
                    Internet
                       │
                       ▼
              ┌─────────────────┐
              │ Next.js Hosting │
              │   Web + BFF     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ FastAPI Service │
              └────────┬────────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      ┌──────────────┐    ┌──────────────┐
      │ PostgreSQL   │    │ Gemini API   │
      │ Managed DB   │    │ optional AI  │
      └──────────────┘    └──────────────┘
```

For a hackathon/demo deployment, the practical minimum is:

-   hosted frontend
-   hosted FastAPI backend
-   managed PostgreSQL
-   environment-managed secrets
-   database migrations
-   HTTPS
-   correctly configured BFF/backend URLs

For production-grade operation, additional infrastructure is
recommended:

-   managed secrets
-   database backups
-   centralized logs
-   metrics and tracing
-   alerting
-   rate limiting
-   background job/queue infrastructure
-   distributed locking where process-local locking is insufficient
-   stronger operational monitoring
-   real provider integrations
-   disaster recovery procedures

The current project should therefore be described as **hackathon/demo
deployable when its deployment environment is configured correctly**,
rather than automatically claiming full production readiness.

------------------------------------------------------------------------

# Demo Workflow

A strong product demonstration follows the real security model instead
of bypassing it.

## Operator

``` text
Login
  ↓
Dashboard
  ↓
Reconciliation
  ↓
Discrepancy
  ↓
AI Investigation
  ↓
Transactions / Lineage
  ↓
Reports
  ↓
Action Requests
  ↓
Financial approval is blocked
```

This demonstrates that an Operator can investigate financial operations
without receiving unauthorized financial authority.

## Finance Manager

``` text
Login
  ↓
Action Request
  ↓
Pending Approval
  ↓
Approve
  ↓
Approved
  ↓
Execute
  ↓
Succeeded
```

This demonstrates controlled financial authorization.

## Admin

``` text
Login
  ↓
Administration
  ↓
User Management
  ↓
Manage Roles
  ↓
Security Audit Logs
```

This demonstrates governance and identity administration.

The three-role demo is intentionally stronger than using one
all-powerful account because it proves that the RBAC boundary is real.

------------------------------------------------------------------------

# Demo Credentials

Demo credentials should **not** be committed to this repository.

For a private hackathon demonstration, use dedicated demo accounts and
distribute credentials separately.

Recommended demo roles:

  -----------------------------------------------------------------------
  Demo account            Role                    Demonstrates
  ----------------------- ----------------------- -----------------------
  Operator demo           `OPERATOR`              Operational workflows
                                                  and investigation

  Finance demo            `FINANCE_MANAGER`       Financial approval and
                                                  controlled execution

  Admin demo              `ADMIN`                 User/role
                                                  administration and
                                                  security audit
  -----------------------------------------------------------------------

Never use a personal production credential as a public demo credential.

------------------------------------------------------------------------

# Current Limitations

The platform is designed as a serious engineering prototype/hackathon
system, but several areas remain opportunities for production hardening.

Depending on the deployment and currently enabled integrations, these
can include:

-   simulator execution instead of real external monetary execution
-   limited external banking/payment/accounting integrations
-   Gemini provider quota/rate limitations in free-tier environments
-   additional ingestion/provider adapters
-   stronger distributed-worker coordination for multi-process
    deployments
-   production-grade queues/workers
-   centralized observability
-   rate limiting and abuse controls
-   enterprise secrets management
-   operational backup/disaster-recovery configuration
-   broader end-to-end integration coverage

These limitations do not change the core architecture: deterministic
financial processing remains separated from AI interpretation and
financial execution.

------------------------------------------------------------------------

# Roadmap

## Financial Data

-   Expand ingestion adapters
-   Add stronger source validation
-   Improve provider-specific normalization
-   Add additional accounting/banking integrations

## AI

-   Additional LLM providers
-   Better investigation evaluation datasets
-   Improved evidence-grounding evaluation
-   Provider health/fallback strategies
-   More domain-specific investigation workflows

## Operations

-   Richer exception resolution workflows
-   More sophisticated period-close controls
-   Advanced CFO reporting
-   Operational forecasting
-   Better notification routing

## Production Hardening

-   Distributed background workers
-   Queue-based processing
-   Rate limiting
-   Centralized observability
-   Metrics and tracing
-   Managed secrets
-   Backup/recovery automation
-   Stronger multi-instance concurrency controls

------------------------------------------------------------------------

# Engineering Highlights

The strongest engineering decisions in this project are not simply the
number of screens or the presence of an LLM.

They are the boundaries between systems.

### Financial correctness

-   `Decimal`-based monetary calculations
-   explicit currency handling
-   deterministic reconciliation
-   database constraints
-   transactional state transitions

### AI safety

-   AI separated from deterministic financial logic
-   structured LLM output
-   schema validation
-   semantic/evidence validation
-   prompt-injection defense
-   deterministic fallback behavior
-   no private chain-of-thought persistence

### Security

-   Argon2id
-   JWT validation
-   token revocation
-   credential versioning
-   HttpOnly browser sessions
-   TOTP MFA
-   recovery-code hashing
-   DB-authoritative RBAC
-   server-derived financial actors

### Financial governance

-   policy evaluation
-   human approval
-   controlled execution
-   action lifecycle
-   auditability
-   period-close readiness evaluation
-   concurrency protection

### Data architecture

-   authoritative source facts
-   derived state
-   transaction lineage
-   database-level pagination
-   avoidance of N+1 query patterns
-   currency-safe reporting
-   protection against reporting double counting

------------------------------------------------------------------------

# Development Milestones

The platform evolved incrementally rather than being built as a single
monolithic prototype.

High-level milestones include:

``` text
M1   → Monorepo / platform foundation
M2   → Financial domain model
M3   → Deterministic reconciliation
M4   → AI investigation intelligence
M4.x → Real Gemini integration
M8   → Authentication / RBAC / identity security
M9   → Transaction workspace
M10  → Unified exception management
M11  → Financial close / period management
M12  → Financial reporting / CFO analytics
M13  → Ingestion and ingestion hardening
```

Each milestone builds on the previous financial and security boundaries
instead of replacing them with a new architecture.

------------------------------------------------------------------------

# Documentation

Detailed engineering documentation is maintained under `docs/`.

Typical documentation areas include:

-   architecture
-   data model
-   security
-   reconciliation
-   investigation/AI behavior
-   transaction workspace
-   exception management
-   financial close
-   reporting
-   administration

Use the actual files under `docs/` as the source of truth for
implementation-level details.

------------------------------------------------------------------------

# API Design Philosophy

The API follows several principles:

### Explicit contracts

Request and response models are typed and validated.

### Server-side authorization

Every protected business operation is gated by authenticated identity
and the required permission.

### Read-only analytics

Reporting and workspace endpoints do not mutate financial source
records.

### Controlled mutations

Financial mutations go through domain services, policy checks, and
authorization rather than allowing arbitrary database writes from the
frontend.

### No client-controlled financial authority

The frontend cannot decide:

-   who approved an action
-   which role the user has
-   whether an unauthorized action is allowed

The backend determines these values.

------------------------------------------------------------------------

# Example Financial Lifecycle

A complete operational scenario looks like this:

``` text
Payment Received
       │
       ▼
Payment / Settlement / Bank Records
       │
       ▼
Deterministic Reconciliation
       │
       ├───────────────┐
       │               │
   Reconciled      Discrepancy
                       │
                       ▼
               AI Investigation
                       │
                       ▼
                Root Cause +
                Evidence +
                Recommendation
                       │
                       ▼
                 Action Request
                       │
                       ▼
                 Policy Engine
                       │
                       ▼
                Human Approval
                       │
                       ▼
              Execution Adapter
                       │
                       ▼
               Execution Result
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
          Audit               Notification
```

This is the core story of Financial AI Operator.

------------------------------------------------------------------------

# What Makes This Suitable for Fintech

A financial system cannot optimize only for "does the AI give a useful
answer?"

It must also answer:

-   Where did this number come from?
-   Can the calculation be reproduced?
-   Can the source data be traced?
-   Why was this transaction considered discrepant?
-   What evidence supports the investigation?
-   Who is allowed to approve the action?
-   Can the client spoof the approver?
-   What happened after execution?
-   Can the system safely close the financial period?
-   Can security activity be audited later?

Financial AI Operator is designed around those questions.

------------------------------------------------------------------------

# Status

The project currently represents a substantial end-to-end fintech
engineering prototype covering:

-   financial data modeling
-   deterministic reconciliation
-   AI investigation
-   transaction operations
-   exception management
-   controlled financial actions
-   financial close
-   reporting
-   authentication
-   MFA
-   RBAC
-   administration
-   notifications
-   security auditing

Some external integrations and production infrastructure remain
deployment-dependent or on the roadmap.

------------------------------------------------------------------------

# License

Add the project's actual license here if/when one is selected.

Until then, do not claim an open-source license that is not present in
the repository.

------------------------------------------------------------------------

# Author

**Tejaswani Mishra**

B.Tech --- Computer Science & Engineering

Built as a fintech/AI engineering project focused on deterministic
financial systems, secure AI orchestration, and human-governed financial
operations.

------------------------------------------------------------------------

## Final Design Principle

> **AI should make financial operations easier to understand --- not
> make financial systems less deterministic.**
