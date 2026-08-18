from __future__ import annotations

from decimal import Decimal

from mcp.server import MCPServer

from app.rules import nip_check as check_nip
from app.rules import vat_math_check as check_vat_math

mcp = MCPServer(
    name="tax-validation",
    version="1.0.0",
    instructions="Deterministic Polish tax document validation tools.",
)


@mcp.tool(structured_output=True)
def nip_check(nip: str) -> dict[str, object]:
    """Validate Polish NIP digits and checksum."""

    return check_nip(nip)


@mcp.tool(structured_output=True)
def vat_math_check(amount_net: float, vat_rate: float, amount_gross: float) -> dict[str, object]:
    """Validate net amount, Polish VAT rate, and gross amount arithmetic."""

    return check_vat_math(
        Decimal(str(amount_net)), Decimal(str(vat_rate)), Decimal(str(amount_gross))
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
