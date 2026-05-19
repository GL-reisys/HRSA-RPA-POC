from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re

@dataclass
class PPOPAddress:
    """PPOP Address data structure"""
    site_type: str  # "Primary" or "Other"
    organization_name: Optional[str] = None
    uei: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    zip_code: Optional[str] = None
    zip5: Optional[str] = None
    zip4: Optional[str] = None
    country: Optional[str] = None
    congressional_district: Optional[str] = None
    
    def is_complete(self) -> bool:
        """Check if address has all required fields for validation"""
        return all([self.street, self.city, self.state_code, self.zip5])

@dataclass
class PPOPFormData:
    """Complete PPOP form data"""
    primary_site: PPOPAddress
    other_site: Optional[PPOPAddress] = None
    
    def get_all_addresses(self) -> List[PPOPAddress]:
        """Get all addresses that need validation"""
        addresses = [self.primary_site]
        if self.other_site and self.other_site.is_complete():
            addresses.append(self.other_site)
        return addresses

class PPOPFieldMapper:
    """
    Maps XFA fields from PPOP form to structured data.
    Handles both Primary Site and Other Site addresses.
    """
    
    def map_to_ppop(self, xfa_data: Dict[str, Any]) -> PPOPFormData:
        """
        Map XFA data to PPOP form structure.
        
        Args:
            xfa_data: Result from XFAPdfExtractor.extract_form_fields()
            
        Returns:
            PPOPFormData with Primary and Other Site addresses
        """
        raw_fields = xfa_data.get('raw_fields', {})
        
        # Extract Primary Site
        primary_site = self._extract_site_address(raw_fields, 'PrimarySite')
        
        # Extract Other Site (optional)
        other_site = self._extract_site_address(raw_fields, 'OtherSite')
        
        return PPOPFormData(
            primary_site=primary_site,
            other_site=other_site if other_site and other_site.is_complete() else None
        )
    
    def _extract_site_address(self, raw_fields: Dict[str, str], site_type: str) -> PPOPAddress:
        """
        Extract address data for a specific site (Primary or Other).
        
        Field pattern: datasets_data_GrantApplicationWrapper_GrantApplication_Forms_PerformanceSite_4_0_{site_type}_*
        """
        # Find fields matching the site type
        site_fields = {
            key: value for key, value in raw_fields.items()
            if site_type in key
        }
        
        # Extract organization info
        org_name = self._find_field_value(site_fields, 'OrganizationName')
        uei = self._find_field_value(site_fields, 'SAMUEI')
        
        # Extract address fields
        street = self._find_field_value(site_fields, 'Address_Street1')
        city = self._find_field_value(site_fields, 'Address_City')
        state_raw = self._find_field_value(site_fields, 'Address_State')
        zip_raw = self._find_field_value(site_fields, 'Address_ZipPostalCode')
        country = self._find_field_value(site_fields, 'Address_Country')
        district = self._find_field_value(site_fields, 'CongressionalDistrictProgramProject')
        
        # Parse state (format: "VA: Virginia" -> "VA")
        state_code = self._parse_state_code(state_raw)
        
        # Parse ZIP code (format: "20166-6748" -> zip5="20166", zip4="6748")
        zip5, zip4 = self._parse_zip_code(zip_raw)
        
        return PPOPAddress(
            site_type=site_type.replace('Site', ' Site'),  # "PrimarySite" -> "Primary Site"
            organization_name=org_name,
            uei=uei,
            street=street,
            city=city,
            state=state_raw,
            state_code=state_code,
            zip_code=zip_raw,
            zip5=zip5,
            zip4=zip4,
            country=country,
            congressional_district=district
        )
    
    def _find_field_value(self, fields: Dict[str, str], field_suffix: str) -> Optional[str]:
        """Find field value by suffix (e.g., 'Address_City')"""
        for key, value in fields.items():
            if field_suffix in key:
                return value.strip() if value else None
        return None
    
    def _parse_state_code(self, state_raw: Optional[str]) -> Optional[str]:
        """
        Parse state code from format "VA: Virginia" -> "VA"
        """
        if not state_raw:
            return None
        
        # Split by colon and take first part
        if ':' in state_raw:
            return state_raw.split(':')[0].strip()
        
        # If already just the code (2 letters)
        if len(state_raw.strip()) == 2:
            return state_raw.strip().upper()
        
        return state_raw.strip()
    
    def _parse_zip_code(self, zip_raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """
        Parse ZIP code from format "20166-6748" -> ("20166", "6748")
        """
        if not zip_raw:
            return None, None
        
        zip_clean = zip_raw.strip()
        
        # Check for ZIP+4 format
        if '-' in zip_clean:
            parts = zip_clean.split('-')
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None
        
        # Just ZIP5
        if len(zip_clean) >= 5:
            return zip_clean[:5], None
        
        return zip_clean, None
