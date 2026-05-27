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
        
        # DEBUG: Log all field names
        print(f"DEBUG PPOP MAPPER: Received {len(raw_fields)} fields")
        print(f"DEBUG PPOP MAPPER: All field names: {list(raw_fields.keys())}")
        if raw_fields:
            print(f"DEBUG PPOP MAPPER: Sample field values:")
            for key in list(raw_fields.keys())[:10]:
                print(f"  - {key}: {raw_fields[key]}")
        
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
        
        Handles both:
        - XFA format: datasets_data_GrantApplicationWrapper_GrantApplication_Forms_PerformanceSite_4_0_{site_type}_*
        - Flattened format with prefix: {site_type_lower}_{field}
        - Flattened format without prefix: just {field} (e.g., 'city', 'state')
        """
        # Find fields matching the site type (case-insensitive for flattened PDFs)
        site_type_lower = site_type.lower().replace('site', '_site')  # "PrimarySite" -> "primary_site"
        site_fields = {
            key: value for key, value in raw_fields.items()
            if site_type in key or site_type_lower in key.lower()
        }
        
        print(f"DEBUG: Extracting {site_type} address from {len(site_fields)} site-specific fields")
        print(f"DEBUG: Site-specific fields: {list(site_fields.keys())}")
        
        # If no site-specific fields found, use all fields (for simple flattened PDFs)
        if not site_fields:
            print(f"DEBUG: No site-specific fields found, using all {len(raw_fields)} fields")
            site_fields = raw_fields
        
        # Extract organization info
        # XFA: 'OrganizationName', Flattened: 'organization_name' or 'org_name'
        org_name = self._find_field_value(site_fields, ['OrganizationName', 'organization_name', 'org_name'])
        uei = self._find_field_value(site_fields, ['SAMUEI', 'uei', 'samuei'])
        
        # Extract address fields
        # XFA: 'Address_Street1', Flattened: 'Street1', 'street', 'street1', 'address_street1'
        street = self._find_field_value(site_fields, ['Address_Street1', 'Street1', 'street', 'street1', 'address_street1', 'address_street'])
        city = self._find_field_value(site_fields, ['Address_City', 'City', 'city', 'address_city'])
        state_raw = self._find_field_value(site_fields, ['Address_State', 'State', 'state', 'address_state'])
        # Handle 'ZIP / Postal Code' (with spaces and slash), 'ZIP/PostalCode', 'ZIPPostalCode', etc.
        zip_raw = self._find_field_value(site_fields, ['Address_ZipPostalCode', 'ZIP / Postal Code', 'ZIP/Postal Code', 'ZIPPostalCode', 'ZIP/PostalCode', 'zip', 'zip_code', 'zippostalcode', 'postal_code', 'zipcode', 'postalcode'])
        country = self._find_field_value(site_fields, ['Address_Country', 'Country', 'country', 'address_country'])
        district = self._find_field_value(site_fields, ['CongressionalDistrictProgramProject', 'congressional_district', 'district'])
        
        print(f"DEBUG: Extracted fields for {site_type}:")
        print(f"  - street: {street}")
        print(f"  - city: {city}")
        print(f"  - state_raw: {state_raw}")
        print(f"  - zip_raw: {zip_raw}")
        print(f"  - district: {district}")
        
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
    
    def _find_field_value(self, fields: Dict[str, str], field_suffixes) -> Optional[str]:
        """
        Find field value by suffix(es).
        Accepts either a single string or list of strings to search for.
        
        Args:
            fields: Dictionary of field names to values
            field_suffixes: Single string or list of strings to search for in field names
            
        Returns:
            First matching non-empty value, or None
        """
        # Convert to list if single string provided
        if isinstance(field_suffixes, str):
            field_suffixes = [field_suffixes]
        
        # Try each suffix pattern
        for suffix in field_suffixes:
            for key, value in fields.items():
                # Case-insensitive search for field name
                if suffix.lower() in key.lower():
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
