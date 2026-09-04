from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    FULFILLED = "FULFILLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class RefundStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FeeType(str, Enum):
    PROCESSING = "PROCESSING"
    PLATFORM = "PLATFORM"
    TAX = "TAX"
    ADJUSTMENT = "ADJUSTMENT"


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SETTLED = "SETTLED"
    DISCREPANT = "DISCREPANT"
    FAILED = "FAILED"


class BankTransactionType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class BankTransactionStatus(str, Enum):
    POSTED = "POSTED"
    PENDING = "PENDING"


class EventType(str, Enum):
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_CREATED = "PAYMENT_CREATED"
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    REFUND_CREATED = "REFUND_CREATED"
    SETTLEMENT_CREATED = "SETTLEMENT_CREATED"
    SETTLEMENT_PAID = "SETTLEMENT_PAID"
    BANK_TRANSACTION_IMPORTED = "BANK_TRANSACTION_IMPORTED"


class IngestionStatus(str, Enum):
    PROCESSED = "PROCESSED"
    EXCEPTION = "EXCEPTION"


class IngestionRunStatus(str, Enum):
    """Lifecycle of one auditable ingestion run (durable batch import)."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class IngestionRunRecordStatus(str, Enum):
    """Row-level outcome of one source record inside an ingestion run.

    - ACCEPTED: validated and materialized into the financial domain
    - DUPLICATE: logically identical source row already processed (skipped)
    - REJECTED: invalid source row (validation error, never persisted)
    - FAILED: valid row whose processing failed and can be retried
    """

    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class IngestionSourceType(str, Enum):
    """Identifies where a batch of source records originated.

    MOCK / API / CSV are local or deterministic synthetic sources. This
    platform does NOT ship credentials or connectors for real external
    providers; adapters for production providers are future work.
    """

    MOCK = "MOCK"
    API = "API"
    CSV = "CSV"
