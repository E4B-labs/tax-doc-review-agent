from __future__ import annotations

from mcp import Client
from mcp.client.stdio import stdio_client

from app.mcp_client import server_parameters


async def test_mcp_lists_validation_tools() -> None:
    async with Client(stdio_client(server_parameters())) as client:
        tools = (await client.list_tools()).tools
    names = {tool.name for tool in tools}
    assert {"nip_check", "vat_math_check"} <= names


async def test_mcp_calls_nip_tool() -> None:
    async with Client(stdio_client(server_parameters())) as client:
        result = await client.call_tool("nip_check", {"nip": "5260250995"})
    assert result.structured_content["valid"] is True
