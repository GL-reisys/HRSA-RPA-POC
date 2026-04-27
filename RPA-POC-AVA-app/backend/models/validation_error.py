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
        return ValidationErrorFactory._create(
            "Grant Number should not be provided for this funding opportunity.",
            f"Grant Number was provided for funding opportunity {fon}, which only accepts new applications.",
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
        return ValidationErrorFactory._create(
            "Grant Number is required for continuation applications.",
            "Grant Number missing for a continuation application.",
            field_name="Federal Award Identifier",
            page_number=1,
            field_location="Page 1, Field 5b",
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_not_found(grant_number: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number is not valid.",
            f"Grant lookup failed. Grant Number not found: {grant_number}.",
            field_name="Grant Number",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_ownership_mismatch(grant_number: str, uei: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number does not belong to the organization identified by the UEI provided.",
            f"Grant ownership mismatch. Grant Number: {grant_number}. UEI: {uei}.",
            field_name="Grant Number",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_expired(grant_number: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number is no longer active.",
            f"Grant is expired or inactive: {grant_number}.",
            field_name="Grant Number",
            page_number=1,
            field_location="Page 1, Field 5b",
            current_value=grant_number,
            image_path="/static/images/fields/grant_number.png"
        )

    @staticmethod
    def grant_program_mismatch(grant_number: str, fon: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number does not match the selected funding opportunity.",
            f"Grant and funding opportunity do not match. Grant Number: {grant_number}. Funding Opportunity Number: {fon}.",
        )
