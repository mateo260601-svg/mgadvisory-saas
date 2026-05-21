from typing import Dict, List

from pydantic import BaseModel, Field


class FinancialLine(BaseModel):
    name: str
    values: Dict[str, float] = Field(default_factory=dict)


class NormalizedFinancials(BaseModel):
    periods: List[str] = Field(default_factory=list)
    income_statement: List[FinancialLine] = Field(default_factory=list)
    balance_sheet: List[FinancialLine] = Field(default_factory=list)
    cash_flow: List[FinancialLine] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)

