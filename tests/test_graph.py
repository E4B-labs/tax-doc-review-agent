from __future__ import annotations

from langgraph.types import Command

from app.graph import build_graph
from app.llm import FakeLLM


async def test_happy_path_auto_posts(service, document) -> None:
    result = await service.start("happy", document)
    assert result["status"] == "posted"
    assert result["ledger_entry"]["status"] == "posted"


async def test_low_confidence_pauses_for_review(service, document) -> None:
    document["confidence"] = 0.2
    await service.start("confidence", document)
    snapshot = await service.snapshot("confidence")
    assert snapshot["status"] == "needs_review"
    assert "Extraction confidence is below review threshold" in snapshot["interrupt"]["reasons"]


async def test_amount_threshold_pauses_for_review(service, document) -> None:
    document.update(amount_net="2000", amount_gross="2460")
    await service.start("amount", document)
    snapshot = await service.snapshot("amount")
    assert snapshot["status"] == "needs_review"
    assert "Gross amount exceeds review threshold" in snapshot["interrupt"]["reasons"]


async def test_failed_rule_pauses_for_review(service, document) -> None:
    document["nip"] = "5260250994"
    await service.start("bad-rule", document)
    snapshot = await service.snapshot("bad-rule")
    assert snapshot["state"]["validation"]["valid"] is False
    assert snapshot["interrupt"] is not None


async def test_review_edits_are_applied_and_posted(service, document) -> None:
    document["confidence"] = 0.2
    await service.start("review", document)
    result = await service.review("review", True, {"category": "professional_services"})
    assert result["status"] == "posted"
    assert result["ledger_entry"]["invoice"]["category"] == "professional_services"


async def test_rejected_review_does_not_post(service, document) -> None:
    document["confidence"] = 0.2
    await service.start("reject", document)
    result = await service.review("reject", False, {})
    assert result["status"] == "rejected"
    assert result["ledger_entry"] == {}


async def test_graph_object_restart_resumes_same_thread(redis_checkpointer, document) -> None:
    first = build_graph(redis_checkpointer, FakeLLM())
    config = {"configurable": {"thread_id": "restart"}}
    document["confidence"] = 0.2
    await first.ainvoke({"document_id": "restart", "document": document}, config)
    redis_checkpointer._redis.close()  # type: ignore[attr-defined]

    import os

    from langgraph.checkpoint.redis import RedisSaver

    second_saver = RedisSaver(redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    second_saver.setup()
    second = build_graph(second_saver, FakeLLM())
    result = await second.ainvoke(Command(resume={"approved": True, "edits": {}}), config)
    assert result["status"] == "posted"
    second_saver._redis.close()  # type: ignore[attr-defined]
