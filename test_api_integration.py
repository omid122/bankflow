"""Workflow engine.

Pure orchestration: given a loan, its workflow definition, and the current
rules, run stages in order until a terminal outcome is reached. The engine
does not know *what* a stage checks (stages.py) or *which* stages apply to
which loan type (definitions.py) -- it only knows the generic algorithm:

    for each step in the definition, starting at the loan's current stage:
        skip it if should_run() is False
        otherwise execute it and react to PASS / FAIL / MANUAL_REVIEW

After every stage that actually executes, `on_step` is invoked with the
loan already advanced to its next resume point, so the caller (the service
layer) can persist the loan + history entry in a single atomic write. This
is what makes restart-safety and duplicate-processing-prevention (FR-7,
FR-8, FR-9) hold even if the process crashes mid-workflow: on restart, the
loan resumes exactly at the next unexecuted stage instead of re-running
anything already recorded in history.
"""
from __future__ import annotations

from typing import Callable, Optional

from src.domain.models import HistoryEntry, Loan, LoanStatus, StageResult, utc_now_iso
from src.domain.rules import RulesConfig
from src.workflow.definitions import StageStep, get_workflow

OnStepCallback = Callable[[Loan, HistoryEntry], None]


def _find_start_index(steps: list[StageStep], current_stage: Optional[str]) -> int:
    if current_stage is None:
        return len(steps)
    for idx, step in enumerate(steps):
        if step.stage.value == current_stage:
            return idx
    return len(steps)


def _next_runnable_index(steps: list[StageStep], loan: Loan, rules: RulesConfig, start: int) -> int:
    idx = start
    while idx < len(steps) and not steps[idx].should_run(loan, rules):
        idx += 1
    return idx


def run_workflow(loan: Loan, rules: RulesConfig, on_step: OnStepCallback) -> Loan:
    """Advance `loan` through its workflow until a terminal status is
    reached, mutating `loan` in place and returning it.

    Assumes the caller has already verified the loan is not already in a
    terminal status (that check is a service-layer / idempotency concern,
    not a workflow-engine concern).
    """
    steps = get_workflow(loan.loan_type)
    index = _find_start_index(steps, loan.current_stage)
    index = _next_runnable_index(steps, loan, rules, index)

    loan.status = LoanStatus.IN_PROGRESS

    while index < len(steps):
        step = steps[index]
        outcome = step.handler.execute(loan, rules)
        timestamp = utc_now_iso()

        entry = HistoryEntry(
            loan_id=loan.loan_id,
            stage=step.stage.value,
            result=outcome.result.value,
            reason=outcome.reason,
            timestamp=timestamp,
        )
        loan.updated_at = timestamp

        if outcome.result == StageResult.FAIL:
            loan.status = LoanStatus.REJECTED
            loan.current_stage = None
            on_step(loan, entry)
            return loan

        if outcome.result == StageResult.MANUAL_REVIEW:
            loan.status = LoanStatus.MANUAL_REVIEW
            loan.current_stage = None
            on_step(loan, entry)
            return loan

        # PASS -> advance to the next applicable stage (skipping any whose
        # should_run() predicate is False) and persist that resume point
        # together with this stage's history entry, atomically.
        next_index = _next_runnable_index(steps, loan, rules, index + 1)
        if next_index >= len(steps):
            loan.status = LoanStatus.APPROVED
            loan.current_stage = None
        else:
            loan.current_stage = steps[next_index].stage.value

        on_step(loan, entry)
        index = next_index

    return loan
