import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationError:
    user_message: str
    ai_context: str
    field_name: Optional[str] = None
    page_number: Optional[int] = None
    field_location: Optional[str] = None
    current_value: Optional[str] = None
    guidance: Optional[str] = None
    image_path: Optional[str] = None


class ValidationErrorFactory:
    @staticmethod
    def _create(user_message: str, ai_context: str, field_name: str = None, 
                page_number: int = None, field_location: str = None, 
                current_value: str = None, guidance: str = None, image_path: str = None) -> ValidationError:
        return ValidationError(
            user_message=user_message, 
            ai_context=ai_context,
            field_name=field_name,
            page_number=page_number,
            field_location=field_location,
            current_value=current_value,
            guidance=guidance,
            image_path=image_path
        )

    @staticmethod
    def required_field(field_name: str, field_code: str) -> ValidationError:
        return ValidationErrorFactory._create(
            f"{field_name} is required.",
            f"Required field missing: {field_name} ({field_code}).",
        )

    @staticmethod
    def invalid_format(field_name: str, expected_format: str, field_code: str) -> ValidationError:
        return ValidationErrorFactory._create(
            f"{field_name} has an invalid format. {expected_format}.",
            f"Invalid format for {field_name} ({field_code}). Expected: {expected_format}.",
        )

    @staticmethod
    def invalid_email_format() -> ValidationError:
        return ValidationErrorFactory._create(
            "Contact Email has an invalid format.",
            "Invalid email format detected for Contact Email.",
        )

    @staticmethod
    def budget_mismatch(total: float, calculated_total: float) -> ValidationError:
        return ValidationErrorFactory._create(
            "Total estimated funding does not match the sum of the budget fields.",
            f"Budget mismatch detected. Reported total: {total}. Calculated total: {calculated_total}.",
        )

    @staticmethod
    def invalid_project_dates() -> ValidationError:
        return ValidationErrorFactory._create(
            "Project end date must be on or after the project start date.",
            "Project date range is invalid because the end date is before the start date.",
        )

    @staticmethod
    def uei_not_found(uei: str) -> ValidationError:
        guidance = "• Verify the UEI by checking the SAM.gov registry. Go to the SAM.gov website and use the search function to enter your UEI. Confirm if the UEI is currently active and registered.<br>• If the UEI is inactive or not found, consider registering through SAM.gov to obtain a valid UEI."
        return ValidationErrorFactory._create(
            "UEI is neither associated with an organization registered in the system nor in SAM.gov.",
            f"UEI lookup failed. UEI not found: {uei}. This UEI does not exist in the SAM.gov registry or is inactive.",
            field_name="UEI",
            page_number=1,
            field_location="Page 1, Field 8c",
            current_value=uei,
            guidance=guidance,
            image_path="/static/images/fields/uei_field.png"
        )

    @staticmethod
    def org_name_mismatch(submitted_name: str, expected_name: str, uei: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Organization Name is incorrect.",
            f"Organization name mismatch for UEI {uei}. Submitted: {submitted_name}. Expected registered name in SAM.gov: {expected_name}.",
            field_name="Organization Name",
            page_number=1,
            field_location="Page 1, Field 8a",
            current_value=submitted_name,
            guidance=None
        )

    @staticmethod
    def fon_not_found(fon: str) -> ValidationError:
        guidance = "• Verify the Funding Opportunity Number by checking the official Grants.gov website for current funding opportunities.<br>• Confirm that the Funding Opportunity Number HRSA-26-994 is correct by checking the official Grants.gov website for current opportunities."
        return ValidationErrorFactory._create(
            "Funding Opportunity Number is incorrect.",
            f"Funding Opportunity Number not found in system: {fon}. This funding opportunity number does not exist or is not currently accepting applications.",
            field_name="Funding Opportunity Number",
            page_number=1,
            field_location="Page 1, Field 4",
            current_value=fon,
            guidance=guidance,
            image_path="/static/images/fields/funding_opportunity_field.png"
        )

    @staticmethod
    def type_mismatch_continuation_required(fon: str, application_type: str = "New") -> ValidationError:
        return ValidationErrorFactory._create(
            "Type of Application is incorrect. This funding opportunity only accepts continuation applications.",
            f"Application type mismatch for funding opportunity {fon}. You submitted {application_type} but this FON only accepts Continuation applications.",
            field_name="Type of Application",
            page_number=1,
            field_location="Kindly update Page 1, Field 2",
            current_value=application_type,
            guidance=None,
            image_path="/static/images/fields/application_type_field.png"
        )

    @staticmethod
    def type_mismatch_new_required(fon: str, application_type: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Type of Application is incorrect. This funding opportunity only accepts new applications.",
            f"Application type mismatch for funding opportunity {fon}. You submitted {application_type} but this FON only accepts New applications.",
            field_name="Type of Application",
            page_number=1,
            field_location="Kindly update Page 1, Field 2",
            current_value=application_type,
            guidance=None,
            image_path="/static/images/fields/application_type_field.png"
        )

    @staticmethod
    def grant_number_not_allowed(fon: str) -> ValidationError:
        guidance = "• Verify that the Funding Opportunity Number in Field 1 only accepts New applications.<br>• If this is a New application, leave Field 5b (Federal Award Identifier) blank."
        return ValidationErrorFactory._create(
            "Grant Number should not be provided for this funding opportunity.",
            f"Grant Number was provided for funding opportunity {fon}, which only accepts new applications.",
            field_name="Grant Number/Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            guidance=guidance,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def duplicate_application(fon: str, application_type: str = "New") -> ValidationError:
        guidance = "• If a duplicate application is found, reach out to Program/Grants Office Contact for details."
        return ValidationErrorFactory._create(
            "An application for this funding opportunity already exists.",
            f"Duplicate application detected for funding opportunity {fon}. An application already exists for this organization.",
            field_name="Type of Application",
            page_number=1,
            field_location="Page 1, Field 2",
            current_value=application_type,
            guidance=guidance,
            image_path="/static/images/fields/application_type_field.png"
        )

    @staticmethod
    def grant_number_required() -> ValidationError:
        guidance = "• For Continuation or Revision applications, you must provide the Grant Number in Field 5b (Federal Award Identifier).<br>• Find your Grant Number on your most recent Notice of Award or contact your Grants Management Specialist."
        return ValidationErrorFactory._create(
            "Grant Number is required for continuation applications.",
            "Grant Number missing for a continuation application.",
            field_name="Grant Number/Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            guidance=guidance,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_not_found(grant_number: str) -> ValidationError:
        guidance = "• Confirm the Grant Number is entered accurately by cross-referencing with the official grant documentation provided by the funding agency.<br>• Verify the Grant Number is currently active by using the grant search tool or database on the funding agency's portal."
        return ValidationErrorFactory._create(
            "Grant Number is not valid.",
            f"Grant lookup failed. Grant Number not found: {grant_number}.",
            field_name="Grant Number/Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            guidance=guidance,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_ownership_mismatch(grant_number: str, uei: str) -> ValidationError:
        guidance = "• Verify that the Grant Number entered matches the organization's UEI provided in Field 8b.<br>• If the Grant Number is correct but doesn't match the UEI, contact your Grants Management Specialist to confirm the organization associated with this grant."
        return ValidationErrorFactory._create(
            "Grant Number does not belong to the organization identified by the UEI provided.",
            f"Grant ownership mismatch. Grant Number: {grant_number}. UEI: {uei}.",
            field_name="Grant Number/Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            guidance=guidance,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_expired(grant_number: str) -> ValidationError:
        guidance = "• Confirm the Grant Number's project period has not ended by checking your Notice of Award or contacting your Grants Management Specialist.<br>• If the grant has expired, you may need to apply as a New application rather than a Continuation."
        return ValidationErrorFactory._create(
            "Grant Number is no longer active.",
            f"Grant is expired or inactive: {grant_number}.",
            field_name="Grant Number/Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            guidance=guidance,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_program_mismatch(grant_number: str, fon: str) -> ValidationError:
        guidance = "• Verify the Funding Opportunity Number in Field 1 matches the program associated with your Grant Number in Field 5b.<br>• If applying for a different funding opportunity, ensure you're using the correct continuation grant number or apply as a New application."
        return ValidationErrorFactory._create(
            "Grant Number does not match the selected funding opportunity.",
            f"Grant and funding opportunity do not match. Grant Number: {grant_number}. Funding Opportunity Number: {fon}.",
            field_name="Grant Number/Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            guidance=guidance,
            image_path="/static/images/fields/grant_number.png"
        )
    
    @staticmethod
    def ppop_address_invalid(site_type: str, address: str) -> ValidationError:
        guidance = "• Verify the address in the PPOP form is correct<br>• Check for typos in street number, street name, city, or ZIP code<br>• Ensure the address is a valid, deliverable location<br>• Confirm the address exists in USPS records"
        return ValidationErrorFactory._create(
            f"{site_type} address could not be validated.",
            f"PPOP {site_type} address validation failed (STD002 - Invalid): {address}. The address does not exist in USPS records or cannot be standardized.",
            field_name=f"PPOP {site_type} Address",
            page_number=1,
            field_location=f"PPOP Form - {site_type}",
            current_value=address,
            guidance=guidance
        )
    
    @staticmethod
    def ppop_address_ambiguous(site_type: str, address: str) -> ValidationError:
        guidance = "• Provide more specific address details (apartment/suite number, building name)<br>• Verify the ZIP code matches the city and state<br>• Check if additional address lines are needed<br>• Ensure the street name is complete and correct"
        return ValidationErrorFactory._create(
            f"{site_type} address matches multiple locations.",
            f"PPOP {site_type} address validation failed (STD003 - Ambiguous): {address}. Multiple locations match this address.",
            field_name=f"PPOP {site_type} Address",
            page_number=1,
            field_location=f"PPOP Form - {site_type}",
            current_value=address,
            guidance=guidance
        )
    
    @staticmethod
    def ppop_address_quality_failure(site_type: str, address: str, reason: str) -> ValidationError:
        guidance = "• Verify the complete street address including street number<br>• Ensure ZIP+4 code is correct<br>• Check that the address is a specific delivery point, not just a street name<br>• Confirm all address components are accurate"
        return ValidationErrorFactory._create(
            f"{site_type} address quality check failed.",
            f"PPOP {site_type} address validation failed quality requirements: {address}. Reason: {reason}",
            field_name=f"PPOP {site_type} Address",
            page_number=1,
            field_location=f"PPOP Form - {site_type}",
            current_value=address,
            guidance=guidance
        )
    
    @staticmethod
    def ppop_district_mismatch(site_type: str, form_district: str, hdw_district: str, address: str) -> ValidationError:
        # Format HDW district to XX-XXX format for user guidance
        hdw_formatted = ValidationErrorFactory._format_district_for_display(hdw_district)
        
        guidance = f"• Verify the congressional district in the form is correct<br>• The HDW API indicates this address is in district <strong>{hdw_formatted}</strong><br>• Update the congressional district field in the PDF to <strong>{hdw_formatted}</strong> (format: XX-XXX)<br>• If the district in the form is correct, verify the address is accurate"
        return ValidationErrorFactory._create(
            f"{site_type} congressional district mismatch.",
            f"PPOP {site_type} congressional district does not match HDW validation. Form shows: {form_district}, HDW shows: {hdw_formatted}. Address: {address}",
            field_name=f"PPOP {site_type} Congressional District",
            page_number=1,
            field_location=f"PPOP Form - {site_type}",
            current_value=form_district,
            guidance=guidance
        )
    
    @staticmethod
    def _format_district_for_display(district: str) -> str:
        """
        Format congressional district to XX-XXX format for display.
        Examples: VA10 → VA-010, CA5 → CA-005, VA-10 → VA-010
        """
        # Remove dashes and spaces, uppercase
        district_clean = district.upper().replace('-', '').replace(' ', '')
        
        # Extract state and district number
        match = re.match(r'^([A-Z]{2})(\d+)$', district_clean)
        if match:
            state = match.group(1)
            num = match.group(2).zfill(3)  # Pad to 3 digits with leading zeros
            return f"{state}-{num}"
        
        # Return as-is if format doesn't match
        return district
    
    @staticmethod
    def ppop_api_timeout(site_type: str) -> ValidationError:
        guidance = "⚠️ <strong>TEMPORARY ISSUE</strong><br>• The HDW API request timed out - this is a temporary network issue<br>• Please try uploading the form again in a few moments<br>• If the issue persists, contact support<br>• Your other validations are not affected"
        return ValidationErrorFactory._create(
            f"⚠️ {site_type} address validation timed out (temporary issue).",
            f"PPOP {site_type} address validation timed out. HDW API did not respond within the timeout period.",
            field_name=f"PPOP {site_type} Address",
            guidance=guidance
        )
    
    @staticmethod
    def ppop_api_error(site_type: str, error_msg: str) -> ValidationError:
        guidance = "⚠️ <strong>TEMPORARY ISSUE</strong><br>• The HDW API is currently unavailable - this is a temporary service issue<br>• Please try again in a few minutes<br>• If you need immediate assistance, contact support<br>• Your SF-424 validations can still proceed normally"
        return ValidationErrorFactory._create(
            f"⚠️ {site_type} address validation temporarily unavailable.",
            f"PPOP {site_type} address validation failed due to API error: {error_msg}",
            field_name=f"PPOP {site_type} Address",
            guidance=guidance
        )
    
    @staticmethod
    def ppop_api_disabled() -> ValidationError:
        guidance = "• PPOP address validation is currently disabled<br>• Contact your system administrator<br>• Check the HDW_API_ENABLED environment variable"
        return ValidationErrorFactory._create(
            "PPOP address validation is disabled.",
            "PPOP address validation is disabled in system configuration (HDW_API_ENABLED=false).",
            field_name="PPOP Validation",
            guidance=guidance
        )
