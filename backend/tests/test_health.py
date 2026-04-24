import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from backend.main import app
from backend.core import bq_client as bq_module


@pytest.mark.asyncio
async def test_health_ok():
    with patch.object(bq_module, "get_bq_client") as mock_client:
        mock_client.return_value.project = "fpa-t-494007"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["bq_project"] == "fpa-t-494007"


@pytest.mark.asyncio
async def test_health_no_credentials():
    import google.auth.exceptions
    with patch.object(bq_module, "get_bq_client") as mock_client:
        mock_client.side_effect = google.auth.exceptions.DefaultCredentialsError("no creds")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 500
