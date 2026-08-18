from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InvoiceFields(BaseModel):
    """Structured extraction contract shared by LLM, rules, and ledger."""

    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(min_length=1)
    nip: str = Field(min_length=10)
    amount_net: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0, le=100)
    amount_gross: Decimal = Field(ge=0)
    date: date
    category: str = Field(min_length=1)
    confidence: float = Field(default=0.95, ge=0, le=1)


class ValidationResult(BaseModel):
    nip_valid: bool
    vat_math_valid: bool
    date_valid: bool
    valid: bool
    reasons: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    approved: bool
    edits: dict[str, Any] = Field(default_factory=dict)


class DocumentRequest(BaseModel):
    content: str | dict[str, Any]
