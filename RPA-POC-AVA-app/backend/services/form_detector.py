"""
Form Type Detection Service
Identifies which form type is being processed based on XFA field signatures
"""
from typing import Dict, Any, Optional
from enum import Enum

class FormType(Enum):
    """Supported form types"""
    SF424 = "SF-424"
    PERFORMANCE_SITE = "PerformanceSite_4_0"
    UNKNOWN = "UNKNOWN"

class FormDetector:
    """
    Detects form type by analyzing XFA field names.
    Each form has unique field signatures that can be used for identification.
    """
    
    # Signature fields that uniquely identify each form type
    # Supports both XFA (camelCase) and flattened PDF (snake_case) field names
    FORM_SIGNATURES = {
        FormType.SF424: [
            'ApplicationType',
            'application_type',  # Flattened PDF version
            'FundingOpportunityNumber',
            'funding_opportunity_number',  # Flattened PDF version
            'SAMUEI',
            'applicant_name',  # Flattened PDF version
            'OrganizationName'
        ],
        FormType.PERFORMANCE_SITE: [
            'CongressionalDistrictProgramProject',
            'congressional_district',  # Flattened PDF version
            'PrimarySite',
            'primary_site',  # Flattened PDF version
            'SiteLocation',
            'PerformanceSite'
        ]
    }
    
    # Minimum number of signature fields that must match
    MIN_MATCH_THRESHOLD = 2
    
    def detect_form_type(self, xfa_data: Dict[str, Any]) -> FormType:
        """
        Detect form type based on XFA field names.
        
        Args:
            xfa_data: Extracted XFA data from PDF (from XFAPdfExtractor)
            
        Returns:
            FormType enum indicating detected form
        """
        fields = xfa_data.get('fields', {})
        raw_fields = xfa_data.get('raw_fields', {})
        
        # Combine all available field names
        all_field_names = set(fields.keys()) | set(raw_fields.keys())
        
        print(f"[DEBUG] Detecting form type from {len(all_field_names)} fields")
        
        # Check each form signature
        best_match = FormType.UNKNOWN
        best_match_count = 0
        
        for form_type, signature_fields in self.FORM_SIGNATURES.items():
            match_count = self._count_signature_matches(all_field_names, signature_fields)
            
            print(f"[DEBUG] {form_type.value}: {match_count}/{len(signature_fields)} signature fields matched")
            
            if match_count >= self.MIN_MATCH_THRESHOLD and match_count > best_match_count:
                best_match = form_type
                best_match_count = match_count
        
        if best_match == FormType.UNKNOWN:
            print(f"[WARNING] Could not detect form type. Available fields: {list(all_field_names)[:10]}")
        else:
            print(f"[INFO] Detected form type: {best_match.value} ({best_match_count} matches)")
        
        return best_match
    
    def _count_signature_matches(self, field_names: set, signature_fields: list) -> int:
        """
        Count how many signature fields are present in the extracted fields.
        Uses fuzzy matching to handle field name variations.
        """
        match_count = 0
        
        for sig_field in signature_fields:
            # Check exact match first
            if sig_field in field_names:
                match_count += 1
                continue
            
            # Check case-insensitive partial match
            sig_lower = sig_field.lower()
            for field_name in field_names:
                if sig_lower in field_name.lower():
                    match_count += 1
                    break
        
        return match_count
    
    def get_form_metadata(self, form_type: FormType) -> Dict[str, Any]:
        """
        Get metadata about a form type.
        
        Returns:
            Dictionary with form information (name, version, description)
        """
        metadata = {
            FormType.SF424: {
                "name": "SF-424: Application for Federal Assistance",
                "version": "4.0",
                "description": "Standard form for applying for federal grants",
                "validator": "SF424Validator",
                "mapper": "SF424Mapper"
            },
            FormType.PERFORMANCE_SITE: {
                "name": "Performance Site Location Form",
                "version": "4.0",
                "description": "Performance site location information including primary and additional sites",
                "validator": "PerformanceSiteValidator",
                "mapper": "PerformanceSiteMapper"
            },
            FormType.UNKNOWN: {
                "name": "Unknown Form",
                "version": "N/A",
                "description": "Form type could not be determined",
                "validator": None,
                "mapper": None
            }
        }
        
        return metadata.get(form_type, metadata[FormType.UNKNOWN])
