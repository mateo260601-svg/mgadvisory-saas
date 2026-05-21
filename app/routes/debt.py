from fastapi import APIRouter

from app.engines.debt_engine import debt_library_payload
from app.schemas.debt_schema import DebtFacility


router = APIRouter(prefix="/api/debt", tags=["debt"])


@router.post("/preview")
def preview_debt(payload: DebtFacility):
    interest_rate = payload.interest_margin + payload.base_rate
    annual_interest = payload.opening_balance * interest_rate
    annual_amortization = payload.opening_balance * payload.amortization_pct
    return {
        "facility": payload.model_dump(),
        "all_in_rate": interest_rate,
        "annual_interest": annual_interest,
        "annual_amortization": annual_amortization,
    }


@router.get("/library")
def debt_library():
    return debt_library_payload()
