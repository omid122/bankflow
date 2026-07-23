"""Stage handlers.

Each stage is an independent class with a single responsibility: given a
loan and the current rules, decide PASS / FAIL / MANUAL_REVIEW and a reason.
No stage knows about any other stage, about persistence, or about HTTP.

Adding a new stage (e.g. CHECK_AML) means adding one new class here that
implements StageHandler -- nothing else in this file changes.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import NamedTuple

from src.domain.models import Loan, LoanType, StageResult
from src.domain.rules import RulesConfig

PHONE_PATTERN = re.compile(r"^09\d{9}$")


class StageOutcome(NamedTuple):
    result: StageResult
    reason: str


class StageHandler(ABC):
    """Contract every workflow stage must implement."""

    @abstractmethod
    def execute(self, loan: Loan, rules: RulesConfig) -> StageOutcome:
        ...


class ValidationStage(StageHandler):
    """Checks the structural validity of the submitted data.

    This stage is only responsible for verifying the input is well formed.
    It is not responsible for fraud, credit, or approval decisions.
    """

    def execute(self, loan: Loan, rules: RulesConfig) -> StageOutcome:
        if not loan.customer_id or not loan.customer_id.strip():
            return StageOutcome(StageResult.FAIL, "INVALID_CUSTOMER_ID")

        if loan.amount is None or loan.amount <= 0:
            return StageOutcome(StageResult.FAIL, "INVALID_AMOUNT")

        if not loan.phone or not PHONE_PATTERN.match(loan.phone):
            return StageOutcome(StageResult.FAIL, "INVALID_PHONE")

        if loan.loan_type not in (LoanType.PERSONAL.value, LoanType.BUSINESS.value):
            return StageOutcome(StageResult.FAIL, "INVALID_LOAN_TYPE")

        if loan.monthly_income is None or loan.monthly_income < 0:
            return StageOutcome(StageResult.FAIL, "INVALID_MONTHLY_INCOME")

        if loan.credit_score is None or not (0 <= loan.credit_score <= 1000):
            return StageOutcome(StageResult.FAIL, "INVALID_CREDIT_SCORE")

        return StageOutcome(StageResult.PASS, "SUCCESS")


class FraudCheckStage(StageHandler):
    """Mock fraud detection so the system does not depend on an external
    fraud-detection service. Decision is driven purely by a customerId
    naming convention, as required by the challenge spec.
    """

    def execute(self, loan: Loan, rules: RulesConfig) -> StageOutcome:
        customer_id = loan.customer_id or ""
        if customer_id.startswith("FRAUD"):
            return StageOutcome(StageResult.FAIL, "SUSPECTED_FRAUD")
        if customer_id.startswith("REVIEW"):
            return StageOutcome(StageResult.MANUAL_REVIEW, "FRAUD_REVIEW_REQUIRED")
        return StageOutcome(StageResult.PASS, "SUCCESS")


class GuarantorCheckStage(StageHandler):
    """Only relevant for BUSINESS loans (the workflow definition decides
    whether to run this stage at all -- this class only decides PASS/FAIL
    once it *is* invoked)."""

    def execute(self, loan: Loan, rules: RulesConfig) -> StageOutcome:
        if not loan.has_guarantor:
            return StageOutcome(StageResult.FAIL, "GUARANTOR_REQUIRED")
        return StageOutcome(StageResult.PASS, "SUCCESS")


class CreditCheckStage(StageHandler):
    """Decides based purely on creditScore, using thresholds read from the
    rules configuration file (never hard-coded)."""

    def execute(self, loan: Loan, rules: RulesConfig) -> StageOutcome:
        score = loan.credit_score
        if score < rules.manual_review_min_score:
            return StageOutcome(StageResult.FAIL, "LOW_CREDIT_SCORE")
        if score <= rules.manual_review_max_score:
            return StageOutcome(StageResult.MANUAL_REVIEW, "CREDIT_SCORE_BORDERLINE")
        if score >= rules.minimum_credit_score:
            return StageOutcome(StageResult.PASS, "SUCCESS")
        # Defensive fallback: score sits between manual_review_max_score and
        # minimum_credit_score if the two are configured with a gap.
        return StageOutcome(StageResult.MANUAL_REVIEW, "CREDIT_SCORE_BORDERLINE")


class ManagerApprovalStage(StageHandler):
    """Mock manager-approval rule; only invoked when the workflow definition
    decides the loan amount requires manager sign-off."""

    def execute(self, loan: Loan, rules: RulesConfig) -> StageOutcome:
        if loan.amount > loan.monthly_income * rules.income_multiplier:
            return StageOutcome(StageResult.FAIL, "INCOME_INSUFFICIENT")
        return StageOutcome(StageResult.PASS, "SUCCESS")
