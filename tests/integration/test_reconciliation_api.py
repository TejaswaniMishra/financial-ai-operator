import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from database.seed_data.generator import DataGenerator

@pytest.fixture
async def seeded_db(db_session: AsyncSession):
    generator = DataGenerator(db_session)
    await generator.generate()
    return db_session

@pytest.mark.asyncio
async def test_api_reconciliation_trigger(async_client: AsyncClient, seeded_db: AsyncSession):
    response = await async_client.post("/api/v1/reconciliation/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["matches_created"] > 0
    
    # List runs
    res2 = await async_client.get("/api/v1/reconciliation/runs")
    assert res2.status_code == 200
    assert len(res2.json()) == 1
    
    # List discrepancies
    res3 = await async_client.get("/api/v1/reconciliation/discrepancies")
    assert res3.status_code == 200
    assert len(res3.json()) > 0
