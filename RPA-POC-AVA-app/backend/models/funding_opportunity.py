from pydantic import BaseModel, Field

class FundingOpportunity(BaseModel):
    """
    Funding Opportunity entity - exactly matches FundingCycleInfo.cs
    
    Reference: MIGRATION_DOCS/References/FundingCycleInfo.cs
    C# Properties (5 total):
    - FundingCycleId (Guid)
    - FundingCycleCode (string)
    - AnnouncementNumber (string)
    - TypeOfAppByFO (int)
    - ProgramId (int)
    """
    
    funding_cycle_id: str = Field(..., alias="FundingCycleId", description="Unique funding cycle identifier (Guid)")
    funding_cycle_code: str = Field(..., alias="FundingCycleCode", description="Funding cycle code")
    announcement_number: str = Field(..., alias="AnnouncementNumber", description="Funding Opportunity Number (FON)")
    type_of_app_by_fo: int = Field(..., alias="TypeOfAppByFO", description="Application type code (int)")
    program_id: int = Field(..., alias="ProgramId", description="Program identifier (int)")
    
    class Config:
        populate_by_name = True  # Allow both snake_case and PascalCase
        json_schema_extra = {
            "example": {
                "funding_cycle_id": "fc-001",
                "funding_cycle_code": "HRSA-25-091",
                "announcement_number": "HRSA-25-091",
                "type_of_app_by_fo": 1,
                "program_id": 1
            }
        }
