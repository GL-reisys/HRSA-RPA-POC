from dataclasses import dataclass


@dataclass
class ValidationError:
    user_message: str
    ai_context: str


class ValidationErrorFactory:
    @staticmethod
    def _create(user_message: str, ai_context: str) -> ValidationError:
        return ValidationError(user_message=user_message, ai_context=ai_context)

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
        return ValidationErrorFactory._create(
            "UEI was not found in the organization records.",
            f"UEI lookup failed. UEI not found: {uei}.",
        )

    @staticmethod
    def org_name_mismatch(submitted_name: str, expected_name: str, uei: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Organization Name does not match the name on file for the UEI provided.",
            f"Organization name mismatch for UEI {uei}. Submitted: {submitted_name}. Expected: {expected_name}.",
        )

    @staticmethod
    def fon_not_found(fon: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Funding Opportunity Number was not found.",
            f"Funding Opportunity Number not found: {fon}.",
        )

    @staticmethod
    def type_mismatch_continuation_required(fon: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "This funding opportunity only accepts continuation applications.",
            f"Application type mismatch for funding opportunity {fon}. Continuation is required.",
        )

    @staticmethod
    def type_mismatch_new_required(fon: str, application_type: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "This funding opportunity only accepts new applications.",
            f"Application type mismatch for funding opportunity {fon}. Received {application_type}; new application required.",
        )

    @staticmethod
    def grant_number_not_allowed(fon: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number should not be provided for this funding opportunity.",
            f"Grant Number was provided for funding opportunity {fon}, which only accepts new applications.",
        )

    @staticmethod
    def duplicate_application(fon: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "An application for this funding opportunity already exists for this organization.",
            f"Duplicate application detected for funding opportunity {fon}.",
        )

    @staticmethod
    def grant_number_required() -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number is required for continuation applications.",
            "Grant Number missing for a continuation application.",
        )

    @staticmethod
    def grant_not_found(grant_number: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number was not found.",
            f"Grant lookup failed. Grant Number not found: {grant_number}.",
        )

    @staticmethod
    def grant_ownership_mismatch(grant_number: str, uei: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number does not belong to the organization identified by the UEI provided.",
            f"Grant ownership mismatch. Grant Number: {grant_number}. UEI: {uei}.",
        )

    @staticmethod
    def grant_expired(grant_number: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number is no longer active.",
            f"Grant is expired or inactive: {grant_number}.",
        )

    @staticmethod
    def grant_program_mismatch(grant_number: str, fon: str) -> ValidationError:
        return ValidationErrorFactory._create(
            "Grant Number does not match the selected funding opportunity.",
            f"Grant and funding opportunity do not match. Grant Number: {grant_number}. Funding Opportunity Number: {fon}.",
        )
