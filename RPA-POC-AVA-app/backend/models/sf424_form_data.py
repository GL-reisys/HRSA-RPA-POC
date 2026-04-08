from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class SF424FormData(BaseModel):
    """
    SF-424 Application for Federal Assistance form data model.
    Total: 88 fields across 10 sections.
    """
    
    # ========================================
    # Section 1: Application Information (10 fields)
    # ========================================
    submission_type: Optional[str] = Field(None, description="1=New, 2=Changed/Corrected")
    application_type: Optional[str] = Field(None, description="1=New, 2=Continuation, 3=Revision")
    revision_type: Optional[str] = None
    revision_other_specify: Optional[str] = None
    date_received: Optional[datetime] = None
    applicant_id: Optional[str] = None
    federal_entity_identifier: Optional[str] = None
    federal_award_identifier: Optional[str] = None
    state_receive_date: Optional[datetime] = None
    state_application_id: Optional[str] = None
    
    # ========================================
    # Section 2: Applicant Information (3 fields)
    # ========================================
    organization_name: Optional[str] = Field(None, description="Legal name of organization")
    employer_taxpayer_identification_number: Optional[str] = Field(None, description="EIN format: XX-XXXXXXX")
    samuei: Optional[str] = Field(None, description="UEI (Unique Entity Identifier), 12 characters")
    
    # ========================================
    # Section 3: Applicant Address (6 fields)
    # ========================================
    applicant_street1: Optional[str] = None
    applicant_street2: Optional[str] = None
    applicant_city: Optional[str] = None
    applicant_state: Optional[str] = Field(None, description="2-letter state code")
    applicant_zip_postal_code: Optional[str] = None
    applicant_country: Optional[str] = Field(None, description="Default: USA")
    
    # ========================================
    # Section 4: Contact Information (9 fields)
    # ========================================
    department_name: Optional[str] = None
    division_name: Optional[str] = None
    contact_person_first_name: Optional[str] = None
    contact_person_last_name: Optional[str] = None
    title: Optional[str] = Field(None, description="Contact person's title")
    organization_affiliation: Optional[str] = None
    phone_number: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    
    # ========================================
    # Section 5: Applicant Type (4 fields)
    # ========================================
    applicant_type_code1: Optional[str] = None
    applicant_type_code2: Optional[str] = None
    applicant_type_code3: Optional[str] = None
    applicant_type_other_specify: Optional[str] = None
    
    # ========================================
    # Section 6: Federal Agency and Program (7 fields)
    # ========================================
    agency_name: Optional[str] = Field(None, description="Federal agency name")
    cfda_number: Optional[str] = Field(None, description="Catalog of Federal Domestic Assistance number")
    cfda_program_title: Optional[str] = None
    funding_opportunity_number: Optional[str] = Field(None, description="FON from announcement")
    funding_opportunity_title: Optional[str] = None
    competition_identification_number: Optional[str] = None
    competition_identification_title: Optional[str] = None
    
    # ========================================
    # Section 7: Project Information (5 fields)
    # ========================================
    project_title: Optional[str] = Field(None, description="Descriptive title of project")
    congressional_district_applicant: Optional[str] = None
    congressional_district_program_project: Optional[str] = None
    project_start_date: Optional[datetime] = None
    project_end_date: Optional[datetime] = None
    
    # ========================================
    # Section 8: Budget Information (7 fields)
    # ========================================
    federal_estimated_funding: Optional[Decimal] = Field(None, description="Federal funds requested")
    applicant_estimated_funding: Optional[Decimal] = Field(None, description="Applicant contribution")
    state_estimated_funding: Optional[Decimal] = None
    local_estimated_funding: Optional[Decimal] = None
    other_estimated_funding: Optional[Decimal] = None
    program_income_estimated_funding: Optional[Decimal] = None
    total_estimated_funding: Optional[Decimal] = Field(None, description="Sum of all funding sources")
    
    # ========================================
    # Section 9: State Review and Certification (4 fields)
    # ========================================
    state_review: Optional[str] = None
    state_review_available_date: Optional[datetime] = None
    delinquent_federal_debt: Optional[str] = Field(None, description="Yes/No")
    certification_agree: Optional[str] = Field(None, description="Yes/No")
    
    # ========================================
    # Section 10: Authorized Representative (10 fields)
    # ========================================
    authorized_representative_first_name: Optional[str] = None
    authorized_representative_last_name: Optional[str] = None
    authorized_representative_title: Optional[str] = None
    authorized_representative_phone_number: Optional[str] = None
    authorized_representative_email: Optional[str] = None
    authorized_representative_fax: Optional[str] = None
    aor_signature: Optional[str] = Field(None, description="Digital signature or name")
    date_signed: Optional[datetime] = None
    
    # ========================================
    # Computed Properties
    # ========================================
    @property
    def contact_person_full_name(self) -> str:
        """Full name of contact person"""
        first = self.contact_person_first_name or ""
        last = self.contact_person_last_name or ""
        return f"{first} {last}".strip()
    
    @property
    def authorized_representative_full_name(self) -> str:
        """Full name of authorized representative"""
        first = self.authorized_representative_first_name or ""
        last = self.authorized_representative_last_name or ""
        return f"{first} {last}".strip()
    
    @property
    def full_address(self) -> str:
        """Complete formatted address"""
        parts = [
            self.applicant_street1,
            self.applicant_street2,
            f"{self.applicant_city}, {self.applicant_state} {self.applicant_zip_postal_code}",
            self.applicant_country
        ]
        return ", ".join(filter(None, parts))
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            Decimal: lambda v: float(v) if v else None
        }
        validate_assignment = True
        use_enum_values = True
