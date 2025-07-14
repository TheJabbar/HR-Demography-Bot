import pytest
import pandas as pd
import sqlite3
from httpx import ASGITransport, AsyncClient
from main import app, insert_api_data_to_db, download_minio_data
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import status
from os import getenv
from dotenv import load_dotenv
load_dotenv('.env', override=True)

valid_payload = {"query": "Buatkan laporan demografi terbaru"}
valid_headers = {
    "x-api-key": getenv('X_API_KEY', 'test-api-key'),
    "Content-Type": "application/json",
    "Accept": "application/json"
}
endpoint = "/HCM_Insight/get_insight_api"
test_db = "/test.db"
test_table = "test_table"
test_json = "/test.json"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def test_client():
    async with AsyncClient(
        base_url="http://test",  # Changed from https to http
        transport=ASGITransport(app=app)
    ) as client:
        yield client


@pytest.mark.anyio
async def test_health_check(test_client):
    response = await test_client.get("/ht")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_valid_payload_success(test_client):
    with patch('main.telkomllm_generate_sql') as mock_gen, \
         patch('main.telkomllm_infer_sql') as mock_infer, \
         patch('main.sqlite3.connect') as mock_db:
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.side_effect = [
            [(0, 'id', 'INTEGER', 0, None, 1)],  # PRAGMA table_info response
            [(1, 'Sample Data')]  # Query result
        ]
        mock_db.return_value = mock_conn
        mock_gen.return_value = "SELECT * FROM employee_demography"
        mock_infer.return_value = "Mocked insight"
        response = await test_client.post(
            url=endpoint,
            headers=valid_headers,
            json=valid_payload
        )
        assert response.status_code == 200
        assert "output" in response.json()


@pytest.mark.anyio
async def test_empty_database_response(test_client):
    with patch('main.telkomllm_generate_sql') as mock_gen, \
         patch('main.sqlite3.connect') as mock_db, \
         patch('main.telkomllm_infer_sql') as mock_infer:
        # Setup mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.side_effect = [
            [(0, 'id', 'INTEGER', 0, None, 1)],  # PRAGMA table_info response
            []  # Empty query result
        ]
        mock_db.return_value = mock_conn
        mock_gen.return_value = "SELECT * FROM employee_demography"
        mock_infer.return_value = "No data insight"
        response = await test_client.post(
            url=endpoint,
            headers=valid_headers,
            json=valid_payload
        )
        assert response.status_code == 200
        assert response.json()['output'] == "No data insight"