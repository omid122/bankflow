from src.domain.models import Loan, LoanType, StageResult
from src.domain.rules import RulesConfig
from src.workflow.stages import (
    CreditCheckStage,
    FraudCheckStage,
    GuarantorCheckStage,
    ManagerApprovalStage,
)

RULES = RulesConfig(
    minimum_credit_score=650,
    manager_approval_threshold=500_000_000,
    income_multiplier=20,
    manual_review_min_score=500,
    manual_review_max_score=649,
)


def make_loan(**overrides) -> Loan:
    base = dict(
        loan_id="L-1",
        customer_id="C-1001",
        amount=1_000_000,
        phone="09121234567",
        loan_type=LoanType.PERSONAL.value,
        monthly_income=50_000_000,
        credit_score=700,
        has_guarantor=False,
    )
    base.update(overrides)
    return Loan(**base)


# --- FraudCheckStage ---

def test_fraud_customer_id_fails():
    outcome = FraudCheckStage().execute(make_loan(customer_id="FRAUD-1"), RULES)
    assert outcome.result == StageResult.FAIL


def test_review_customer_id_triggers_manual_review():
    outcome = FraudCheckStage().execute(make_loan(customer_id="REVIEW-1"), RULES)
    assert outcome.result == StageResult.MANUAL_REVIEW


def test_normal_customer_id_passes_fraud_check():
    outcome = FraudCheckStage().execute(make_loan(customer_id="C-1001"), RULES)
    assert outcome.result == StageResult.PASS


# --- GuarantorCheckStage ---

def test_missing_guarantor_fails():
    outcome = GuarantorCheckStage().execute(make_loan(has_guarantor=False), RULES)
    assert outcome.result == StageResult.FAIL


def test_present_guarantor_passes():
    outcome = GuarantorCheckStage().execute(make_loan(has_guarantor=True), RULES)
    assert outcome.result == StageResult.PASS


# --- CreditCheckStage ---

def test_low_credit_score_fails():
    outcome = CreditCheckStage().execute(make_loan(credit_score=499), RULES)
    assert outcome.result == StageResult.FAIL


def test_borderline_credit_score_triggers_manual_review():
    outcome = CreditCheckStage().execute(make_loan(credit_score=500), RULES)
    assert outcome.result == StageResult.MANUAL_REVIEW

    outcome = CreditCheckStage().execute(make_loan(credit_score=649), RULES)
    assert outcome.result == StageResult.MANUAL_REVIEW


def test_high_credit_score_passes():
    outcome = CreditCheckStage().execute(make_loan(credit_score=650), RULES)
    assert outcome.result == StageResult.PASS


# --- ManagerApprovalStage ---

def test_manager_approval_fails_when_amount_exceeds_income_multiple():
    loan = make_loan(amount=1_000_000_000, monthly_income=10_000_000)
    outcome = ManagerApprovalStage().execute(loan, RULES)
    assert outcome.result == StageResult.FAIL


def test_manager_approval_passes_when_within_income_multiple():
    loan = make_loan(amount=600_000_000, monthly_income=50_000_000)  # 20x = 1,000,000,000
    outcome = ManagerApprovalStage().execute(loan, RULES)
    assert outcome.result == StageResult.PASS
