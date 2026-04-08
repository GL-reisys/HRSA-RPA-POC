from typing import Dict, Any, Optional
from datetime import datetime

class FormMapper:
    """
    Maps extracted XFA fields to SF424FormData model.
    Based on C# SF424FormMapper.cs
    """
    
    # Multiple possible prefixes for different PDF versions
    SF424_FIELD_PREFIXES = [
        "datasets_data_GrantApplicationWrapper_GrantApplication_Forms_SF424_4_0_",
        "form1_Page1_",
        ""  # No prefix fallback
    ]
    
    def map_to_sf424(self, xfa_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map XFA form data to SF424 structure.
        
        Args:
            xfa_data: Result from XFAPdfExtractor.extract_form_fields()
            
        Returns:
            Dictionary matching SF424FormData structure
        """
        fields = xfa_data.get('fields', {})
        raw_fields = xfa_data.get('raw_fields', {})
        
        sf424 = {}
        
        # Application Information
        sf424['submission_type'] = self._get_string_value(fields, raw_fields, 'SubmissionType')
        sf424['application_type'] = self._get_string_value(fields, raw_fields, 'ApplicationType')
        sf424['revision_type'] = self._get_string_value(fields, raw_fields, 'RevisionType')
        sf424['revision_other_specify'] = self._get_string_value(fields, raw_fields, 'RevisionOtherSpecify')
        sf424['date_received'] = self._get_date_value(fields, raw_fields, 'DateReceived')
        sf424['applicant_id'] = self._get_string_value(fields, raw_fields, 'ApplicantID')
        sf424['federal_entity_identifier'] = self._get_string_value(fields, raw_fields, 'FederalEntityIdentifier')
        sf424['federal_award_identifier'] = self._get_string_value(fields, raw_fields, 'FederalAwardIdentifier')
        sf424['state_receive_date'] = self._get_date_value(fields, raw_fields, 'StateReceiveDate')
        sf424['state_application_id'] = self._get_string_value(fields, raw_fields, 'StateApplicationID')
        
        # Applicant Information
        sf424['organization_name'] = self._get_string_value(fields, raw_fields, 'OrganizationName')
        sf424['employer_taxpayer_identification_number'] = self._get_string_value(fields, raw_fields, 'EmployerTaxpayerIdentificationNumber')
        sf424['samuei'] = self._get_string_value(fields, raw_fields, 'SAMUEI')
        
        # Applicant Address
        sf424['applicant_street1'] = self._get_string_value(fields, raw_fields, 'Applicant_Street1')
        sf424['applicant_street2'] = self._get_string_value(fields, raw_fields, 'Applicant_Street2')
        sf424['applicant_city'] = self._get_string_value(fields, raw_fields, 'Applicant_City')
        sf424['applicant_state'] = self._get_string_value(fields, raw_fields, 'Applicant_State')
        sf424['applicant_zip_postal_code'] = self._get_string_value(fields, raw_fields, 'Applicant_ZipPostalCode')
        sf424['applicant_country'] = self._get_string_value(fields, raw_fields, 'Applicant_Country')
        
        # Contact Information
        sf424['department_name'] = self._get_string_value(fields, raw_fields, 'DepartmentName')
        sf424['division_name'] = self._get_string_value(fields, raw_fields, 'DivisionName')
        sf424['contact_person_first_name'] = self._get_string_value(fields, raw_fields, 'ContactPerson_FirstName')
        sf424['contact_person_last_name'] = self._get_string_value(fields, raw_fields, 'ContactPerson_LastName')
        sf424['title'] = self._get_string_value(fields, raw_fields, 'Title')
        sf424['organization_affiliation'] = self._get_string_value(fields, raw_fields, 'OrganizationAffiliation')
        sf424['phone_number'] = self._get_string_value(fields, raw_fields, 'PhoneNumber')
        sf424['fax'] = self._get_string_value(fields, raw_fields, 'Fax')
        sf424['email'] = self._get_string_value(fields, raw_fields, 'Email')
        
        # Applicant Type
        sf424['applicant_type_code1'] = self._get_string_value(fields, raw_fields, 'ApplicantTypeCode1')
        sf424['applicant_type_code2'] = self._get_string_value(fields, raw_fields, 'ApplicantTypeCode2')
        sf424['applicant_type_code3'] = self._get_string_value(fields, raw_fields, 'ApplicantTypeCode3')
        sf424['applicant_type_other_specify'] = self._get_string_value(fields, raw_fields, 'ApplicantTypeOtherSpecify')
        
        # Federal Agency and Program
        sf424['agency_name'] = self._get_string_value(fields, raw_fields, 'AgencyName')
        sf424['cfda_number'] = self._get_string_value(fields, raw_fields, 'CFDANumber')
        sf424['cfda_program_title'] = self._get_string_value(fields, raw_fields, 'CFDAProgramTitle')
        sf424['funding_opportunity_number'] = self._get_string_value(fields, raw_fields, 'FundingOpportunityNumber')
        sf424['funding_opportunity_title'] = self._get_string_value(fields, raw_fields, 'FundingOpportunityTitle')
        sf424['competition_identification_number'] = self._get_string_value(fields, raw_fields, 'CompetitionIdentificationNumber')
        sf424['competition_identification_title'] = self._get_string_value(fields, raw_fields, 'CompetitionIdentificationTitle')
        
        # Project Information
        sf424['project_title'] = self._get_string_value(fields, raw_fields, 'ProjectTitle')
        sf424['congressional_district_applicant'] = self._get_string_value(fields, raw_fields, 'CongressionalDistrictApplicant')
        sf424['congressional_district_program_project'] = self._get_string_value(fields, raw_fields, 'CongressionalDistrictProgramProject')
        sf424['project_start_date'] = self._get_date_value(fields, raw_fields, 'ProjectStartDate')
        sf424['project_end_date'] = self._get_date_value(fields, raw_fields, 'ProjectEndDate')
        
        # Budget Information
        sf424['federal_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'FederalEstimatedFunding')
        sf424['applicant_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'ApplicantEstimatedFunding')
        sf424['state_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'StateEstimatedFunding')
        sf424['local_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'LocalEstimatedFunding')
        sf424['other_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'OtherEstimatedFunding')
        sf424['program_income_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'ProgramIncomeEstimatedFunding')
        sf424['total_estimated_funding'] = self._get_decimal_value(fields, raw_fields, 'TotalEstimatedFunding')
        
        # State Review and Certification
        sf424['state_review'] = self._get_string_value(fields, raw_fields, 'StateReview')
        sf424['state_review_available_date'] = self._get_date_value(fields, raw_fields, 'StateReviewAvailableDate')
        sf424['delinquent_federal_debt'] = self._get_string_value(fields, raw_fields, 'DelinquentFederalDebt')
        sf424['certification_agree'] = self._get_string_value(fields, raw_fields, 'CertificationAgree')
        
        # Authorized Representative
        sf424['authorized_representative_first_name'] = self._get_string_value(fields, raw_fields, 'AuthorizedRepresentative_FirstName')
        sf424['authorized_representative_last_name'] = self._get_string_value(fields, raw_fields, 'AuthorizedRepresentative_LastName')
        sf424['authorized_representative_title'] = self._get_string_value(fields, raw_fields, 'AuthorizedRepresentativeTitle')
        sf424['authorized_representative_phone_number'] = self._get_string_value(fields, raw_fields, 'AuthorizedRepresentativePhoneNumber')
        sf424['authorized_representative_email'] = self._get_string_value(fields, raw_fields, 'AuthorizedRepresentativeEmail')
        sf424['authorized_representative_fax'] = self._get_string_value(fields, raw_fields, 'AuthorizedRepresentativeFax')
        sf424['aor_signature'] = self._get_string_value(fields, raw_fields, 'AORSignature')
        sf424['date_signed'] = self._get_date_value(fields, raw_fields, 'DateSigned')
        
        return sf424
    
    def _get_string_value(self, fields: Dict, raw_fields: Dict, field_name: str) -> Optional[str]:
        """Get string value from fields with multiple possible field name variants"""
        # Try with all known prefixes
        for prefix in self.SF424_FIELD_PREFIXES:
            full_field_name = prefix + field_name
            value = fields.get(full_field_name) or raw_fields.get(full_field_name)
            if value is not None:
                return str(value)
        
        # Try fuzzy match as fallback
        for key in fields.keys():
            if field_name.lower() in key.lower():
                value = fields.get(key) or raw_fields.get(key)
                if value is not None:
                    return str(value)
        
        return None
    
    def _get_date_value(self, fields: Dict, raw_fields: Dict, field_name: str) -> Optional[str]:
        """Get date value as ISO string"""
        value = self._get_string_value(fields, raw_fields, field_name)
        if not value:
            return None
        
        try:
            if isinstance(value, datetime):
                return value.isoformat()
            dt = datetime.fromisoformat(str(value))
            return dt.isoformat()
        except:
            return None
    
    def _get_decimal_value(self, fields: Dict, raw_fields: Dict, field_name: str) -> Optional[float]:
        """Get decimal/numeric value"""
        # Try with all known prefixes
        for prefix in self.SF424_FIELD_PREFIXES:
            full_field_name = prefix + field_name
            value = fields.get(full_field_name) or raw_fields.get(full_field_name)
            if value is not None:
                break
        
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
        
        try:
            return float(str(value).replace(',', '').replace('$', ''))
        except:
            return None
