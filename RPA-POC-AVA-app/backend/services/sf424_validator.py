from typing import List, Dict, Any
import pikepdf
import re
from services.database_service import DatabaseService
from models.validation_error import ValidationError, ValidationErrorFactory

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
        self.db_service = db_service or DatabaseService(use_sql_server=False)
    
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
    
    def validate_form_data(self, form_data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate SF-424 form data against business rules.
        Returns list of ValidationError objects with dual message system.
        """
        errors = []
        
        # Required fields
        if not form_data.get('organization_name'):
            errors.append(ValidationErrorFactory.required_field("Organization Name", "ORG_NAME"))
        
        if not form_data.get('samuei'):
            errors.append(ValidationErrorFactory.required_field("UEI (Unique Entity Identifier)", "UEI"))
        
        if not form_data.get('employer_taxpayer_identification_number'):
            errors.append(ValidationErrorFactory.required_field("EIN (Employer Identification Number)", "EIN"))
        
        if not form_data.get('project_title'):
            errors.append(ValidationErrorFactory.required_field("Project Title", "PROJECT_TITLE"))
        
        if not form_data.get('email'):
            errors.append(ValidationErrorFactory.required_field("Contact Email", "CONTACT_EMAIL"))
        
        if not form_data.get('phone_number'):
            errors.append(ValidationErrorFactory.required_field("Contact Phone Number", "CONTACT_PHONE"))
        
        if not form_data.get('funding_opportunity_number'):
            errors.append(ValidationErrorFactory.required_field("Funding Opportunity Number", "FON"))
        
        # Validate submission type
        if not form_data.get('submission_type'):
            errors.append(ValidationErrorFactory.required_field("Submission Type", "SUBMISSION_TYPE"))
        
        # Validate UEI format (12 characters, alphanumeric)
        uei = form_data.get('samuei')
        if uei and (len(uei) != 12 or not uei.isalnum()):
            errors.append(ValidationErrorFactory.invalid_format("UEI", "Must be 12 alphanumeric characters", "UEI"))
        
        # Validate EIN format (XX-XXXXXXX)
        ein = form_data.get('employer_taxpayer_identification_number')
        if ein and not self._validate_ein_format(ein):
            errors.append(ValidationErrorFactory.invalid_format("EIN", "Must be XX-XXXXXXX (e.g., 12-3456789)", "EIN"))
        
        # Validate email format
        email = form_data.get('email')
        if email and not self._validate_email_format(email):
            errors.append(ValidationErrorFactory.invalid_email_format())
        
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
            errors.append(ValidationErrorFactory.budget_mismatch(total, calculated_total))
        
        # Validate project dates
        start_date = form_data.get('project_start_date')
        end_date = form_data.get('project_end_date')
        
        if start_date and end_date:
            if str(end_date) < str(start_date):
                errors.append(ValidationErrorFactory.invalid_project_dates())
        
        # Validate authorized representative fields
        if not form_data.get('authorized_representative_first_name'):
            errors.append(ValidationErrorFactory.required_field("Authorized Representative First Name", "AUTH_REP_FIRST_NAME"))
        
        if not form_data.get('authorized_representative_last_name'):
            errors.append(ValidationErrorFactory.required_field("Authorized Representative Last Name", "AUTH_REP_LAST_NAME"))
        
        if not form_data.get('authorized_representative_email'):
            errors.append(ValidationErrorFactory.required_field("Authorized Representative Email", "AUTH_REP_EMAIL"))
        
        # Database validations
        errors.extend(self._validate_database_rules(form_data))
        
        return errors
    
    def _normalize_application_type(self, app_type: str) -> str:
        """
        Normalize application type to numeric code.
        Handles both text values from PDF form and numeric codes.
        
        PDF Form Values (from SF-424 Section 2):
        - "New" → 1
        - "Continuation" → 2
        - "Revision" → 3
        
        Args:
            app_type: Application type from form (text or numeric)
            
        Returns:
            Numeric code as string ("1", "2", or "3"), or original value if unknown
        """
        if not app_type:
            return app_type
        
        app_type_str = str(app_type).strip()
        
        # Already numeric
        if app_type_str in ["1", "2", "3"]:
            return app_type_str
        
        # Text to numeric mapping (exact PDF form values)
        mapping = {
            "new": "1",
            "continuation": "2",
            "revision": "3"
        }
        
        normalized = mapping.get(app_type_str.lower())
        return normalized if normalized else app_type_str
    
    def _normalize_submission_type(self, sub_type: str) -> str:
        """
        Normalize submission type to numeric code.
        Handles both text values from PDF form and numeric codes.
        
        PDF Form Values (from SF-424 Section 1):
        - "Preapplication" (not commonly used)
        - "Application" → 1
        - "Changed/Corrected Application" → 2
        
        Args:
            sub_type: Submission type from form (text or numeric)
            
        Returns:
            Numeric code as string ("1" or "2"), or original value if unknown
        """
        if not sub_type:
            return sub_type
        
        sub_type_str = str(sub_type).strip()
        
        # Already numeric
        if sub_type_str in ["1", "2"]:
            return sub_type_str
        
        # Text to numeric mapping (exact PDF form values)
        mapping = {
            "preapplication": "1",  # Treat as application
            "application": "1",
            "changed/corrected application": "2",
            "changed": "2",  # Partial match
            "corrected": "2",  # Partial match
            "changed/corrected": "2"  # Partial match
        }
        
        normalized = mapping.get(sub_type_str.lower())
        return normalized if normalized else sub_type_str
    
    def _validate_database_rules(self, form_data: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate form data against database records using typed models.
        
        Models match C# references exactly:
        - Organization: OrganizationInfo.cs (3 fields)
        - FundingOpportunity: FundingCycleInfo.cs (5 fields)
        
        Validates:
        1. Organization exists (UEI lookup)
        2. Organization name matches database record
        3. Funding Opportunity exists
        4. Application type matches funding opportunity requirements
        5. No duplicate applications (org already has active application for same FON)
        6. Continuation applications: Grant number required
        7. Continuation applications: Grant exists
        8. Continuation applications: Grant belongs to organization
        9. Continuation applications: Grant is active and not expired
        10. Continuation applications: Grant program matches funding opportunity program
        
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
                errors.append(ValidationErrorFactory.uei_not_found(uei))
            else:
                # Validate organization name matches
                if org_name:
                    if organization.organization_name.strip().lower() != org_name.strip().lower():
                        errors.append(ValidationErrorFactory.org_name_mismatch(
                            org_name, organization.organization_name, uei
                        ))
        
        # ========================================
        # Funding Opportunity Validation
        # ========================================
        if fon:
            # Get FundingOpportunity model from database (FundingCycleInfo.cs: 5 fields)
            funding_opportunity = self.db_service.get_funding_cycle_by_code(fon)
            
            if not funding_opportunity:
                errors.append(ValidationErrorFactory.fon_not_found(fon))
            else:
                # Validate application type matches funding opportunity requirements
                application_type = form_data.get('application_type')
                if application_type:
                    try:
                        # Normalize to numeric code
                        app_type_normalized = self._normalize_application_type(application_type)
                        app_type_code = int(app_type_normalized)
                        type_of_app_by_fo = funding_opportunity.type_of_app_by_fo
                        
                        # TypeOfAppByFO = 2 (Continuation only), but application is New (1)
                        if type_of_app_by_fo == 2 and app_type_code == 1:
                            errors.append(ValidationErrorFactory.type_mismatch_continuation_required(fon, application_type))
                        # TypeOfAppByFO = 1 (New only), but application is NOT New
                        elif type_of_app_by_fo == 1 and app_type_code != 1:
                            app_type_name = "Continuation" if app_type_code == 2 else "Revision" if app_type_code == 3 else "Unknown"
                            errors.append(ValidationErrorFactory.type_mismatch_new_required(fon, app_type_name))
                    except (ValueError, TypeError):
                        # Invalid application type format - will be caught by other validation
                        pass
                
                # ========================================
                # Federal Award Identifier Validation for "New Only" Opportunities
                # ========================================
                # Validate Grant Number should not be populated for "New only" funding opportunities
                federal_award_identifier = form_data.get('federal_award_identifier')
                if federal_award_identifier and funding_opportunity.type_of_app_by_fo == 1:
                    errors.append(ValidationErrorFactory.grant_number_not_allowed(fon))
                
                # ========================================
                # Duplicate Application Detection
                # ========================================
                # Check if organization already has an active application for this Funding Opportunity Number (FON)
                # For New applications: Check same FON + Same UEI + Same App Type = DUPLICATE
                # For Continuation/Revision: Check same FON + Same UEI + Same App Type + Same Grant # = DUPLICATE
                if uei and organization:
                    try:
                        print(f"[DEBUG] Checking for duplicates: FON={fon}, OrgID={organization.organization_id}, FundingCycleID={funding_opportunity.funding_cycle_id}")
                        
                        # Find existing applications for this org + funding opportunity combination
                        existing_apps = self.db_service.find_related_applications(
                            fo=funding_opportunity.funding_cycle_id,
                            org=organization.organization_id
                        )
                        
                        print(f"[DEBUG] Found {len(existing_apps) if existing_apps else 0} existing applications")
                        
                        if existing_apps:
                            # Get current application details
                            app_type_raw = form_data.get('application_type', 'New')
                            app_type_normalized = self._normalize_application_type(app_type_raw)
                            federal_award_identifier = form_data.get('federal_award_identifier')
                            
                            print(f"[DEBUG] Current app type: {app_type_raw} (normalized: {app_type_normalized})")
                            
                            # Check for duplicates based on application type
                            is_duplicate = False
                            
                            if app_type_normalized == "1":  # New application
                                # For New: Check if any existing app is also type 1 (New)
                                for app in existing_apps:
                                    print(f"[DEBUG] Checking existing app: ID={app['application_id']}, TypeCode={app['application_type_code']}, Status={app['application_status_flag']}, GrantID={app.get('grant_id', 'None')}")
                                    # Convert to int for comparison (handles both string and int from different sources)
                                    existing_app_type = int(app['application_type_code']) if app['application_type_code'] else 0
                                    if existing_app_type == 1:  # ApplicationTypeCode = 1 (New)
                                        print(f"[DEBUG] DUPLICATE FOUND: Another 'New' application exists (AppID={app['application_id']})")
                                        is_duplicate = True
                                        break
                            
                            elif app_type_normalized in ["2", "3"]:  # Continuation or Revision
                                # For Continuation/Revision: Check same application type AND same grant
                                if federal_award_identifier:
                                    # Get the grant ID for the current grant number
                                    current_grant = self.db_service.get_grant_by_number(federal_award_identifier)
                                    if current_grant:
                                        current_grant_id = current_grant.get('grant_id')
                                        target_app_type = 2 if app_type_normalized == "2" else 3
                                        
                                        print(f"[DEBUG] Current grant ID: {current_grant_id}, Target app type: {target_app_type}")
                                        
                                        for app in existing_apps:
                                            print(f"[DEBUG] Checking existing app: ID={app['application_id']}, TypeCode={app['application_type_code']}, GrantID={app.get('grant_id', 'None')}")
                                            # Convert to int for comparison (handles both string and int from different sources)
                                            existing_app_type = int(app['application_type_code']) if app['application_type_code'] else 0
                                            # Check if same application type AND same grant
                                            if existing_app_type == target_app_type and app.get('grant_id') == current_grant_id:  # ApplicationTypeCode and GrantId
                                                print(f"[DEBUG] DUPLICATE FOUND: Same type + same grant (AppID={app['application_id']})")
                                                is_duplicate = True
                                                break
                            
                            if is_duplicate:
                                print(f"[DEBUG] Adding duplicate application error")
                                errors.append(ValidationErrorFactory.duplicate_application(fon, app_type_raw))
                            else:
                                print(f"[DEBUG] No duplicate detected")
                    except Exception as e:
                        # Log error but don't fail validation - duplicate check is supplementary
                        print(f"[ERROR] Duplicate detection check failed: {str(e)}")
                        import traceback
                        traceback.print_exc()
        
        # ========================================
        # Continuation Application Grant Validation
        # ========================================
        application_type = form_data.get('application_type')
        federal_award_identifier = form_data.get('federal_award_identifier')
        
        # Normalize application type to handle both text and numeric values
        app_type_normalized = self._normalize_application_type(application_type)
        
        if app_type_normalized == "2":  # Continuation application
            # Require grant number for continuation applications
            if not federal_award_identifier:
                errors.append(ValidationErrorFactory.grant_number_required())
            else:
                try:
                    # Get grant by number
                    grant = self.db_service.get_grant_by_number(federal_award_identifier)
                    
                    if not grant:
                        errors.append(ValidationErrorFactory.grant_not_found(federal_award_identifier))
                    else:
                        # Validate grant ownership (only if organization was validated)
                        if uei and organization:
                            # Check if grant belongs to this organization via grant_organizations
                            active_grants = self.db_service.get_active_grants_by_organization(
                                organization_id=organization.organization_id,
                                funding_cycle_id=funding_opportunity.funding_cycle_id if funding_opportunity else ""
                            )
                            
                            grant_belongs_to_org = any(
                                g.get('grant_number') == federal_award_identifier 
                                for g in active_grants
                            )
                            
                            if not grant_belongs_to_org:
                                errors.append(ValidationErrorFactory.grant_ownership_mismatch(federal_award_identifier, uei))
                            else:
                                # Check if grant is expired (via awards table)
                                grant_is_active = False
                                for g in active_grants:
                                    if g.get('grant_number') == federal_award_identifier:
                                        grant_is_active = True
                                        break
                                
                                if not grant_is_active:
                                    errors.append(ValidationErrorFactory.grant_expired(federal_award_identifier))
                        
                        # Validate program match (only if funding opportunity was validated)
                        if funding_opportunity:
                            program_match = self.db_service.check_program_match(
                                grant_id=grant.get('grant_id'),
                                fo=funding_opportunity.funding_cycle_id
                            )
                            
                            if not program_match:
                                errors.append(ValidationErrorFactory.grant_program_mismatch(federal_award_identifier, fon))
                
                except Exception as e:
                    # Log error but don't fail validation
                    print(f"Warning: Grant validation check failed: {str(e)}")
        
        return errors
    
    def _validate_ein_format(self, ein: str) -> bool:
        """Validate EIN format: XX-XXXXXXX"""
        pattern = r'^\d{2}-\d{7}$'
        return bool(re.match(pattern, ein))
    
    def _validate_email_format(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
