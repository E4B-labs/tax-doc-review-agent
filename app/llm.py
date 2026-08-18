from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol, cast

from app.models import InvoiceFields


class Extractor(Protocol):
    async def ainvoke(self, document: str) -> Any: ...


def _field(text: str, name: str, default: str = "") -> str:
    match = re.search(rf"(?:^|[,\n;])\s*{re.escape(name)}\s*[:=]\s*([^,\n;]+)", text, re.I)
    return match.group(1).strip() if match else default


class FakeLLM:
    """Deterministic structured extractor used by tests and no-key local demos."""

    async def ainvoke(self, document: str) -> InvoiceFields:
        try:
            data: Any = json.loads(document)
        except json.JSONDecodeError:
            data = {
                "vendor": _field(document, "vendor"),
                "nip": _field(document, "nip"),
                "amount_net": _field(document, "amount_net", "0"),
                "vat_rate": _field(document, "vat_rate", "23"),
                "amount_gross": _field(document, "amount_gross", "0"),
                "date": _field(document, "date"),
                "category": _field(document, "category", "other"),
                "confidence": _field(document, "confidence", "0.95"),
            }
        if not isinstance(data, dict):
            raise ValueError("Document must be a JSON object or labeled text")
        return InvoiceFields.model_validate(data)


def build_extractor() -> Extractor:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return FakeLLM()
    from langchain_anthropic import ChatAnthropic

    model = ChatAnthropic(
        model_name=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        temperature=0,
        timeout=None,
        stop=None,
    )
    return cast(Extractor, model.with_structured_output(InvoiceFields))
