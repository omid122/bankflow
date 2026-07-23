from src.domain.models import Loan, LoanType, StageResult
from src.domain.rules import RulesConfig
from src.workflow.stages import ValidationStage

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


def test_valid_loan_passes():
    outcome = ValidationStage().execute(make_loan(), RULES)
    assert outcome.result == StageResult.PASS
    assert outcome.reason == "SUCCESS"


def test_empty_customer_id_fails():
    outcome = ValidationStage().execute(make_loan(customer_id="  "), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_CUSTOMER_ID"


def test_zero_amount_fails():
    outcome = ValidationStage().execute(make_loan(amount=0), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_AMOUNT"


def test_negative_amount_fails():
    outcome = ValidationStage().execute(make_loan(amount=-5), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_AMOUNT"


def test_phone_not_starting_with_09_fails():
    outcome = ValidationStage().execute(make_loan(phone="08121234567"), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_PHONE"


def test_phone_wrong_length_fails():
    outcome = ValidationStage().execute(make_loan(phone="0912123456"), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_PHONE"


def test_phone_non_digits_fails():
    outcome = ValidationStage().execute(make_loan(phone="0912abc4567"), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_PHONE"


def test_invalid_loan_type_fails():
    outcome = ValidationStage().execute(make_loan(loan_type="MORTGAGE"), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_LOAN_TYPE"


def test_negative_monthly_income_fails():
    outcome = ValidationStage().execute(make_loan(monthly_income=-1), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_MONTHLY_INCOME"


def test_credit_score_out_of_range_fails():
    outcome = ValidationStage().execute(make_loan(credit_score=1001), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_CREDIT_SCORE"

    outcome = ValidationStage().execute(make_loan(credit_score=-1), RULES)
    assert outcome.result == StageResult.FAIL
    assert outcome.reason == "INVALID_CREDIT_SCORE"


def test_boundary_credit_scores_pass_validation():
    assert ValidationStage().execute(make_loan(credit_score=0), RULES).result == StageResult.PASS
    assert ValidationStage().execute(make_loan(credit_score=1000), RULES).result == StageResult.PASS
