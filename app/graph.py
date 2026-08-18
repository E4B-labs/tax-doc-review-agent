from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.llm import Extractor, build_extractor
from app.mcp_client import validate_with_mcp
from app.models import InvoiceFields, ValidationResult
from app.observability import trace_event
from app.rules import date_check

logger = logging.getLogger(__name__)


class TaxState(TypedDict, total=False):
    document_id: str
    document: str | dict[str, Any]
    normalized_document: str
    invoice: dict[str, Any]
    validation: dict[str, Any]
    needs_review: bool
    review_reasons: list[str]
    status: str
    approved: bool
    edits: dict[str, Any]
    ledger_entry: dict[str, Any]


def _json_document(document: str | dict[str, Any]) -> str:
    return document if isinstance(document, str) else json.dumps(document, ensure_ascii=False)


def _ingest(state: TaxState) -> dict[str, Any]:
    return {
        "document_id": state.get("document_id", str(uuid4())),
        "normalized_document": _json_document(state["document"]),
        "status": "ingested",
    }


def _extract(extractor: Extractor) -> Callable[[TaxState], Awaitable[dict[str, Any]]]:
    async def node(state: TaxState) -> dict[str, Any]:
        invoice = await extractor.ainvoke(state["normalized_document"])
        if not isinstance(invoice, InvoiceFields):
            invoice = InvoiceFields.model_validate(invoice)
        return {"invoice": invoice.model_dump(mode="json"), "status": "extracted"}

    return node


async def _validate(state: TaxState) -> dict[str, Any]:
    invoice = InvoiceFields.model_validate(state["invoice"])
    mcp_results = await validate_with_mcp(invoice)
    date_result = date_check(invoice.date)
    reasons: list[str] = []
    for result in (*mcp_results.values(), date_result):
        reason = result.get("reason")
        if not result["valid"] and isinstance(reason, str):
            reasons.append(reason)
    settings = {
        "amount_threshold": float(os.getenv("REVIEW_AMOUNT_THRESHOLD", "1000")),
        "confidence_threshold": float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.80")),
    }
    if invoice.confidence < settings["confidence_threshold"]:
        reasons.append("Extraction confidence is below review threshold")
    if float(invoice.amount_gross) > settings["amount_threshold"]:
        reasons.append("Gross amount exceeds review threshold")
    validation = ValidationResult(
        nip_valid=bool(mcp_results["nip"]["valid"]),
        vat_math_valid=bool(mcp_results["vat"]["valid"]),
        date_valid=bool(date_result["valid"]),
        valid=not reasons,
        reasons=reasons,
    )
    trace_event(
        "tax-document-validation", {"document_id": state["document_id"], "valid": validation.valid}
    )
    return {
        "validation": validation.model_dump(),
        "needs_review": bool(reasons),
        "review_reasons": reasons,
        "status": "needs_review" if reasons else "validated",
    }


def _route(state: TaxState) -> str:
    return "human_review" if state.get("needs_review") else "finalize"


def _human_review(state: TaxState) -> dict[str, Any]:
    payload = {
        "type": "tax_document_review",
        "message": "Approve invoice before posting to ledger.",
        "reasons": state.get("review_reasons", []),
        "invoice": state["invoice"],
        "validation": state["validation"],
    }
    decision = interrupt(payload)
    if not isinstance(decision, dict) or "approved" not in decision:
        raise ValueError("Review decision must contain boolean approved")
    edits = decision.get("edits") or {}
    if not isinstance(edits, dict):
        raise ValueError("Review edits must be an object")
    invoice = InvoiceFields.model_validate({**state["invoice"], **edits})
    return {
        "invoice": invoice.model_dump(mode="json"),
        "approved": bool(decision["approved"]),
        "edits": edits,
        "status": "reviewed",
    }


def _finalize(state: TaxState) -> dict[str, Any]:
    if not state.get("approved", True):
        return {"status": "rejected", "ledger_entry": {}}
    invoice = InvoiceFields.model_validate(state["invoice"])
    ledger_entry = {
        "entry_id": f"ledger-{state['document_id']}",
        "status": "posted",
        "document_id": state["document_id"],
        "invoice": invoice.model_dump(mode="json"),
    }
    return {"status": "posted", "ledger_entry": ledger_entry}


def build_graph(checkpointer: BaseCheckpointSaver, extractor: Extractor | None = None) -> Any:
    extractor = extractor or build_extractor()
    workflow = StateGraph(TaxState)
    workflow.add_node("ingest", _ingest)
    workflow.add_node("extract", _extract(extractor))  # type: ignore[arg-type]
    workflow.add_node("validate", _validate)
    workflow.add_node("route", lambda state: {})
    workflow.add_node("human_review", _human_review)
    workflow.add_node("finalize", _finalize)
    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "extract")
    workflow.add_edge("extract", "validate")
    workflow.add_edge("validate", "route")
    workflow.add_conditional_edges(
        "route", _route, {"human_review": "human_review", "finalize": "finalize"}
    )
    workflow.add_edge("human_review", "finalize")
    workflow.add_edge("finalize", END)
    return workflow.compile(checkpointer=checkpointer)
