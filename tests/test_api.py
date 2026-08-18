from __future__ import annotations

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.llm import FakeLLM
from app.main import create_app


@pytest.fixture
def api_app():
    return create_app(InMemorySaver(), FakeLLM(), api_token="test-token")


async def test_api_auto_post(api_app, document) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/documents", json={"content": document}, headers={"Authorization": "Bearer test-token"}
        )
    assert response.status_code == 202
    assert response.json()["status"] == "posted"


async def test_api_review_and_resume(api_app, document) -> None:
    document["confidence"] = 0.2
    headers = {"Authorization": "Bearer test-token"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        created = await client.post("/documents", json={"content": document}, headers=headers)
        body = created.json()
        assert body["status"] == "needs_review"
        reviewed = await client.post(
            f"/documents/{body['thread_id']}/review",
            json={"approved": True, "edits": {"category": "travel"}},
            headers=headers,
        )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "posted"
    assert reviewed.json()["state"]["invoice"]["category"] == "travel"


async def test_api_get_returns_pending_interrupt(api_app, document) -> None:
    document["confidence"] = 0.2
    headers = {"Authorization": "Bearer test-token"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        created = await client.post("/documents", json={"content": document}, headers=headers)
        fetched = await client.get(f"/documents/{created.json()['thread_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["interrupt"]["type"] == "tax_document_review"


async def test_api_rejects_missing_auth(api_app, document) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        response = await client.post("/documents", json={"content": document})
    assert response.status_code == 401


async def test_api_returns_404_for_unknown_thread(api_app) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/documents/missing", headers={"Authorization": "Bearer test-token"}
        )
    assert response.status_code == 404
