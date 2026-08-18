from __future__ import annotations

import logging
import os
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.redis import RedisSaver

from app.llm import Extractor
from app.models import DocumentRequest, ReviewRequest
from app.observability import configure_logging
from app.service import DocumentService

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def create_checkpointer() -> BaseCheckpointSaver:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        saver = RedisSaver(redis_url=redis_url)
        saver.setup()
        logger.info("using RedisSaver", extra={"redis_url": redis_url})
        return saver
    except Exception as exc:  # local uvicorn remains usable without Docker Redis
        logger.warning("Redis unavailable; using in-memory checkpoints: %s", exc)
        return InMemorySaver()


def _auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = request.app.state.api_token
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_app(
    checkpointer: BaseCheckpointSaver | None = None,
    extractor: Extractor | None = None,
    api_token: str | None = None,
) -> FastAPI:
    configure_logging()
    api = FastAPI(title="Tax Document Review Agent", version="0.1.0")
    api.state.api_token = api_token or os.getenv("API_BEARER_TOKEN", "dev-token")
    api.state.service = DocumentService(checkpointer or create_checkpointer(), extractor)

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/documents", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_auth)])
    async def create_document(request: DocumentRequest) -> dict[str, Any]:
        thread_id = str(uuid4())
        try:
            await api.state.service.start(thread_id, request.content)
            return await api.state.service.snapshot(thread_id)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get("/documents/{thread_id}", dependencies=[Depends(_auth)])
    async def get_document(thread_id: str) -> dict[str, Any]:
        try:
            return await api.state.service.snapshot(thread_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Document not found") from exc

    @api.post("/documents/{thread_id}/review", dependencies=[Depends(_auth)])
    async def review_document(thread_id: str, review: ReviewRequest) -> dict[str, Any]:
        try:
            current = await api.state.service.snapshot(thread_id)
            if current["interrupt"] is None:
                raise HTTPException(status_code=409, detail="Document is not waiting for review")
            await api.state.service.review(thread_id, review.approved, review.edits)
            return await api.state.service.snapshot(thread_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Document not found") from exc
        except HTTPException:
            raise
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return api


app = create_app()
