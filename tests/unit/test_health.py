import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "aiconnex-compiler"
    assert data["version"] == "0.1.0"
    assert data["phase"] == 0
