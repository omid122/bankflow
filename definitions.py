"""API-layer schemas.

Important design note: per the challenge spec, business-rule validation
(amount > 0, phone format, credit score range, etc.) happens INSIDE the
VALIDATION workflow stage, not at the HTTP boundary. A syntactically valid
JSON body with a negative amount must be accepted (201) and only rejected
once /process runs the workflow. The API layer therefore only enforces
that the JSON is well-formed and the required fields are present with the
right basic type -- nothing more.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateLoanRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    customer_id: str = Field(alias="customerId")
    amount: int
    phone: str
    loan_type: str = Field(alias="loanType")
    monthly_income: int = Field(alias="monthlyIncome")
    credit_score: int = Field(alias="creditScore")
    has_guarantor: bool = Field(alias="hasGuarantor")


class CreateLoanResponse(BaseModel):
    loanId: str
    status: str
    currentStage: Optional[str]


class ProcessLoanResponse(BaseModel):
    loanId: str
    status: str
    currentStage: Optional[str]


class LoanDetailResponse(BaseModel):
    loanId: str
    customerId: str
    amount: int
    phone: str
    loanType: str
    monthlyIncome: int
    creditScore: int
    hasGuarantor: bool
    status: str
    currentStage: Optional[str]
    createdAt: str
    updatedAt: str


class HistoryEntryResponse(BaseModel):
    stage: str
    result: str
    timestamp: str
    reason: str


class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: str = "UP"
