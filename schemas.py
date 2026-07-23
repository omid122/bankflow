from __future__ import annotations

import threading
import uuid
from typing import List

from src.domain.models import (
    HistoryEntry,
    Loan,
    LoanStatus,
    Stage,
    TERMINAL_STATUSES,
)
from src.domain.rules import RulesConfig
from src.repository.loan_repository import LoanRepository
from src.workflow.engine import run_workflow


def generate_loan_id() -> str:
    return f"L-{uuid.uuid4().hex[:10].upper()}"


class LoanService:
    """Application service: the single entry point business logic goes
    through. Coordinates the repository (persistence) and the workflow
    engine (business process execution), and owns the concurrency /
    idempotency guarantees that neither of those two care about.
    """

    def __init__(self, repository: LoanRepository, rules: RulesConfig):
        self._repository = repository
        self._rules = rules
        # One lock per loan id prevents two concurrent /process calls for
        # the SAME loan from interleaving. A short-lived global lock only
        # guards creation/lookup of the per-loan lock objects themselves.
        self._locks_guard = threading.Lock()
        self._loan_locks: dict[str, threading.Lock] = {}

    def _lock_for(self, loan_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._loan_locks.get(loan_id)
            if lock is None:
                lock = threading.Lock()
                self._loan_locks[loan_id] = lock
            return lock

    def create_loan(
        self,
        customer_id: str,
        amount: int,
        phone: str,
        loan_type: str,
        monthly_income: int,
        credit_score: int,
        has_guarantor: bool,
    ) -> Loan:
        loan = Loan(
            loan_id=generate_loan_id(),
            customer_id=customer_id,
            amount=amount,
            phone=phone,
            loan_type=loan_type,
            monthly_income=monthly_income,
            credit_score=credit_score,
            has_guarantor=has_guarantor,
            status=LoanStatus.SUBMITTED,
            current_stage=Stage.VALIDATION.value,
        )
        self._repository.create(loan)
        return loan

    def process_loan(self, loan_id: str) -> Loan:
        with self._lock_for(loan_id):
            loan = self._repository.require(loan_id)

            if loan.status in TERMINAL_STATUSES:
                # FR-9: reprocessing a finished loan must not re-run stages,
                # must not duplicate history, and must not change the
                # final status. Simply return the current state.
                return loan

            def on_step(current_loan: Loan, entry: HistoryEntry) -> None:
                self._repository.save_step(current_loan, entry)

            return run_workflow(loan, self._rules, on_step)

    def get_loan(self, loan_id: str) -> Loan:
        return self._repository.require(loan_id)

    def get_history(self, loan_id: str) -> List[HistoryEntry]:
        # Ensure the loan exists so callers get a proper 404 instead of an
        # empty (and ambiguous) history list.
        self._repository.require(loan_id)
        return self._repository.get_history(loan_id)
