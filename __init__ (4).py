from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.domain.models import LoanNotFoundError


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # A malformed / structurally invalid request body -> INVALID_REQUEST.
    return JSONResponse(status_code=400, content={"error": "INVALID_REQUEST"})


async def loan_not_found_handler(request: Request, exc: LoanNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "LOAN_NOT_FOUND"})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "INVALID_REQUEST"})
