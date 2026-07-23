"""Core domain model for the BankFlow loan processing system.

This module contains only plain data structures and enumerations. It has
zero dependencies on persistence, HTTP, or workflow orchestration code, so
it can be reused/tested in complete isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utc_now_iso() -> str:
    """Return the current UTC time formatted per ISO-8601 (e.g. 2026-07-15T10:00:00Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LoanType(str, Enum):
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"


class LoanStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    IN_PROGRESS = "IN_PROGRESS"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# Statuses that mean "processing is finished, do not run the workflow again".
TERMINAL_STATUSES = {LoanStatus.APPROVED, LoanStatus.REJECTED, LoanStatus.MANUAL_REVIEW}


class Stage(str, Enum):
    VALIDATION = "VALIDATION"
    CHECK_FRAUD = "CHECK_FRAUD"
    CHECK_GUARANTOR = "CHECK_GUARANTOR"
    CHECK_CREDIT = "CHECK_CREDIT"
    APPROVAL_MANAGER = "APPROVAL_MANAGER"


class StageResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    LOAN_NOT_FOUND = "LOAN_NOT_FOUND"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    INVALID_PHONE = "INVALID_PHONE"
    INVALID_CUSTOMER_ID = "INVALID_CUSTOMER_ID"
    INVALID_LOAN_TYPE = "INVALID_LOAN_TYPE"
    INVALID_CREDIT_SCORE = "INVALID_CREDIT_SCORE"
    INVALID_MONTHLY_INCOME = "INVALID_MONTHLY_INCOME"


@dataclass
class Loan:
    loan_id: str
    customer_id: str
    amount: int
    phone: str
    loan_type: str
    monthly_income: int
    credit_score: int
    has_guarantor: bool
    status: LoanStatus = LoanStatus.SUBMITTED
    current_stage: Optional[str] = Stage.VALIDATION.value
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class HistoryEntry:
    loan_id: str
    stage: str
    result: str
    reason: str
    timestamp: str = field(default_factory=utc_now_iso)


class LoanNotFoundError(Exception):
    """Raised when a loan id does not exist in the repository."""

    def __init__(self, loan_id: str):
        super().__init__(f"Loan not found: {loan_id}")
        self.loan_id = loan_id
