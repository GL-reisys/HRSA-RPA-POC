from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class Application(BaseModel):
    """
    Application entity - represents data extracted from SF-424 PDF form.
    This is the application being submitted by the applicant.
    
    References:
    - MIGRATION_DOCS/References/ApplicationInfo.cs (Application metadata)
    - MIGRATION_DOCS/References/SF424FormData.cs (Form field structure)
    
    C# ApplicationInfo Properties:
    - ApplicationId (Guid)
    - GrantsGovApplicationId (string)
    - GrantsGovTrackingNo (string)
    - ApplicationStatusFlag (string)
    
    C# SF424FormData Properties: 108 fields covering all SF-424 sections
    """
    
    # Application metadata (from ApplicationInfo.cs)
    application_id: Optional[str] = Field(None, alias="ApplicationId", description="Unique application identifier (Guid)")
    grants_gov_application_id: Optional[str] = Field(None, alias="GrantsGovApplicationId", description="Grants.gov application ID")
    grants_gov_tracking_no: Optional[str] = Field(None, alias="GrantsGovTrackingNo", description="Grants.gov tracking number")
    application_status: str = Field(default="Draft", alias="ApplicationStatusFlag", description="Application status flag")
    submission_date: Optional[datetime] = Field(None, description="Date application was submitted")
    
    # Organization Information (from SF424FormData.cs)
    organization_name: str = Field(..., alias="OrganizationName", description="Applicant organization name")
    uei: str = Field(..., alias="SAMUEI", min_length=12, max_length=12, description="Unique Entity Identifier")
    ein: str = Field(..., alias="EmployerTaxpayerIdentificationNumber", description="Employer Identification Number")
    
    # Funding Opportunity (from SF424FormData.cs)
    funding_opportunity_number: str = Field(..., alias="FundingOpportunityNumber", description="Funding Opportunity Number")
    
    # Project Information (from SF424FormData.cs)
    project_title: str = Field(..., alias="ProjectTitle", description="Project title")
    project_start_date: date = Field(..., alias="ProjectStartDate", description="Project start date")
    project_end_date: date = Field(..., alias="ProjectEndDate", description="Project end date")
    
    # Budget Information (from SF424FormData.cs - decimal? in C#)
    federal_estimated_funding: float = Field(..., alias="FederalEstimatedFunding", ge=0, description="Federal funding requested")
    applicant_estimated_funding: float = Field(default=0, alias="ApplicantEstimatedFunding", ge=0, description="Applicant contribution")
    state_estimated_funding: float = Field(default=0, alias="StateEstimatedFunding", ge=0, description="State funding")
    local_estimated_funding: float = Field(default=0, alias="LocalEstimatedFunding", ge=0, description="Local funding")
    other_estimated_funding: float = Field(default=0, alias="OtherEstimatedFunding", ge=0, description="Other funding")
    program_income_estimated_funding: float = Field(default=0, alias="ProgramIncomeEstimatedFunding", ge=0, description="Program income")
    total_estimated_funding: float = Field(..., alias="TotalEstimatedFunding", ge=0, description="Total funding")
    
    # Contact Information (from SF424FormData.cs)
    contact_email: str = Field(..., alias="Email", description="Contact email")
    contact_phone: str = Field(..., alias="PhoneNumber", description="Contact phone number")
    
    # Authorized Representative (from SF424FormData.cs)
    authorized_representative_first_name: str = Field(..., alias="AuthorizedRepresentative_FirstName", description="AOR first name")
    authorized_representative_last_name: str = Field(..., alias="AuthorizedRepresentative_LastName", description="AOR last name")
    authorized_representative_email: str = Field(..., alias="AuthorizedRepresentativeEmail", description="AOR email")
    
    # Application Type (from SF424FormData.cs)
    application_type: Optional[str] = Field(None, alias="ApplicationType", description="Application type (New/Continuation/Revision)")
    
    # Related Grant (for continuations)
    related_grant_number: Optional[str] = Field(None, description="Grant number for continuation applications")
    
    class Config:
        populate_by_name = True  # Allow both snake_case and PascalCase
        json_schema_extra = {
            "example": {
                "application_id": "app-001",
                "submission_date": "2026-04-03T18:49:00",
                "application_status": "Draft",
                "organization_name": "Testing INC",
                "uei": "P3PBCKY723N6",
                "ein": "12-3456789",
                "funding_opportunity_number": "HRSA-25-091",
                "project_title": "Community Health Initiative",
                "project_start_date": "2026-07-01",
                "project_end_date": "2027-06-30",
                "federal_estimated_funding": 500000.00,
                "total_estimated_funding": 500000.00,
                "contact_email": "contact@testinginc.org",
                "contact_phone": "555-123-4567",
                "authorized_representative_first_name": "John",
                "authorized_representative_last_name": "Doe",
                "authorized_representative_email": "john.doe@testinginc.org",
                "application_type": "New"
            }
        }
    
    def calculate_total_funding(self) -> float:
        """Calculate total funding from all sources"""
        return (
            self.federal_estimated_funding +
            self.applicant_estimated_funding +
            self.state_estimated_funding +
            self.local_estimated_funding +
            self.other_estimated_funding +
            self.program_income_estimated_funding
        )
    
    def validate_budget_totals(self) -> bool:
        """Validate that total matches sum of sources"""
        calculated = self.calculate_total_funding()
        return abs(calculated - self.total_estimated_funding) <= 0.01
    
    def is_continuation(self) -> bool:
        """Check if this is a continuation application"""
        return self.application_type == "Continuation" and self.related_grant_number is not None
    
    def project_duration_days(self) -> int:
        """Calculate project duration in days"""
        return (self.project_end_date - self.project_start_date).days
