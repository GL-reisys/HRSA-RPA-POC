from enum import Enum
from typing import Dict, Any

class FormType(Enum):
    """Supported form types"""
    SF424 = "SF-424"
    PPOP_FORM = "PPOP"
    UNKNOWN = "UNKNOWN"

class FormTypeDetector:
    """
    Detects form type from extracted PDF data.
    Supports SF-424 and PPOP (Project/Performance Site Location) forms.
    """
    
    def detect_form_type(self, extraction_result: Dict[str, Any]) -> FormType:
        """
        Detect form type based on PDF metadata and field patterns.
        
        Args:
            extraction_result: Result from XFAPdfExtractor.extract_form_fields()
            
        Returns:
            FormType enum (SF424, PPOP_FORM, or UNKNOWN)
        """
        metadata = extraction_result.get('metadata', {})
        raw_fields = extraction_result.get('raw_fields', {})
        
        # Check PDF title first (most reliable)
        pdf_title = raw_fields.get('_PDF_Title', '').lower()
        
        # PPOP Form Detection
        if 'project/performance site location' in pdf_title:
            return FormType.PPOP_FORM
        
        if self._has_ppop_field_pattern(raw_fields):
            return FormType.PPOP_FORM
        
        # SF-424 Form Detection
        if 'sf-424' in pdf_title or 'sf424' in pdf_title:
            return FormType.SF424
        
        # Check if already detected by XFA extractor
        detected_type = metadata.get('form_type', '').upper()
        if 'SF-424' in detected_type or 'SF424' in detected_type:
            return FormType.SF424
        
        # Check for SF-424 specific fields
        if self._has_sf424_field_pattern(raw_fields):
            return FormType.SF424
        
        # Unknown form type
        return FormType.UNKNOWN
    
    def _has_ppop_field_pattern(self, raw_fields: Dict[str, str]) -> bool:
        """
        Check if fields match PPOP form pattern.
        PPOP forms have fields like: PerformanceSite_4_0_PrimarySite_Address_*
        """
        ppop_indicators = [
            'performancesite',
            'primarysite_address',
            'othersite_address',
            'primarysite_organizationname',
            'congressionaldistrictprogramproject'
        ]
        
        field_names_lower = [f.lower() for f in raw_fields.keys()]
        
        # Check if at least 2 PPOP indicators are present
        matches = sum(1 for indicator in ppop_indicators 
                     if any(indicator in field for field in field_names_lower))
        
        return matches >= 2
    
    def _has_sf424_field_pattern(self, raw_fields: Dict[str, str]) -> bool:
        """
        Check if fields match SF-424 form pattern.
        SF-424 forms have fields like: SAMUEI, FundingOpportunityNumber, etc.
        """
        sf424_indicators = [
            'samuei',
            'fundingopp',
            'applicanttype',
            'federalawardidentifier',
            'employertaxpayer',
            'organizationname',
            'legalname'
        ]
        
        field_names_lower = [f.lower() for f in raw_fields.keys()]
        
        # Check if at least 3 SF-424 indicators are present
        matches = sum(1 for indicator in sf424_indicators 
                     if any(indicator in field for field in field_names_lower))
        
        return matches >= 3
