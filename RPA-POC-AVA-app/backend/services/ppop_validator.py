import os
import re
import logging
import requests
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from services.ppop_field_mapper import PPOPAddress, PPOPFormData
from models.validation_error import ValidationError, ValidationErrorFactory

logger = logging.getLogger(__name__)

class HDWValidationStatus(Enum):
    """HDW API validation status codes"""
    EXACT_MATCH = "STD000"
    APPROXIMATED_MATCH = "STD001"
    INVALID = "STD002"
    AMBIGUOUS = "STD003"

@dataclass
class HDWValidationResult:
    """Result from HDW API validation"""
    is_valid: bool
    status_code: str
    status_description: str
    standardized_street: Optional[str] = None
    standardized_city: Optional[str] = None
    standardized_state: Optional[str] = None
    standardized_zip5: Optional[str] = None
    standardized_zip4: Optional[str] = None
    county: Optional[str] = None
    county_fips: Optional[str] = None
    congressional_district: Optional[str] = None
    match_score: Optional[float] = None
    match_level: Optional[str] = None
    error_message: Optional[str] = None

class PPOPValidator:
    """
    Validates PPOP addresses using HRSA Data Warehouse (HDW) API.
    Implements validation rules from PPOP_Validation_Implementation_Guide.md
    """
    
    def __init__(self):
        self.api_url = os.getenv('HDW_API_URL', 'https://data.hrsa.gov/HDWAPI3_External/api/Location/GetLocationInfoByAddress')
        self.api_token = os.getenv('HDW_API_TOKEN', '')
        self.api_timeout = int(os.getenv('HDW_API_TIMEOUT', '30'))
        self.api_enabled = os.getenv('HDW_API_ENABLED', 'true').lower() == 'true'
        
        # Validate API configuration
        if self.api_enabled and not self.api_token:
            logger.warning("HDW_API_ENABLED is true but HDW_API_TOKEN is not set. PPOP validation will fail.")
        
        # Validation settings
        self.accept_approximated = os.getenv('PPOP_ACCEPT_APPROXIMATED_MATCH', 'true').lower() == 'true'
        self.minimum_score = float(os.getenv('PPOP_MINIMUM_MATCH_SCORE', '95.0'))
        self.require_zip4 = os.getenv('PPOP_REQUIRE_ZIP4', 'true').lower() == 'true'
        self.require_street_number = os.getenv('PPOP_REQUIRE_STREET_NUMBER', 'true').lower() == 'true'
    
    def validate_ppop_form(self, ppop_data: PPOPFormData) -> List[ValidationError]:
        """
        Validate all addresses in PPOP form.
        
        Args:
            ppop_data: PPOPFormData with Primary and optional Other Site
            
        Returns:
            List of ValidationError objects
        """
        errors = []
        
        # Check if HDW API is enabled
        if not self.api_enabled:
            errors.append(ValidationErrorFactory.ppop_api_disabled())
            return errors
        
        # Validate only Primary Site address (skip Other Site per requirements)
        if ppop_data.primary_site:
            address_errors = self._validate_address(ppop_data.primary_site)
            errors.extend(address_errors)
        
        return errors
    
    def _validate_address(self, address: PPOPAddress) -> List[ValidationError]:
        """Validate a single PPOP address"""
        errors = []
        
        # Check required fields
        if not address.street:
            errors.append(ValidationErrorFactory.ppop_required_field(
                f"{address.site_type} Street Address", 
                f"PPOP_{address.site_type.replace(' ', '_').upper()}_STREET"
            ))
        
        if not address.city:
            errors.append(ValidationErrorFactory.ppop_required_field(
                f"{address.site_type} City", 
                f"PPOP_{address.site_type.replace(' ', '_').upper()}_CITY"
            ))
        
        if not address.state_code:
            errors.append(ValidationErrorFactory.ppop_required_field(
                f"{address.site_type} State", 
                f"PPOP_{address.site_type.replace(' ', '_').upper()}_STATE"
            ))
        
        if not address.zip5:
            errors.append(ValidationErrorFactory.ppop_required_field(
                f"{address.site_type} ZIP Code", 
                f"PPOP_{address.site_type.replace(' ', '_').upper()}_ZIP"
            ))
        
        # Validate congressional district format if provided
        if address.congressional_district:
            district_error = self._validate_district_format(address.congressional_district, address.site_type)
            if district_error:
                errors.append(district_error)
        
        # If required fields missing, skip API validation
        if errors:
            return errors
        
        # Call HDW API
        try:
            hdw_result = self._call_hdw_api(address)
            
            # Check validation result
            if not hdw_result.is_valid:
                errors.append(self._create_validation_error(address, hdw_result))
            else:
                # Check congressional district match (if provided in form)
                if address.congressional_district and hdw_result.congressional_district:
                    if not self._districts_match(address.congressional_district, hdw_result.congressional_district):
                        errors.append(ValidationErrorFactory.ppop_district_mismatch(
                            address.site_type,
                            address.congressional_district,
                            hdw_result.congressional_district,
                            f"{address.street}, {address.city}, {address.state_code} {address.zip5}"
                        ))
        
        except requests.exceptions.Timeout:
            errors.append(ValidationErrorFactory.ppop_api_timeout(address.site_type))
        except requests.exceptions.RequestException as e:
            errors.append(ValidationErrorFactory.ppop_api_error(address.site_type, str(e)))
        except Exception as e:
            errors.append(ValidationErrorFactory.ppop_api_error(address.site_type, str(e)))
        
        return errors
    
    def _call_hdw_api(self, address: PPOPAddress) -> HDWValidationResult:
        """
        Call HDW API to validate address.
        
        API Request Format:
        {
            "InputAddresses": [{
                "inputAddress": "45335 Vintage Park Plaza",
                "inputCity": "Sterling",
                "inputState": "VA",
                "inputZip": "20166",
                "inputTieBreaker": "True"
            }],
            "Targets": "CONGDIST,COUNTY",
            "token": "API_TOKEN"
        }
        """
        logger.info(f"Calling HDW API for {address.site_type} address: {address.street}, {address.city}, {address.state_code}")
        
        payload = {
            "InputAddresses": [{
                "inputAddress": address.street,
                "inputCity": address.city,
                "inputState": address.state_code,
                "inputZip": address.zip5,
                "inputTieBreaker": "True"
            }],
            "Targets": "CONGDIST,COUNTY",
            "token": self.api_token
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.api_timeout
            )
            logger.info(f"HDW API response status: {response.status_code}")
            response.raise_for_status()
            
            return self._parse_hdw_response(response.json())
        except requests.exceptions.Timeout:
            logger.warning(f"HDW API timeout after {self.api_timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"HDW API error: {str(e)}")
            raise
    
    def _parse_hdw_response(self, api_response: Dict[str, Any]) -> HDWValidationResult:
        """Parse HDW API response and apply validation rules"""
        
        if not api_response.get('Addresses'):
            return HDWValidationResult(
                is_valid=False,
                status_code="ERROR",
                status_description="No address data in API response",
                error_message="HDW API returned no address data"
            )
        
        address_data = api_response['Addresses'][0]
        code = address_data.get('code', '')
        description = address_data.get('description', '')
        
        # Extract standardized address
        std_street = address_data.get('street', '')
        std_city = address_data.get('city', '')
        std_state = address_data.get('state', '')
        std_zip5 = address_data.get('zip5Code', '')
        std_zip4 = address_data.get('zip4Code', '')
        street_number = address_data.get('StreetNumber', '')
        score = address_data.get('score', 0.0)
        
        # Extract geographic data
        county = None
        county_fips = None
        cong_district = None
        
        targets = address_data.get('Targets', [])
        for target in targets:
            if target.get('Target') == 'COUNTY' and target.get('Preferred'):
                county_data = target['Preferred'][0]
                county = county_data.get('County Name')
                county_fips = county_data.get('State County FIPS Code')
            elif target.get('Target') == 'CONGDIST' and target.get('Preferred'):
                district_data = target['Preferred'][0]
                raw_district = district_data.get('Congressional District Code')
                # Format to XX-XXX (e.g., CA48 → CA-048)
                if raw_district:
                    from models.validation_error import ValidationErrorFactory
                    cong_district = ValidationErrorFactory._format_district_for_display(raw_district)
                else:
                    cong_district = raw_district
        
        # Extract match level
        match_level = ''
        locations = address_data.get('Locations', [])
        if locations:
            match_level = locations[0].get('matchLevel', '')
        
        # Validate based on status code
        is_valid = False
        
        if code == HDWValidationStatus.EXACT_MATCH.value:
            # STD000 - Exact Match
            is_valid = True
        
        elif code == HDWValidationStatus.APPROXIMATED_MATCH.value:
            # STD001 - Approximated Match
            is_valid = self.accept_approximated
        
        elif code == HDWValidationStatus.INVALID.value:
            # STD002 - Invalid
            is_valid = False
        
        elif code == HDWValidationStatus.AMBIGUOUS.value:
            # STD003 - Ambiguous
            is_valid = False
        
        # For PPOP validation, we only care if HDW can match the address
        # Quality checks are informational only - we accept STD000 and STD001
        logger.info(f"HDW validation result: code={code}, description={description}, score={score}, match_level={match_level}")
        
        return HDWValidationResult(
            is_valid=is_valid,
            status_code=code,
            status_description=description,
            standardized_street=std_street,
            standardized_city=std_city,
            standardized_state=std_state,
            standardized_zip5=std_zip5,
            standardized_zip4=std_zip4,
            county=county,
            county_fips=county_fips,
            congressional_district=cong_district,
            match_score=score,
            match_level=match_level,
            error_message=None if is_valid else description
        )
    
    def _create_validation_error(self, address: PPOPAddress, hdw_result: HDWValidationResult) -> ValidationError:
        """Create appropriate ValidationError based on HDW result"""
        
        address_str = f"{address.street}, {address.city}, {address.state_code} {address.zip5}"
        
        if hdw_result.status_code == HDWValidationStatus.INVALID.value:
            return ValidationErrorFactory.ppop_address_invalid(address.site_type, address_str)
        
        elif hdw_result.status_code == HDWValidationStatus.AMBIGUOUS.value:
            return ValidationErrorFactory.ppop_address_ambiguous(address.site_type, address_str)
        
        else:
            # Quality check failure
            return ValidationErrorFactory.ppop_address_quality_failure(
                address.site_type, 
                address_str,
                hdw_result.error_message or "Address quality checks failed"
            )
    
    def _validate_district_format(self, district: str, site_type: str) -> Optional[ValidationError]:
        """
        Validate congressional district format.
        Valid formats:
        - 2 character State + 3 character District: CA-005, CA005
        - Special cases: "all" for all districts in state, "00-00" for outside US
        
        Examples: CA-005, CA-012, VA-010, all, 00-00
        """
        district_clean = district.strip().upper()
        
        # Special cases
        if district_clean == "ALL" or district_clean == "00-00":
            return None
        
        # Standard format: 2-letter state + optional dash + 3-digit district
        # Examples: CA-005, VA-010, CA005, VA010
        pattern = r'^[A-Z]{2}-?\d{3}$'
        
        if not re.match(pattern, district_clean):
            from models.validation_error import ValidationErrorFactory
            guidance = "• Enter the Congressional District in the format: 2 character State Abbreviation - 3 character District Number<br>• Examples: CA-005 for California's 5th District, CA-012 for California's 12th District<br>• If all districts in a state are affected, enter 'all' for the District number<br>• If the Program/Project is outside the U.S., enter 00-00"
            return ValidationErrorFactory._create(
                f"Invalid {site_type} Congressional District format.",
                f"PPOP {site_type} Congressional District '{district}' is not in the correct format. Expected format: XX-XXX (e.g., CA-005, VA-010)",
                field_name=f"PPOP {site_type} Congressional District",
                page_number=1,
                field_location=f"PPOP Form - {site_type}",
                current_value=district,
                guidance=guidance
            )
        
        return None
    
    def _districts_match(self, form_district: str, hdw_district: str) -> bool:
        """
        Compare congressional districts (case-insensitive, flexible format).
        PDF format: XX-XXX (e.g., VA-010)
        HDW format: XXXX (e.g., VA10)
        
        Examples: 
        - "VA-010" == "VA10" → True
        - "CA-005" == "CA5" → True
        - "VA-010" == "VA010" → True
        """
        # Normalize: remove dashes and spaces, uppercase
        form_clean = form_district.upper().replace('-', '').replace(' ', '')
        hdw_clean = hdw_district.upper().replace('-', '').replace(' ', '')
        
        # Extract state and district number from both
        # Form format: VA010 or VA10
        # HDW format: VA10 or VA010
        form_match = re.match(r'^([A-Z]{2})(\d+)$', form_clean)
        hdw_match = re.match(r'^([A-Z]{2})(\d+)$', hdw_clean)
        
        if not form_match or not hdw_match:
            # Fallback to direct comparison
            return form_clean == hdw_clean
        
        form_state = form_match.group(1)
        form_num = int(form_match.group(2))  # Convert to int to ignore leading zeros
        
        hdw_state = hdw_match.group(1)
        hdw_num = int(hdw_match.group(2))  # Convert to int to ignore leading zeros
        
        # Compare state and district number
        return form_state == hdw_state and form_num == hdw_num
