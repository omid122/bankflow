from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.schemas import (
    CreateLoanRequest,
    CreateLoanResponse,
    HealthResponse,
    HistoryEntryResponse,
    LoanDetailResponse,
    ProcessLoanResponse,
)
from src.domain.models import HistoryEntry, Loan
from src.services.loan_service import LoanService

router = APIRouter()


def _service(request: Request) -> LoanService:
    return request.app.state.loan_service


def _loan_to_detail(loan: Loan) -> LoanDetailResponse:
    return LoanDetailResponse(
        loanId=loan.loan_id,
        customerId=loan.customer_id,
        amount=loan.amount,
        phone=loan.phone,
        loanType=loan.loan_type,
        monthlyIncome=loan.monthly_income,
        creditScore=loan.credit_score,
        hasGuarantor=loan.has_guarantor,
        status=loan.status.value,
        currentStage=loan.current_stage,
        createdAt=loan.created_at,
        updatedAt=loan.updated_at,
    )


def _history_to_response(entry: HistoryEntry) -> HistoryEntryResponse:
    return HistoryEntryResponse(
        stage=entry.stage,
        result=entry.result,
        timestamp=entry.timestamp,
        reason=entry.reason,
    )


@router.post("/api/v1/loans", response_model=CreateLoanResponse, status_code=201)
def create_loan(payload: CreateLoanRequest, request: Request):
    service = _service(request)
    loan = service.create_loan(
        customer_id=payload.customer_id,
        amount=payload.amount,
        phone=payload.phone,
        loan_type=payload.loan_type,
        monthly_income=payload.monthly_income,
        credit_score=payload.credit_score,
        has_guarantor=payload.has_guarantor,
    )
    return CreateLoanResponse(
        loanId=loan.loan_id, status=loan.status.value, currentStage=loan.current_stage
    )


@router.post("/api/v1/loans/{loan_id}/process", response_model=ProcessLoanResponse)
def process_loan(loan_id: str, request: Request):
    service = _service(request)
    loan = service.process_loan(loan_id)
    return ProcessLoanResponse(
        loanId=loan.loan_id, status=loan.status.value, currentStage=loan.current_stage
    )


@router.get("/api/v1/loans/{loan_id}", response_model=LoanDetailResponse)
def get_loan(loan_id: str, request: Request):
    service = _service(request)
    loan = service.get_loan(loan_id)
    return _loan_to_detail(loan)


@router.get("/api/v1/loans/{loan_id}/history", response_model=list[HistoryEntryResponse])
def get_history(loan_id: str, request: Request):
    service = _service(request)
    entries = service.get_history(loan_id)
    return [_history_to_response(e) for e in entries]


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="UP")
