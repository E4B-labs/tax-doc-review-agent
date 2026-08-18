from datetime import date
from decimal import Decimal

from app.rules import date_check, nip_check, vat_math_check


def test_valid_nip() -> None:
    assert nip_check("526-025-09-95")["valid"] is True


def test_invalid_nip_checksum() -> None:
    assert nip_check("5260250994")["valid"] is False


def test_invalid_nip_length() -> None:
    assert nip_check("123")["valid"] is False


def test_vat_math_accepts_rounding() -> None:
    assert vat_math_check(Decimal("100"), Decimal("23"), Decimal("123.00"))["valid"] is True


def test_vat_math_rejects_wrong_gross() -> None:
    assert vat_math_check(Decimal("100"), Decimal("23"), Decimal("124"))["valid"] is False


def test_vat_math_rejects_unknown_rate() -> None:
    assert vat_math_check(Decimal("100"), Decimal("21"), Decimal("121"))["valid"] is False


def test_date_rejects_future() -> None:
    assert date_check(date(2099, 1, 1))["valid"] is False


def test_date_rejects_old_document() -> None:
    assert date_check(date(1999, 12, 31))["valid"] is False
