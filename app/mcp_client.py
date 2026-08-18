from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.models import InvoiceFields

ROOT = Path(__file__).resolve().parents[1]


def _tool_result_to_dict(result: Any) -> dict[str, object]:
    for name in ("structuredContent", "structured_content"):
        value = getattr(result, name, None)
        if isinstance(value, dict):
            return value
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError("MCP tool returned no structured result")


def server_parameters() -> StdioServerParameters:
    env = {
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
    }
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=env,
    )


async def validate_with_mcp(invoice: InvoiceFields) -> dict[str, dict[str, object]]:
    async with Client(stdio_client(server_parameters())) as client:
        nip_result = await client.call_tool("nip_check", {"nip": invoice.nip})
        vat_result = await client.call_tool(
            "vat_math_check",
            {
                "amount_net": float(Decimal(invoice.amount_net)),
                "vat_rate": float(Decimal(invoice.vat_rate)),
                "amount_gross": float(Decimal(invoice.amount_gross)),
            },
        )
    return {
        "nip": _tool_result_to_dict(nip_result),
        "vat": _tool_result_to_dict(vat_result),
    }
