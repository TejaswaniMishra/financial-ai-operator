import asyncio
import sys
import json

async def run_once(discrepancy_id, n):
    from database.connection import AsyncSessionLocal
    from services.investigation.context import ContextBuilder
    from services.investigation.agent import InvestigationAgent
    from services.investigation.schema import InvestigationResult

    async with AsyncSessionLocal() as session:
        cb = ContextBuilder(session)
        ctx, _, _ = await cb.build_investigation_context(discrepancy_id)
        agent = InvestigationAgent(session)
        prompt = agent._build_prompt(ctx)
        provider = agent.provider
        try:
            result = await asyncio.wait_for(
                provider.generate_structured_investigation(prompt=prompt, context=ctx, schema=InvestigationResult),
                timeout=120,
            )
            errors = agent._semantic_validation(result, ctx)
            if errors:
                print(f"run {n}: SEMANTIC-FAIL entity_ids={[e for e in errors.get('entity_ids', [])]}")
            else:
                cited = sorted({ev.entity_id for c in result.claims for ev in c.evidence})
                print(f"run {n}: OK cited={cited} rc={result.root_cause_category}")
        except Exception as e:
            print(f"run {n}: PROVIDER-ERROR {type(e).__name__}: {str(e)[:120]}")

async def main():
    did = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    for i in range(1, count + 1):
        await run_once(did, i)

asyncio.run(main())
