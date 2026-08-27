# Financial AI Operator (`financial-ai-operator`)

An enterprise-grade, AI-powered financial operations and reconciliation platform designed for merchants and modern businesses. The system ingests multi-source financial records, normalizes them, balances double-entry ledgers, performs deterministic transaction matching and discrepancy detection, and lays the governance foundation for autonomous AI operators.

---

## 🏛️ Core Architectural Principle

> **DETERMINISTIC FINANCIAL LOGIC MUST NEVER DEPEND ON AN LLM.**

- **Financial Calculations & Matching**: Implemented in pure, testable deterministic services using Python `Decimal` (never floating-point numbers) with explicit ISO-4217 currency codes.
- **Double-Entry Accounting & Audit**: Append-only ledgers ensuring total debits equal total credits, with cryptographic audit trails for every mutation.
- **AI Agent Decoupling**: AI agents act as an orchestration, reasoning, and investigation layer on top of deterministic service APIs and tools. Services never import or rely on agents.
- **Authoritative Policy Gate**: The controller and policy engine enforce hard financial boundaries, preventing AI agents or automated jobs from performing unauthorized high-risk actions.

---

## 🧱 Repository Structure

```
FinOps/
├── apps/
│   ├── api/                  # FastAPI REST API (Async, typed, versioned routes)
│   └── web/                  # Next.js 14 + React + TypeScript + Tailwind CSS Frontend
│
├── packages/
│   ├── schemas/              # Pydantic v2 domain schemas (Money, System, Health)
│   └── utils/                # Shared utilities (Prefix ID generation, Math, Hashing)
│
├── database/
│   ├── base.py               # SQLAlchemy 2.0 Base & Timestamp mixins
│   └── connection.py         # Dual engine async connection pool (PostgreSQL / SQLite)
│
├── ops/
│   └── docker/               # Docker Compose (PostgreSQL 16, API, Web) & Dockerfiles
│
├── tests/
│   ├── unit/                 # Unit tests (Strict Decimal Money, Settings, Schemas)
│   └── integration/          # API endpoint integration tests (Health, System status)
│
├── config/
│   ├── env.py                # Environment detection
│   └── settings.py           # Pydantic BaseSettings management
│
└── docs/
    ├── architecture.md       # Target and incremental architecture
    └── data-model.md         # Financial domain data model & ledger principles
```

---

## 🚀 Getting Started

### Prerequisites
- Python >= 3.10
- Node.js >= 18.x & npm
- Docker & Docker Compose (Optional for local PostgreSQL)

### 1. Backend Setup

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Run test suite
python -m pytest -v

# Start the FastAPI server
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be accessible at:
- **Root**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/health`
- **System Info**: `http://localhost:8000/api/v1/system/info`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`

### 2. Frontend Setup

```powershell
# Navigate to web application directory
cd apps/web

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

The Web Dashboard will be accessible at:
- `http://localhost:3000`

### 3. Running with Docker Compose

```powershell
docker compose -f ops/docker/docker-compose.yml up --build
```

---

## 🧪 Testing

Run all unit and integration tests:

```powershell
python -m pytest tests/ -v
```

---

## 🔒 Financial Correctness & Safety

1. **Strict Decimal Enforcement**: All monetary fields are validated via Pydantic `Decimal`. Passing raw floats raises a `TypeError`.
2. **Currency Safety**: Arithmetic operations between mismatched currencies raise explicit `ValueError` exceptions.
3. **Deterministic ID Standards**: Identifiers use collision-resistant time-ordered prefixes (`tx_...`, `rec_...`, `aud_...`).
4. **Zero Hardcoded Secrets**: Configuration is managed strictly via environment variables (`.env.example`).
