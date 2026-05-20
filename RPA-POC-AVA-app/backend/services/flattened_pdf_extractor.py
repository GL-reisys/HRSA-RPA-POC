"""
Flattened PDF Extractor
Extracts SF-424 and PPOP fields from flattened PDFs using text parsing
NO Azure AI needed - FREE solution
"""
import pdfplumber
import re
from typing import Dict, Any, List

class FlattenedPdfExtractor:
    """Extract form fields from flattened PDFs using text parsing"""
    
    def extract_form_fields(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract fields from flattened PDF
        
        Returns same structure as XFAPdfExtractor for compatibility
        """
        result = {
            'raw_fields': {},
            'fields': {},
            'metadata': {
                'extraction_method': 'text_parsing',
                'page_count': 0,
                'field_count': 0,
                'form_type': 'Unknown',
                'forms_found': []
            }
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                result['metadata']['page_count'] = len(pdf.pages)
                
                # Extract text from all pages
                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
                
                lines = all_text.split('\n')
                
                # Detect which forms are present
                has_sf424 = self._detect_sf424(all_text)
                has_ppop = self._detect_ppop(all_text)
                
                if has_sf424:
                    result['metadata']['forms_found'].append('SF-424')
                    sf424_fields = self._extract_sf424_fields(lines, all_text)
                    result['fields'].update(sf424_fields)
                    result['raw_fields'].update(sf424_fields)
                
                if has_ppop:
                    result['metadata']['forms_found'].append('PPOP')
                    ppop_fields = self._extract_ppop_fields(lines, all_text)
                    result['fields'].update(ppop_fields)
                    result['raw_fields'].update(ppop_fields)
                
                # Set form type based on what was found
                if has_sf424 and has_ppop:
                    result['metadata']['form_type'] = 'Multi-Form'
                elif has_sf424:
                    result['metadata']['form_type'] = 'SF-424'
                elif has_ppop:
                    result['metadata']['form_type'] = 'PPOP'
                
                result['metadata']['field_count'] = len(result['fields'])
                
        except Exception as e:
            print(f"Error extracting flattened PDF: {str(e)}")
            result['metadata']['error'] = str(e)
        
        return result
    
    def _detect_sf424(self, text: str) -> bool:
        """Detect if PDF contains SF-424 form"""
        indicators = [
            'SF 424',
            'SF-424',
            'APPLICATION FOR FEDERAL ASSISTANCE',
            'APPLICANT INFORMATION',
            'Federal Identifier'
        ]
        return any(indicator in text for indicator in indicators)
    
    def _detect_ppop(self, text: str) -> bool:
        """Detect if PDF contains PPOP (Performance Site Location) form"""
        indicators = [
            'Project/Performance Site Location',
            'Primary Site',
            'Additional Site',
            'Performance Site',
            'Congressional District'
        ]
        return any(indicator in text for indicator in indicators)
    
    def _extract_sf424_fields(self, lines: List[str], full_text: str) -> Dict[str, str]:
        """Extract SF-424 specific fields"""
        fields = {}
        
        # Extract UEI
        for line in lines:
            if 'UEI:' in line:
                uei_match = re.search(r'UEI:\s*([A-Z0-9]+)', line)
                if uei_match:
                    fields['uei'] = uei_match.group(1)
        
        # Extract Legal Name (Applicant)
        for line in lines:
            if 'Legal Name:' in line:
                name = line.replace('Legal Name:', '').strip()
                if name and name not in ['', '-', 'N/A']:
                    fields['applicant_name'] = name
        
        # Extract Funding Opportunity Number
        fon_match = re.search(r'(HRSA-\d{2}-\d{3,4})', full_text)
        if fon_match:
            fields['funding_opportunity_number'] = fon_match.group(1)
        
        # Extract Application Type
        for i, line in enumerate(lines):
            if 'TYPE OF SUBMISSION' in line or 'Type of Application' in line:
                next_lines = ' '.join(lines[i:i+10])
                if 'Continuation' in next_lines:
                    fields['application_type'] = '2'  # Continuation
                elif 'Revision' in next_lines:
                    fields['application_type'] = '3'  # Revision
                elif 'Pre-application' in next_lines:
                    fields['application_type'] = 'Pre-application'
                else:
                    fields['application_type'] = '1'  # New
                break
        
        # Extract Federal Award Identifier (Grant Number)
        grant_patterns = [
            r'Federal Identifier[:\s]+([A-Z]\d{2}[A-Z]{2}\d{5,8})',
            r'Grant Number[:\s]+([A-Z]\d{2}[A-Z]{2}\d{5,8})',
            r'([A-Z]\d{2}[A-Z]{2}\d{5,8})'
        ]
        for pattern in grant_patterns:
            match = re.search(pattern, full_text)
            if match:
                fields['federal_award_identifier'] = match.group(1)
                break
        
        return fields
    
    def _extract_ppop_fields(self, lines: List[str], full_text: str) -> Dict[str, str]:
        """Extract PPOP (Performance Site Location) specific fields"""
        fields = {}
        
        # Extract Primary Site Congressional District
        for line in lines:
            if 'Congressional District' in line:
                # Look for district pattern like "VA-10" or "10"
                district_match = re.search(r'District[:\s]+([A-Z]{2}-\d{1,2}|\d{1,2})', line)
                if district_match:
                    fields['congressional_district'] = district_match.group(1)
        
        # Extract Primary Site Location (City, State)
        city_pattern = r'City[:\s]+([A-Za-z\s]+)'
        state_pattern = r'State[:\s]+([A-Z]{2})'
        
        city_match = re.search(city_pattern, full_text)
        state_match = re.search(state_pattern, full_text)
        
        if city_match:
            fields['primary_site_city'] = city_match.group(1).strip()
        if state_match:
            fields['primary_site_state'] = state_match.group(1).strip()
        
        return fields
