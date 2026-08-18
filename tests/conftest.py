from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import redis
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.redis import RedisSaver

from app.llm import FakeLLM
from app.service import DocumentService

VALID_DOCUMENT = {
    "vendor": "Acme Supplies Sp. z o.o.",
    "nip": "5260250995",
    "amount_net": "100.00",
    "vat_rate": "23",
    "amount_gross": "123.00",
    "date": "2025-06-15",
    "category": "office",
    "confidence": 0.98,
}


@pytest.fixture
def document() -> dict[str, object]:
    return dict(VALID_DOCUMENT)


@pytest.fixture
def memory_checkpointer() -> BaseCheckpointSaver:
    return InMemorySaver()


@pytest.fixture
def service(memory_checkpointer: BaseCheckpointSaver) -> DocumentService:
    return DocumentService(memory_checkpointer, FakeLLM())


def redis_saver_or_skip() -> RedisSaver:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(url)
    try:
        client.ping()
        saver = RedisSaver(redis_url=url)
        saver.setup()
        return saver
    except Exception as exc:
        client.close()
        pytest.skip(f"Redis unavailable: {exc}")


@pytest.fixture
def redis_checkpointer() -> Iterator[RedisSaver]:
    saver = redis_saver_or_skip()
    yield saver
    saver._redis.close()  # type: ignore[attr-defined]
