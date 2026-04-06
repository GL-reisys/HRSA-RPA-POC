from typing import List, Dict, Any
import pikepdf
import re
from services.database_service import DatabaseService

class SF424Validator:
    """
    Validates PDF structure and SF-424 form data.
    Includes database validation for UEI, Funding Opportunity, etc.
    Based on C# XfaPdfValidator.cs
    """
    
    def __init__(self, db_service: DatabaseService = None):
        """
        Initialize validator with optional database service.
        
        Args:
            db_service: DatabaseService instance (defaults to JSON-based)
        """
        self.db_service = db_service or DatabaseService(use_postgres=False)
    
    def validate_pdf_structure(self, pdf_path: str) -> bool:
        """
        Validate that PDF is a valid XFA or AcroForm.
        Returns True if valid, False otherwise.
        """
        try:
            pdf = pikepdf.open(pdf_path)
            
            if '/AcroForm' not in pdf.Root:
                print("PDF does not contain a form")
                return False
            
            acro_form = pdf.Root.AcroForm
            
            has_xfa = '/XFA' in acro_form
            has_fields = '/Fields' in acro_form
            
            if not has_xfa and not has_fields:
                print("PDF form has no XFA or Fields")
                return False
            
            pdf.close()
            return True
            
        except Exception as e:
            print(f"PDF validation error: {str(e)}")
            return False
    
    def validate_form_data(self, form_data: Dict[str, Any]) -> List[str]:
        """
        Validate SF-424 form data against business rules.
        Returns list of validation error messages.
        """
        errors = []
        
        # Required fields
        if not form_data.get('organization_name'):
            errors.append("Missing required field: Organization Name")
        
        if not form_data.get('samuei'):
            errors.append("Missing required field: UEI (Unique Entity Identifier)")
        
        if not form_data.get('employer_taxpayer_identification_number'):
            errors.append("Missing required field: EIN (Employer Identification Number)")
        
        if not form_data.get('project_title'):
            errors.append("Missing required field: Project Title")
        
        if not form_data.get('email'):
            errors.append("Missing required field: Contact Email")
        
        if not form_data.get('phone_number'):
            errors.append("Missing required field: Contact Phone Number")
        
        if not form_data.get('funding_opportunity_number'):
            errors.append("Missing required field: Funding Opportunity Number")
        
        # Validate submission type
        if not form_data.get('submission_type'):
            errors.append("Missing required field: Submission Type")
        
        # Validate UEI format (12 characters, alphanumeric)
        uei = form_data.get('samuei')
        if uei and (len(uei) != 12 or not uei.isalnum()):
            errors.append("Invalid UEI format: Must be 12 alphanumeric characters")
        
        # Validate EIN format (XX-XXXXXXX)
        ein = form_data.get('employer_taxpayer_identification_number')
        if ein and not self._validate_ein_format(ein):
            errors.append("Invalid EIN format: Must be XX-XXXXXXX")
        
        # Validate email format
        email = form_data.get('email')
        if email and not self._validate_email_format(email):
            errors.append("Invalid email format")
        
        # Validate budget totals
        federal = form_data.get('federal_estimated_funding', 0) or 0
        applicant = form_data.get('applicant_estimated_funding', 0) or 0
        state = form_data.get('state_estimated_funding', 0) or 0
        local = form_data.get('local_estimated_funding', 0) or 0
        other = form_data.get('other_estimated_funding', 0) or 0
        program_income = form_data.get('program_income_estimated_funding', 0) or 0
        total = form_data.get('total_estimated_funding', 0) or 0
        
        calculated_total = federal + applicant + state + local + other + program_income
        
        if total > 0 and abs(calculated_total - total) > 0.01:
            errors.append(f"Budget mismatch: Total ({total}) does not equal sum of sources ({calculated_total})")
        
        # Validate project dates
        start_date = form_data.get('project_start_date')
        end_date = form_data.get('project_end_date')
        
        if start_date and end_date:
            if str(end_date) < str(start_date):
                errors.append("Project end date must be after start date")
        
        # Validate authorized representative fields
        if not form_data.get('authorized_representative_first_name'):
            errors.append("Missing required field: Authorized Representative First Name")
        
        if not form_data.get('authorized_representative_last_name'):
            errors.append("Missing required field: Authorized Representative Last Name")
        
        if not form_data.get('authorized_representative_email'):
            errors.append("Missing required field: Authorized Representative Email")
        
        # Database validations
        errors.extend(self._validate_database_rules(form_data))
        
        return errors
    
    def _validate_database_rules(self, form_data: Dict[str, Any]) -> List[str]:
        """
        Validate form data against database records using typed models.
        
        Models match C# references exactly:
        - Organization: OrganizationInfo.cs (3 fields)
        - FundingOpportunity: FundingCycleInfo.cs (5 fields)
        
        Validates:
        1. Organization exists (UEI lookup)
        2. Organization name matches database record
        3. Funding Opportunity exists
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Extract form data
        uei = form_data.get('samuei')
        org_name = form_data.get('organization_name')
        fon = form_data.get('funding_opportunity_number')
        
        # ========================================
        # Organization Validation
        # ========================================
        if uei:
            # Get Organization model from database (OrganizationInfo.cs: 3 fields)
            organization = self.db_service.get_organization_by_uei(uei)
            
            if not organization:
                errors.append(
                    f"UEI '{uei}' not found in system. "
                    "Please verify your organization is registered in SAM.gov."
                )
            else:
                # Validate organization name matches
                if org_name:
                    if organization.organization_name.strip().lower() != org_name.strip().lower():
                        errors.append(
                            f"Organization name '{org_name}' does not match the registered name "
                            f"'{organization.organization_name}' for UEI '{uei}'."
                        )
        
        # ========================================
        # Funding Opportunity Validation
        # ========================================
        if fon:
            # Get FundingOpportunity model from database (FundingCycleInfo.cs: 5 fields)
            funding_opportunity = self.db_service.get_funding_cycle_by_code(fon)
            
            if not funding_opportunity:
                errors.append(
                    f"Funding Opportunity Number '{fon}' not found. "
                    "Please verify the FON matches the announcement exactly."
                )
            else:
                # Validate application type matches funding opportunity requirements
                application_type = form_data.get('application_type')
                if application_type:
                    try:
                        app_type_code = int(application_type)
                        type_of_app_by_fo = funding_opportunity.type_of_app_by_fo
                        
                        # TypeOfAppByFO = 2 (Continuation only), but application is New (1)
                        if type_of_app_by_fo == 2 and app_type_code == 1:
                            errors.append(
                                f"Application type mismatch: Funding Opportunity '{fon}' only accepts "
                                "Continuation applications, but you submitted a New application."
                            )
                        # TypeOfAppByFO = 1 (New only), but application is NOT New
                        elif type_of_app_by_fo == 1 and app_type_code != 1:
                            app_type_name = "Continuation" if app_type_code == 2 else "Revision" if app_type_code == 3 else "Unknown"
                            errors.append(
                                f"Application type mismatch: Funding Opportunity '{fon}' only accepts "
                                f"New applications, but you submitted a {app_type_name} application."
                            )
                    except (ValueError, TypeError):
                        # Invalid application type format - will be caught by other validation
                        pass
        
        return errors
    
    def _validate_ein_format(self, ein: str) -> bool:
        """Validate EIN format: XX-XXXXXXX"""
        pattern = r'^\d{2}-\d{7}$'
        return bool(re.match(pattern, ein))
    
    def _validate_email_format(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
