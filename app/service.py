from __future__ import annotations

import asyncio
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from app.graph import build_graph
from app.llm import Extractor


def _config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


class DocumentService:
    def __init__(
        self, checkpointer: BaseCheckpointSaver, extractor: Extractor | None = None
    ) -> None:
        self.graph = build_graph(checkpointer, extractor)

    async def start(self, thread_id: str, content: str | dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.graph.invoke,
            {"document_id": thread_id, "document": content},
            config=_config(thread_id),
        )

    async def review(self, thread_id: str, approved: bool, edits: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.graph.invoke,
            Command(resume={"approved": approved, "edits": edits}),
            config=_config(thread_id),
        )

    async def snapshot(self, thread_id: str) -> dict[str, Any]:
        snapshot = await asyncio.to_thread(self.graph.get_state, _config(thread_id))
        state = dict(snapshot.values)
        interrupts = [interrupt.value for task in snapshot.tasks for interrupt in task.interrupts]
        if not state and not interrupts:
            raise KeyError(thread_id)
        if interrupts:
            state["status"] = "needs_review"
        result = {
            "thread_id": thread_id,
            "status": state.get("status"),
            "state": state,
            "interrupt": interrupts[0] if interrupts else None,
        }
        return result
