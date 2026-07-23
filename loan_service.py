from __future__ import annotations

from typing import List, Optional

from src.domain.models import HistoryEntry, Loan, LoanNotFoundError, LoanStatus
from src.repository.db import Database


class LoanRepository:
    def __init__(self, database: Database):
        self._db = database

    def create(self, loan: Loan) -> None:
        with self._db.lock:
            self._db.conn.execute(
                """
                INSERT INTO loans (
                    loan_id, customer_id, amount, phone, loan_type,
                    monthly_income, credit_score, has_guarantor,
                    status, current_stage, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    loan.loan_id,
                    loan.customer_id,
                    loan.amount,
                    loan.phone,
                    loan.loan_type,
                    loan.monthly_income,
                    loan.credit_score,
                    int(loan.has_guarantor),
                    loan.status.value,
                    loan.current_stage,
                    loan.created_at,
                    loan.updated_at,
                ),
            )
            self._db.conn.commit()

    def get(self, loan_id: str) -> Optional[Loan]:
        with self._db.lock:
            row = self._db.conn.execute(
                "SELECT * FROM loans WHERE loan_id = ?", (loan_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_loan(row)

    def require(self, loan_id: str) -> Loan:
        loan = self.get(loan_id)
        if loan is None:
            raise LoanNotFoundError(loan_id)
        return loan

    def save_step(self, loan: Loan, entry: HistoryEntry) -> None:
        """Atomically persist the loan's new state and one history entry.

        The UNIQUE(loan_id, stage) constraint on loan_history guarantees a
        stage can never be recorded twice for the same loan, which is the
        storage-level backstop for the "no duplicate processing" rule.
        """
        with self._db.lock:
            conn = self._db.conn
            try:
                conn.execute(
                    """
                    UPDATE loans
                    SET status = ?, current_stage = ?, updated_at = ?
                    WHERE loan_id = ?
                    """,
                    (loan.status.value, loan.current_stage, loan.updated_at, loan.loan_id),
                )
                conn.execute(
                    """
                    INSERT INTO loan_history (loan_id, stage, result, reason, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (entry.loan_id, entry.stage, entry.result, entry.reason, entry.timestamp),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def get_history(self, loan_id: str) -> List[HistoryEntry]:
        with self._db.lock:
            rows = self._db.conn.execute(
                """
                SELECT loan_id, stage, result, reason, timestamp
                FROM loan_history
                WHERE loan_id = ?
                ORDER BY timestamp ASC, id ASC
                """,
                (loan_id,),
            ).fetchall()
        return [
            HistoryEntry(
                loan_id=row["loan_id"],
                stage=row["stage"],
                result=row["result"],
                reason=row["reason"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_loan(row) -> Loan:
        return Loan(
            loan_id=row["loan_id"],
            customer_id=row["customer_id"],
            amount=row["amount"],
            phone=row["phone"],
            loan_type=row["loan_type"],
            monthly_income=row["monthly_income"],
            credit_score=row["credit_score"],
            has_guarantor=bool(row["has_guarantor"]),
            status=LoanStatus(row["status"]),
            current_stage=row["current_stage"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
