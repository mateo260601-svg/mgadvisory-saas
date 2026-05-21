from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=160)
    project_type: str = Field(default="Investment case", max_length=80)
    currency: str = Field(default="EUR", max_length=8)
    fiscal_year_end: str = Field(default="December", max_length=20)
    industry: str = Field(default="", max_length=80)
    country: str = Field(default="", max_length=60)
    description: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    company_name: Optional[str] = Field(None, min_length=2, max_length=160)
    project_type: Optional[str] = Field(None, max_length=80)
    currency: Optional[str] = Field(None, max_length=8)
    fiscal_year_end: Optional[str] = Field(None, max_length=20)
    industry: Optional[str] = Field(None, max_length=80)
    country: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, max_length=20)


class Project(BaseModel):
    id: str
    company_name: str
    project_type: str
    currency: str
    fiscal_year_end: str
    industry: str = ""
    country: str = ""
    description: str = ""
    notes: str = ""
    created_at: datetime
    updated_at: datetime
    status: str = "active"
