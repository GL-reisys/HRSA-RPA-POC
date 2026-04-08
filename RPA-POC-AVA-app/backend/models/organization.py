from pydantic import BaseModel, Field

class Organization(BaseModel):
    """
    Organization entity - exactly matches OrganizationInfo.cs
    
    Reference: MIGRATION_DOCS/References/OrganizationInfo.cs
    C# Properties (3 total):
    - OrganizationId (Guid)
    - OrganizationName (string)
    - UEI (string)
    """
    
    organization_id: str = Field(..., alias="OrganizationId", description="Unique organization identifier (Guid)")
    organization_name: str = Field(..., alias="OrganizationName", description="Organization legal name")
    uei: str = Field(..., alias="UEI", min_length=12, max_length=12, description="Unique Entity Identifier (SAM.gov)")
    
    class Config:
        populate_by_name = True  # Allow both snake_case and PascalCase
        json_schema_extra = {
            "example": {
                "organization_id": "org-001",
                "organization_name": "Testing INC",
                "uei": "P3PBCKY723N6"
            }
        }
