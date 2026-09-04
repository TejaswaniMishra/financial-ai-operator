"""M4 regression: real Gemini investigation end-to-end failure modes.

Reproduces the observed production defect where a real Gemini investigation
landed in FAILED with an INVALID attempt and the UI could never show the
result. The two root causes covered here:

1. ``active_attempt_id`` was assigned from ``attempt.id`` BEFORE the attempt
   row was flushed, so it persisted as NULL and the API/UI could never
   retrieve the attempt result.
2. Gemini occasionally cites a fabricated entity id (e.g. the discrepancy
   *rule code* ``SETTLEMENT_FEE_MISMATCH_001`` used as an ``entity_id``).
   Deterministic evidence-grounding validation must reject that truthfully,
   and every failure mode must produce safe, user-facing errors with no
   provider internals leaked and no 500s.

All agent/API-level tests use fake providers, so they never touch an
external API. The single real-Gemini test lives in test_investigation_gemini.py
and skips when credentials are unavailable.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from database.models.investigation import Investigation, InvestigationStatus, InvestigationAttempt
from database.models.reconciliation import Discrepancy
from services.investigation.schema import InvestigationResult, RootCauseEnum
from services.investigation.provider import InvestigationProviderError
from services.investigation.agent import InvestigationAgent


# ─── Fake providers (never call an external API) ────────────────────────────

def _result_grounded_in_context(context):
    """Build a schema-valid InvestigationResult that cites only real context ids."""
    discrepancy = context.get("discrepancy", {})
    registry = context.get("citable_entities") or []
    evidence = [
        {
            "entity_id": entry["id"],
            "entity_type": entry.get("entity_type", "DISCREPANCY"),
            "field": "id",
            "value": entry["id"],
            "currency": None,
        }
        for entry in registry
    ] or [
        {
            "entity_id": discrepancy.get("id", "dummy"),
            "entity_type": "DISCREPANCY",
            "field": "rule_code",
            "value": discrepancy.get("rule_code", ""),
            "currency": None,
        }
    ]
    return InvestigationResult(
        summary="Grounded summary from fake provider.",
        root_cause_category=RootCauseEnum.UNKNOWN,
        ai_confidence=0.7,
        claims=[{"claim": "Grounded claim", "evidence": evidence}],
        recommendations=["Review manually."],
    )


class FakeProvider:
    """Configurable async provider for agent/API regression tests."""

    def __init__(self, behavior: str = "valid", model: str | None = "fake-model-1"):
        self.behavior = behavior
        self.model = model

    async def generate_structured_investigation(self, prompt, context, schema):
        if self.behavior == "hallucinated":
            # Mirrors the real failure: the id equals a rule-code-like string
            # that is NOT present in the context.
            result = InvestigationResult(
                summary="Summary with a fabricated citation.",
                root_cause_category=RootCauseEnum.UNKNOWN,
                ai_confidence=0.8,
                claims=[
                    {
                        "claim": "Claim citing an invented entity",
                        "evidence": [
                            {
                                "entity_id": "SETTLEMENT_FEE_MISMATCH_001",
                                "entity_type": "SETTLEMENT",
                                "field": "amount",
                                "value": "1.00",
                                "currency": "USD",
                            }
                        ],
                    }
                ],
                recommendations=[],
            )
            self.last_raw_response = json.dumps(result.model_dump(mode="json"))
            return result

        if self.behavior == "schema_invalid":
            raise InvestigationProviderError(
                "The AI response did not match the required investigation schema.",
                kind="SCHEMA",
                details={"schema": ["summary: Field required"]},
            )

        if self.behavior == "transport":
            raise InvestigationProviderError(
                "The AI provider could not complete the investigation request. Please retry.",
                kind="TRANSPORT",
            )

        if self.behavior == "boom":
            raise RuntimeError("internal boom - must never reach the user")

        result = _result_grounded_in_context(context)
        self.last_raw_response = json.dumps(result.model_dump(mode="json"))
        return result


@pytest.fixture
async def discrepancy_fixture(db_session):
    from uuid import uuid4
    from decimal import Decimal

    from database.models.reconciliation import ReconciliationRun, ReconciliationRelationship
    from database.models.transaction import Payment

    run_id = str(uuid4())
    db_session.add(ReconciliationRun(id=run_id))

    pay_id = str(uuid4())
    db_session.add(
        Payment(
            id=pay_id,
            external_id=str(uuid4()),
            order_id=str(uuid4()),
            status="COMPLETED",
            amount=Decimal("100.00"),
            currency="USD",
            provider="STRIPE",
            merchant_id="merchant_1",
        )
    )

    disc_id = str(uuid4())
    db_session.add(
        Discrepancy(
            id=disc_id,
            run_id=run_id,
            rule_code="SETTLEMENT_FEE_MISMATCH_001",
            discrepancy_type="FEE_MISMATCH",
            severity="MEDIUM",
            source_entity_type="PAYMENT",
            source_entity_id=pay_id,
            expected_amount=Decimal("100.00"),
            actual_amount=Decimal("99.00"),
            difference_amount=Decimal("1.00"),
            currency="USD",
        )
    )

    db_session.add(
        ReconciliationRelationship(
            id=str(uuid4()),
            run_id=run_id,
            source_entity_type="PAYMENT",
            source_entity_id=pay_id,
            target_entity_type="SETTLEMENT",
            target_entity_id=str(uuid4()),
            relationship_type="PAYMENT_TO_SETTLEMENT",
            relationship_status="CONFIRMED",
            financial_status="DISCREPANCY",
        )
    )
    await db_session.commit()
    return disc_id


def _make_agent(session, behavior: str):
    agent = InvestigationAgent(session)
    agent.provider = FakeProvider(behavior=behavior)
    return agent


# ─── Agent-level regression ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_result_completes_and_links_active_attempt(db_session, discrepancy_fixture):
    """Valid structured result -> COMPLETED; the active attempt id MUST be
    persisted (regression for the flush-order bug)."""
    agent = _make_agent(db_session, behavior="valid")
    attempt = await agent.run_investigation(discrepancy_fixture)
    await db_session.refresh(attempt, ["investigation"])

    assert attempt.is_valid is True
    assert attempt.investigation.status == InvestigationStatus.COMPLETED
    assert attempt.validated_output is not None
    assert attempt.validated_output["summary"]

    # Regression: active_attempt_id must point at the attempt row.
    assert attempt.investigation.active_attempt_id == attempt.id
    # raw response captured internally for diagnosis.
    assert attempt.raw_llm_response is not None

    # And the DB row agrees (not just the in-memory object).
    from sqlalchemy.future import select as s
    stored = (await db_session.execute(
        s(Investigation).where(Investigation.id == attempt.investigation_id)
    )).scalar_one()
    assert stored.active_attempt_id == attempt.id


@pytest.mark.asyncio
async def test_hallucinated_entity_id_fails_truthfully(db_session, discrepancy_fixture):
    """Exact observed failure mode: model cites SETTLEMENT_FEE_MISMATCH_001
    (the rule code) as an entity_id -> attempt INVALID, investigation FAILED."""
    agent = _make_agent(db_session, behavior="hallucinated")
    attempt = await agent.run_investigation(discrepancy_fixture)
    await db_session.refresh(attempt, ["investigation"])

    assert attempt.is_valid is False
    assert attempt.investigation.status == InvestigationStatus.FAILED
    assert attempt.validated_output is None
    assert attempt.investigation.active_attempt_id == attempt.id

    errors = attempt.validation_errors or {}
    assert "summary" in errors
    assert "entity_ids" in errors
    assert any("SETTLEMENT_FEE_MISMATCH_001" in e for e in errors["entity_ids"])


@pytest.mark.asyncio
async def test_schema_invalid_response_fails_as_failed(db_session, discrepancy_fixture):
    """A response that cannot satisfy the schema -> invalid attempt, FAILED."""
    agent = _make_agent(db_session, behavior="schema_invalid")
    attempt = await agent.run_investigation(discrepancy_fixture)
    await db_session.refresh(attempt, ["investigation"])

    assert attempt.is_valid is False
    assert attempt.investigation.status == InvestigationStatus.FAILED
    errors = attempt.validation_errors or {}
    assert errors.get("kind") == "SCHEMA"
    assert errors.get("summary")
    assert "schema" in errors


@pytest.mark.asyncio
async def test_provider_transport_failure_is_unavailable_and_safe(db_session, discrepancy_fixture):
    agent = _make_agent(db_session, behavior="transport")
    attempt = await agent.run_investigation(discrepancy_fixture)
    await db_session.refresh(attempt, ["investigation"])

    assert attempt.is_valid is False
    assert attempt.investigation.status == InvestigationStatus.UNAVAILABLE
    assert attempt.investigation.active_attempt_id == attempt.id

    # Safe user-facing summary; no provider internals / raw error text.
    errors = attempt.validation_errors or {}
    assert errors.get("kind") == "TRANSPORT"
    assert "503" not in json.dumps(errors)
    assert "APIError" not in json.dumps(errors)
    assert attempt.validated_output is None


@pytest.mark.asyncio
async def test_unexpected_internal_error_is_safe(db_session, discrepancy_fixture):
    agent = _make_agent(db_session, behavior="boom")
    attempt = await agent.run_investigation(discrepancy_fixture)
    await db_session.refresh(attempt, ["investigation"])

    assert attempt.is_valid is False
    assert attempt.investigation.status == InvestigationStatus.UNAVAILABLE
    errors = attempt.validation_errors or {}
    assert "boom" not in json.dumps(errors)
    assert "Traceback" not in json.dumps(errors)
    assert errors.get("kind") == "INTERNAL"


@pytest.mark.asyncio
async def test_retry_appends_attempt_and_updates_status(db_session, discrepancy_fixture):
    """A failed attempt must not corrupt state: retrying appends a new attempt
    and the investigation recovers to COMPLETED."""
    agent = _make_agent(db_session, behavior="hallucinated")
    a1 = await agent.run_investigation(discrepancy_fixture)
    await db_session.refresh(a1, ["investigation"])
    assert a1.investigation.status == InvestigationStatus.FAILED

    agent2 = _make_agent(db_session, behavior="valid")
    a2 = await agent2.run_investigation(discrepancy_fixture)
    await db_session.refresh(a2, ["investigation"])
    assert a2.id != a1.id
    assert a2.is_valid is True
    assert a2.investigation.status == InvestigationStatus.COMPLETED
    assert a2.investigation.active_attempt_id == a2.id

    await db_session.refresh(a2.investigation, ["attempts"])
    assert len(a2.investigation.attempts) == 2


@pytest.mark.asyncio
async def test_context_builder_builds_citable_registry(db_session, discrepancy_fixture):
    """The deterministic citable-entity allowlist is present and grounded."""
    from services.investigation.context import ContextBuilder

    ctx, _, _ = await ContextBuilder(db_session).build_investigation_context(discrepancy_fixture)
    registry = ctx["citable_entities"]
    assert isinstance(registry, list)
    assert len(registry) >= 2  # discrepancy + relationship (+ payment)
    registry_ids = {e["id"] for e in registry}
    assert discrepancy_fixture in registry_ids
    # The registry id must equal the discrepancy's own source entity id entry
    assert all(e["entity_type"] for e in registry)


# ─── API-level regression (through FastAPI, no external calls) ──────────────

@pytest.fixture
def patch_provider(monkeypatch):
    def _patch(behavior: str):
        fake = FakeProvider(behavior=behavior)
        monkeypatch.setattr(
            "services.investigation.agent.get_llm_provider",
            lambda: fake,
        )
        return fake
    return _patch


@pytest.mark.asyncio
async def test_api_valid_run_returns_result_and_active_attempt(
    async_client, db_session, discrepancy_fixture, auth_headers, patch_provider
):
    patch_provider("valid")
    resp = await async_client.post(
        f"/api/v1/investigations/discrepancy/{discrepancy_fixture}/run",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["is_valid"] is True
    assert data["result"] is not None
    assert data["errors"] is None
    inv_id = data["investigation_id"]
    attempt_id = data["attempt_id"]

    # GET investigation shows the active attempt id (regression).
    inv = (await async_client.get(f"/api/v1/investigations/{inv_id}", headers=auth_headers)).json()
    assert inv["active_attempt_id"] == attempt_id

    # Attempt result endpoint returns the validated result.
    att = (await async_client.get(
        f"/api/v1/investigations/{inv_id}/attempts/{attempt_id}", headers=auth_headers
    )).json()
    assert att["status"] == "COMPLETED"
    assert att["is_valid"] is True
    assert att["result"]["summary"]
    # No internal fields leak.
    for internal in ("context_snapshot", "context_hash", "raw_llm_response"):
        assert internal not in att
        assert internal not in inv


@pytest.mark.asyncio
async def test_api_hallucinated_run_fails_safely_no_500(
    async_client, db_session, discrepancy_fixture, auth_headers, patch_provider
):
    """The exact observed defect through the HTTP API: the attempt is invalid,
    the investigation FAILS, but the request is a clean 200 with safe errors."""
    patch_provider("hallucinated")
    resp = await async_client.post(
        f"/api/v1/investigations/discrepancy/{discrepancy_fixture}/run",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["is_valid"] is False
    assert data["result"] is None
    errors = data["errors"] or {}
    assert "entity_ids" in errors
    assert any("SETTLEMENT_FEE_MISMATCH_001" in e for e in errors["entity_ids"])

    inv_id = data["investigation_id"]
    attempt_id = data["attempt_id"]

    inv = (await async_client.get(f"/api/v1/investigations/{inv_id}", headers=auth_headers)).json()
    assert inv["status"] == "FAILED"
    assert inv["active_attempt_id"] == attempt_id

    att = (await async_client.get(
        f"/api/v1/investigations/{inv_id}/attempts/{attempt_id}", headers=auth_headers
    )).json()
    assert att["is_valid"] is False
    assert att["result"] is None
    assert att["errors"]["entity_ids"]


@pytest.mark.asyncio
async def test_api_provider_failure_is_unavailable_no_500(
    async_client, db_session, discrepancy_fixture, auth_headers, patch_provider
):
    """Gemini transport failure -> UNAVAILABLE investigation, clean 200,
    safe errors only (no 503/APIError internals leaked)."""
    patch_provider("transport")
    resp = await async_client.post(
        f"/api/v1/investigations/discrepancy/{discrepancy_fixture}/run",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "UNAVAILABLE"
    assert data["is_valid"] is False
    errors = json.dumps(data["errors"] or {})
    assert "503" not in errors
    assert "APIError" not in errors

    inv = (await async_client.get(
        f"/api/v1/investigations/{data['investigation_id']}", headers=auth_headers
    )).json()
    assert inv["status"] == "UNAVAILABLE"
    assert inv["active_attempt_id"] == data["attempt_id"]


@pytest.mark.asyncio
async def test_agent_model_label_uses_real_model_when_available(db_session, discrepancy_fixture):
    """The attempt record must show the actual Gemini model, not just the
    provider class name, when the provider exposes one."""
    agent = InvestigationAgent(db_session)
    agent.provider = FakeProvider(behavior="valid", model="gemini-3.6-flash")
    assert "gemini-3.6-flash" in agent._model_label()

    agent.provider = FakeProvider(behavior="valid", model=None)
    assert agent._model_label() == "FakeProvider"
