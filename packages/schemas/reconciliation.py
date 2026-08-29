from enum import Enum

class ReconciliationRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class RelationshipStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNRESOLVED = "UNRESOLVED"

class FinancialEvaluationStatus(str, Enum):
    RECONCILED = "RECONCILED"
    DISCREPANCY = "DISCREPANCY"
    UNRESOLVED = "UNRESOLVED"

class DiscrepancyType(str, Enum):
    FEE_MISMATCH = "FEE_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_BANK_TX = "MISSING_BANK_TX"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    LATE_ARRIVAL = "LATE_ARRIVAL"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    ORPHAN_RECORD = "ORPHAN_RECORD"

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
