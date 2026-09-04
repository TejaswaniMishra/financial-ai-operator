"""M13 — Deterministic source-row validation & normalization.

Every raw source row is validated and normalized BEFORE anything touches the
financial domain. Validation failures are row-level and safe: the raw payload
is never persisted, never materialized, and never pollutes domain tables.

Design rules
------------
- No floats for money: monetary fields must be int or decimal strings.
- Monetary precision is capped at 4 decimal places (Numeric(18,4) storage).
- Currency must be a supported ISO-4217 code (Currency enum vocabulary).
- Naive datetimes are interpreted as UTC (documented timezone semantics).
- Unknown extra keys are ignored for normalization but preserved in the raw
  payload for provenance; logical identity is provider+external_id+entity.
- Status values must match the authoritative domain enum strings exactly.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from packages.schemas.enums import (
    BankTransactionStatus,
    BankTransactionType,
    FeeType,
    PaymentStatus,
    RefundStatus,
    SettlementStatus,
)
from packages.schemas.money import Currency
from packages.utils.id_generator import generate_id
from services.ingestion.base import generate_fingerprint

# ─── Vocabulary ──────────────────────────────────────────────────────────────

SUPPORTED_ENTITY_TYPES = (
    "PAYMENT",
    "REFUND",
    "FEE",
    "SETTLEMENT",
    "BANK_TRANSACTION",
)

_SUPPORTED_CURRENCIES = {c.value for c in Currency}

# ─── Row-level error codes (stable API codes) ───────────────────────────────

UNSUPPORTED_RECORD_TYPE = "UNSUPPORTED_RECORD_TYPE"
MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
INVALID_AMOUNT = "INVALID_AMOUNT"
INVALID_CURRENCY = "INVALID_CURRENCY"
MALFORMED_DATE = "MALFORMED_DATE"
INVALID_STATUS = "INVALID_STATUS"
INVALID_REFERENCE = "INVALID_REFERENCE"
INVALID_FIELD = "INVALID_FIELD"


class RowValidationError(ValueError):
    """A source row is invalid; carries a stable error code + safe message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ─── Canonical value helpers ────────────────────────────────────────────────


def parse_amount(value: Any, field: str) -> Decimal:
    """Parse a monetary value. Floats and >4dp values are rejected."""
    if isinstance(value, float):
        raise RowValidationError(
            INVALID_AMOUNT,
            f"{field} must be provided as an integer or decimal string (float is forbidden)",
        )
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RowValidationError(INVALID_AMOUNT, f"{field} must be a number or numeric string")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise RowValidationError(INVALID_AMOUNT, f"{field} is not a valid decimal number")
    if not amount.is_finite():
        raise RowValidationError(INVALID_AMOUNT, f"{field} must be a finite number")
    exponent = amount.as_tuple().exponent
    if exponent < -4:
        raise RowValidationError(
            INVALID_AMOUNT,
            f"{field} supports at most 4 decimal places",
        )
    return amount


def parse_datetime(value: Any, field: str) -> datetime:
    """Parse an ISO-8601 datetime. Naive values are interpreted as UTC.

    Plain 'YYYY-MM-DD' dates are accepted as UTC midnight for CSV ergonomics.
    """
    if not isinstance(value, str) or not value.strip():
        raise RowValidationError(MALFORMED_DATE, f"{field} must be an ISO-8601 datetime string")
    raw = value.strip()
    # Python 3.10's fromisoformat does not accept the trailing 'Z' UTC marker.
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(raw), datetime.min.time())
        except ValueError:
            raise RowValidationError(
                MALFORMED_DATE, f"{field} is not a valid ISO-8601 datetime: {raw[:64]}"
            )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_currency(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 3 or not value.isalpha():
        raise RowValidationError(INVALID_CURRENCY, f"{field} must be a 3-letter ISO-4217 code")
    code = value.upper()
    if code not in _SUPPORTED_CURRENCIES:
        raise RowValidationError(
            INVALID_CURRENCY,
            f"{field} is not a supported currency (supported: {', '.join(sorted(_SUPPORTED_CURRENCIES))})",
        )
    return code


def parse_enum(value: Any, enum_cls, field: str) -> str:
    """Value must equal one of the authoritative domain enum strings."""
    if not isinstance(value, str):
        raise RowValidationError(INVALID_STATUS, f"{field} must be one of {[e.value for e in enum_cls]}")
    raw = value.strip().upper()
    allowed = {e.value for e in enum_cls}
    if raw not in allowed:
        raise RowValidationError(
            INVALID_STATUS,
            f"{field} must be one of: {', '.join(sorted(allowed))}",
        )
    return raw


def _opt_str(row: dict, key: str) -> Optional[str]:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RowValidationError(INVALID_FIELD, f"{key} must be a non-empty string")
    return value.strip()


def _req_str(row: dict, key: str) -> str:
    value = _opt_str(row, key)
    if value is None:
        raise RowValidationError(MISSING_REQUIRED_FIELD, f"missing required field: {key}")
    return value


def reference_from_row(row: dict, entity: str, required: bool = True) -> Optional[dict]:
    """Return {'id': ...} or {'external_id': ...} for a referenced entity.

    Accepts exactly one of `<entity>_id` / `<entity>_external_id`.
    """
    id_key = f"{entity}_id"
    ext_key = f"{entity}_external_id"
    by_id = _opt_str(row, id_key)
    by_ext = _opt_str(row, ext_key)
    if by_id is not None and by_ext is not None:
        raise RowValidationError(
            INVALID_REFERENCE,
            f"provide either {id_key} or {ext_key}, not both",
        )
    if by_id is not None:
        return {"id": by_id}
    if by_ext is not None:
        return {"external_id": by_ext}
    if required:
        raise RowValidationError(
            MISSING_REQUIRED_FIELD,
            f"missing required reference: {id_key} or {ext_key}",
        )
    return None


# ─── Normalized row ─────────────────────────────────────────────────────────


@dataclass
class NormalizedRow:
    """Canonical, validated source row ready for idempotency checks."""

    entity_type: str
    provider: str
    external_id: str
    payload: dict[str, Any]
    row_fingerprint: str
    raw_payload: dict[str, Any]
    # Only populated on validation failure (never normalized further).
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def valid(self) -> bool:
        return self.error_code is None


def _canonical_fingerprint(entity_type: str, payload: dict) -> str:
    """Deterministic fingerprint over the NORMALIZED payload.

    Decimal values are serialized as canonical strings and datetimes as ISO
    strings, so equal logical rows always produce equal fingerprints even when
    the raw JSON spelling differs (e.g. '100.0' vs '100.00').
    """
    canonical: dict[str, Any] = {"entity_type": entity_type}
    for key, value in payload.items():
        if isinstance(value, Decimal):
            canonical[key] = str(value)
        elif isinstance(value, datetime):
            canonical[key] = value.isoformat()
        elif isinstance(value, dict):
            canonical[key] = _canonical_fingerprint("", value)
        elif isinstance(value, list):
            canonical[key] = [
                _canonical_fingerprint("", v) if isinstance(v, dict) else v for v in value
            ]
        else:
            canonical[key] = value
    return generate_fingerprint(canonical)


def _normalize_common(row: dict) -> tuple[str, str, str]:
    """entity_type / provider / external_id (identity triplet)."""
    entity_type = _req_str(row, "entity_type").upper()
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise RowValidationError(
            UNSUPPORTED_RECORD_TYPE,
            f"unsupported record type '{entity_type}'; supported: {', '.join(SUPPORTED_ENTITY_TYPES)}",
        )
    provider = _req_str(row, "provider")
    if len(provider) > 64:
        raise RowValidationError(INVALID_FIELD, "provider exceeds 64 characters")
    external_id = _req_str(row, "external_id")
    if len(external_id) > 255:
        raise RowValidationError(INVALID_FIELD, "external_id exceeds 255 characters")
    return entity_type, provider, external_id


def _normalize_payment(row: dict) -> dict:
    return {
        "merchant_ref": reference_from_row(row, "merchant"),
        "order_ref": reference_from_row(row, "order"),
        "amount": parse_amount(row.get("amount"), "amount"),
        "currency": parse_currency(row.get("currency"), "currency"),
        "status": parse_enum(row.get("status"), PaymentStatus, "status"),
        "payment_method_type": _opt_str(row, "payment_method_type"),
        "processed_at": (
            parse_datetime(row["processed_at"], "processed_at")
            if row.get("processed_at") is not None
            else None
        ),
    }


def _normalize_refund(row: dict) -> dict:
    return {
        "payment_ref": reference_from_row(row, "payment"),
        "amount": parse_amount(row.get("amount"), "amount"),
        "currency": parse_currency(row.get("currency"), "currency"),
        "status": parse_enum(row.get("status"), RefundStatus, "status"),
        "reason": _opt_str(row, "reason"),
        "processed_at": (
            parse_datetime(row["processed_at"], "processed_at")
            if row.get("processed_at") is not None
            else None
        ),
    }


def _normalize_fee(row: dict) -> dict:
    return {
        "merchant_ref": reference_from_row(row, "merchant"),
        "payment_ref": reference_from_row(row, "payment", required=False),
        "settlement_ref": reference_from_row(row, "settlement", required=False),
        "fee_type": parse_enum(row.get("fee_type"), FeeType, "fee_type"),
        "amount": parse_amount(row.get("amount"), "amount"),
        "currency": parse_currency(row.get("currency"), "currency"),
    }


def _normalize_settlement(row: dict) -> dict:
    payload: dict[str, Any] = {
        "merchant_ref": reference_from_row(row, "merchant"),
        "gross_amount": parse_amount(row.get("gross_amount"), "gross_amount"),
        "fee_amount": (
            parse_amount(row["fee_amount"], "fee_amount")
            if row.get("fee_amount") is not None
            else Decimal("0")
        ),
        "adjustment_amount": (
            parse_amount(row["adjustment_amount"], "adjustment_amount")
            if row.get("adjustment_amount") is not None
            else Decimal("0")
        ),
        "expected_net_amount": (
            parse_amount(row["expected_net_amount"], "expected_net_amount")
            if row.get("expected_net_amount") is not None
            else None
        ),
        "actual_settled_amount": (
            parse_amount(row["actual_settled_amount"], "actual_settled_amount")
            if row.get("actual_settled_amount") is not None
            else None
        ),
        "currency": parse_currency(row.get("currency"), "currency"),
        "settlement_date": parse_datetime(row.get("settlement_date"), "settlement_date"),
        "status": parse_enum(row.get("status"), SettlementStatus, "status"),
    }
    return payload


def _normalize_bank_transaction(row: dict) -> dict:
    return {
        "merchant_ref": reference_from_row(row, "merchant"),
        "settlement_ref": reference_from_row(row, "settlement", required=False),
        "amount": parse_amount(row.get("amount"), "amount"),
        "currency": parse_currency(row.get("currency"), "currency"),
        "transaction_type": parse_enum(
            row.get("transaction_type"), BankTransactionType, "transaction_type"
        ),
        "transaction_date": parse_datetime(row.get("transaction_date"), "transaction_date"),
        "status": parse_enum(row.get("status"), BankTransactionStatus, "status"),
        "description": _opt_str(row, "description"),
    }


_NORMALIZERS = {
    "PAYMENT": _normalize_payment,
    "REFUND": _normalize_refund,
    "FEE": _normalize_fee,
    "SETTLEMENT": _normalize_settlement,
    "BANK_TRANSACTION": _normalize_bank_transaction,
}


def normalize_row(raw: dict, row_index: int = 0) -> NormalizedRow:
    """Validate + normalize one raw source row.

    Returns a NormalizedRow; on validation failure the returned row carries
    the stable error_code / error_message and valid=False.
    """
    if not isinstance(raw, dict):
        return NormalizedRow(
            entity_type="UNKNOWN",
            provider="",
            external_id="",
            payload={},
            row_fingerprint="",
            raw_payload={},
            error_code=INVALID_FIELD,
            error_message=f"row {row_index} must be an object",
        )
    try:
        entity_type, provider, external_id = _normalize_common(raw)
        normalized = _NORMALIZERS[entity_type](raw)
    except RowValidationError as exc:
        return NormalizedRow(
            entity_type="UNKNOWN",
            provider="",
            external_id="",
            payload={},
            row_fingerprint="",
            raw_payload=raw,
            error_code=exc.code,
            error_message=exc.message,
        )
    # Canonical normalized payload includes the logical identity fields so the
    # fingerprint fully identifies the logical source row.
    payload: dict[str, Any] = {
        "provider": provider,
        "external_id": external_id,
        **normalized,
    }
    fingerprint = _canonical_fingerprint(entity_type, payload)
    return NormalizedRow(
        entity_type=entity_type,
        provider=provider,
        external_id=external_id,
        payload=payload,
        row_fingerprint=fingerprint,
        raw_payload=raw,
    )


def new_record_id(entity_type: str) -> str:
    """Deterministic-format id prefix per entity type (server-generated)."""
    prefix_map = {
        "PAYMENT": "pay",
        "REFUND": "ref",
        "FEE": "fee",
        "SETTLEMENT": "set",
        "BANK_TRANSACTION": "btx",
    }
    return generate_id(prefix_map.get(entity_type, "ing"))


def new_run_id() -> str:
    return generate_id("irn")


def new_run_record_id() -> str:
    return generate_id("irr")
