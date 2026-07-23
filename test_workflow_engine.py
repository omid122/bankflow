"""Declarative workflow definitions.

This is the ONLY place that knows the *order* of stages and the
*conditions* under which a stage runs for a given loan type. Stage
handlers (stages.py) know nothing about order or branching; the engine
(engine.py) knows nothing about business conditions. This separation is
what lets us satisfy the "extensibility" requirement of the challenge:

  * Add a new stage to a workflow      -> add one StageStep entry here.
  * Change the order of stages         -> reorder the list here.
  * Change a decision rule             -> edit the predicate here (which
                                           itself typically just reads a
                                           value from RulesConfig).

None of the above require touching stage handlers, the engine, the
repository, or the API layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from src.domain.models import Loan, LoanType, Stage
from src.domain.rules import RulesConfig
from src.workflow.stages import (
    CreditCheckStage,
    FraudCheckStage,
    GuarantorCheckStage,
    ManagerApprovalStage,
    StageHandler,
    ValidationStage,
)

Predicate = Callable[[Loan, RulesConfig], bool]


def _always(loan: Loan, rules: RulesConfig) -> bool:
    return True


def _requires_manager_approval(loan: Loan, rules: RulesConfig) -> bool:
    return loan.amount > rules.manager_approval_threshold


@dataclass(frozen=True)
class StageStep:
    stage: Stage
    handler: StageHandler
    should_run: Predicate = _always


# Single set of handler instances shared across workflow definitions -
# handlers are stateless, so reuse is safe.
_VALIDATION = StageStep(Stage.VALIDATION, ValidationStage())
_FRAUD = StageStep(Stage.CHECK_FRAUD, FraudCheckStage())
_GUARANTOR = StageStep(Stage.CHECK_GUARANTOR, GuarantorCheckStage())
_CREDIT = StageStep(Stage.CHECK_CREDIT, CreditCheckStage())
_MANAGER = StageStep(Stage.APPROVAL_MANAGER, ManagerApprovalStage(), _requires_manager_approval)


_WORKFLOWS: dict[str, List[StageStep]] = {
    LoanType.PERSONAL.value: [_VALIDATION, _FRAUD, _CREDIT, _MANAGER],
    LoanType.BUSINESS.value: [_VALIDATION, _FRAUD, _GUARANTOR, _CREDIT, _MANAGER],
}


def get_workflow(loan_type: str) -> List[StageStep]:
    try:
        return _WORKFLOWS[loan_type]
    except KeyError as exc:
        raise ValueError(f"No workflow defined for loan type: {loan_type}") from exc


# --- Future extensibility (not implemented, kept here as documentation) ---
# Adding CHECK_AML right after CHECK_FRAUD would look like:
#
#   _AML = StageStep(Stage.CHECK_AML, AmlCheckStage())
#   _WORKFLOWS[LoanType.BUSINESS.value] = [
#       _VALIDATION, _FRAUD, _AML, _GUARANTOR, _CREDIT, _MANAGER,
#   ]
#
# No change would be required in engine.py, stages.py (besides adding the
# new AmlCheckStage class), the repository, or the API layer.
