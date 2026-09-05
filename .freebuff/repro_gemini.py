"""Temporary M4 repro: run the REAL Gemini path (provider + agent validation)
against the discrepancy that produced the FAILED/INVALID attempt.

Read-only: does not write to the database.
"""
import asyncio
import json
import sys
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    from database.connection import AsyncSessionLocal
    from services.investigation.context import ContextBuilder
    from services.investigation.provider import get_llm_provider
    from services.investigation.agent import InvestigationAgent
    from services.investigation.schema import InvestigationResult

    # The discrepancy from the observed FAILED investigation
    discrepancy_id = sys.argv[1] if len(sys.argv) > 1 else "fc262b6e-4e29-4e69-b68d-85f019ca79d2"

    async with AsyncSessionLocal() as session:
        cb = ContextBuilder(session)
        ctx, snapshot, chash = await cb.build_investigation_context(discrepancy_id)

        def collect_ids(d):
            out = []
            if isinstance(d, dict):
                if isinstance(d.get("id"), str):
                    out.append(d["id"])
                for v in d.values():
                    out += collect_ids(v)
            elif isinstance(d, list):
                for i in d:
                    out += collect_ids(i)
            return out

        ids = sorted(set(collect_ids(ctx)))
        print("CONTEXT IDS:", ids)

        agent = InvestigationAgent(session)
        print("PROVIDER:", agent.provider.__class__.__name__)
        prompt = agent._build_prompt(ctx)
        print("PROMPT LENGTH:", len(prompt))

        provider = agent.provider
        result = await asyncio.wait_for(
            provider.generate_structured_investigation(prompt=prompt, context=ctx, schema=InvestigationResult),
            timeout=120,
        )
        print("\n=== PARSED RESULT ===")
        print(json.dumps(result.model_dump(mode="json"), indent=2)[:4000])
        print("\n=== SEMANTIC VALIDATION ===")
        errors = agent._semantic_validation(result, ctx)
        print(json.dumps(errors, indent=2) if errors else "NO ERRORS — would be COMPLETED")

asyncio.run(main())
