from typing import Optional

from pydantic import BaseModel, Field


class DebtFacility(BaseModel):
    name: str = Field(default="Senior Term Loan", max_length=80)
    opening_balance: float = 0.0
    interest_margin: float = 0.045
    base_rate: float = 0.03
    amortization_pct: float = 0.10
    maturity_year: Optional[int] = None
    covenant_leverage_max: float = 3.5
    covenant_icr_min: float = 2.0

