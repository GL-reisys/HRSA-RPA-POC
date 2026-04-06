from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Grant(BaseModel):
    """
    Grant entity - exactly matches GrantInfo.cs
    
    Reference: MIGRATION_DOCS/References/GrantInfo.cs
    C# Properties (6 total):
    - GrantId (Guid)
    - GrantNumber (string)
    - OrganizationId (Guid)
    - ProgramId (int)
    - ProjectPeriodEndDate (DateTime?)
    - GrantStatus (string)
    """
    
    grant_id: str = Field(..., alias="GrantId", description="Unique grant identifier (Guid)")
    grant_number: str = Field(..., alias="GrantNumber", description="Grant number (e.g., H80CS12345)")
    organization_id: str = Field(..., alias="OrganizationId", description="Organization ID (Guid)")
    program_id: int = Field(..., alias="ProgramId", description="Program identifier (int)")
    project_period_end_date: Optional[datetime] = Field(None, alias="ProjectPeriodEndDate", description="Project period end date (DateTime?)")
    grant_status: str = Field(..., alias="GrantStatus", description="Grant status")
    
    class Config:
        populate_by_name = True  # Allow both snake_case and PascalCase
        json_schema_extra = {
            "example": {
                "grant_id": "grant-001",
                "grant_number": "H80CS12345",
                "organization_id": "org-001",
                "program_id": 1,
                "project_period_end_date": "2027-12-31T00:00:00",
                "grant_status": "Active"
            }
        }
