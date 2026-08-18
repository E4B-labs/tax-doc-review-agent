from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
VALID_VAT_RATES = {Decimal("0"), Decimal("5"), Decimal("8"), Decimal("23")}


def normalize_nip(nip: str) -> str:
    return "".join(char for char in nip if char.isdigit())


def nip_check(nip: str) -> dict[str, object]:
    digits = normalize_nip(nip)
    if len(digits) != 10:
        return {"valid": False, "reason": "NIP must contain exactly 10 digits"}
    checksum = (
        sum(int(digit) * weight for digit, weight in zip(digits[:9], NIP_WEIGHTS, strict=True)) % 11
    )
    valid = checksum != 10 and checksum == int(digits[-1])
    return {"valid": valid, "reason": None if valid else "NIP checksum failed"}


def vat_math_check(
    amount_net: Decimal, vat_rate: Decimal, amount_gross: Decimal
) -> dict[str, object]:
    if vat_rate not in VALID_VAT_RATES:
        return {"valid": False, "reason": "Unsupported Polish VAT rate"}
    expected = (amount_net * (Decimal(1) + vat_rate / Decimal(100))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    actual = amount_gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    valid = expected == actual
    return {
        "valid": valid,
        "reason": None if valid else f"Gross should be {expected}, received {actual}",
    }


def date_check(value: date, today: date | None = None) -> dict[str, object]:
    today = today or date.today()
    valid = date(2000, 1, 1) <= value <= today
    return {
        "valid": valid,
        "reason": None if valid else "Date must be between 2000-01-01 and today",
    }
