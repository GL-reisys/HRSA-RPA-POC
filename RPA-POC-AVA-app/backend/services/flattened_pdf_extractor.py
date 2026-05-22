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
        """Extract SF-424 specific fields with comprehensive parsing"""
        fields = {}
        
        # Extract UEI (multiple patterns)
        uei_patterns = [
            r'UEI[:\s]+([A-Z0-9]{12})',
            r'8c[.\s]+UEI[:\s]+([A-Z0-9]{12})',
            r'Unique Entity Identifier[:\s]+([A-Z0-9]{12})',
            r'([A-Z0-9]{12})',  # 12-character alphanumeric
        ]
        for pattern in uei_patterns:
            match = re.search(pattern, full_text)
            if match and len(match.group(1)) == 12:
                fields['samuei'] = match.group(1)
                break
        
        # Extract EIN (multiple patterns)
        ein_patterns = [
            r'EIN[:\s]+(\d{2}-\d{7})',
            r'8b[.\s]+EIN[:\s]+(\d{2}-\d{7})',
            r'Tax ID[:\s]+(\d{2}-\d{7})',
            r'(\d{2}-\d{7})',
        ]
        for pattern in ein_patterns:
            match = re.search(pattern, full_text)
            if match:
                ein = match.group(1)
                if re.match(r'^\d{2}-\d{7}$', ein):
                    fields['employer_taxpayer_identification_number'] = ein
                    break
        
        # Extract Organization Name (multiple patterns)
        org_patterns = [
            r'8a\.\s*Legal Name[:\s]+(.+)',
            r'Organization Name[:\s]+(.+)',
            r'Legal Name[:\s]+(.+)',
            r'Applicant Information[:\s\n]+(.+)',
        ]
        for pattern in org_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().split('\n')[0].strip()
                if name and name not in ['', '-', 'N/A', '*']:
                    fields['organization_name'] = name
                    break
        
        # Extract Funding Opportunity Number
        fon_match = re.search(r'(HRSA-\d{2}-\d{3,4})', full_text)
        if fon_match:
            fields['funding_opportunity_number'] = fon_match.group(1)
        
        # Extract Application Type
        for i, line in enumerate(lines):
            if 'TYPE OF SUBMISSION' in line.upper() or 'Type of Application' in line:
                next_lines = ' '.join(lines[i:i+10])
                if 'Continuation' in next_lines or '☒' in next_lines and 'Continuation' in next_lines:
                    fields['application_type'] = '2'
                elif 'Revision' in next_lines:
                    fields['application_type'] = '3'
                elif 'New' in next_lines:
                    fields['application_type'] = '1'
                break
        
        # Extract Submission Type
        if 'Pre-application' in full_text:
            fields['submission_type'] = 'Pre-application'
        elif 'Application' in full_text:
            fields['submission_type'] = 'Application'
        
        # Extract Project Title
        title_patterns = [
            r'Project Title[:\s]+(.+)',
            r'11\.\s*(.+)',
        ]
        for pattern in title_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                title = match.group(1).strip().split('\n')[0].strip()
                if title and len(title) > 3 and title not in ['', '-', 'N/A']:
                    fields['project_title'] = title
                    break
        
        # Extract Contact Email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
        if email_match:
            fields['email'] = email_match.group(0)
        
        # Extract Contact Phone
        phone_patterns = [
            r'Phone[:\s]+([\d\(\)\-\s\.]+)',
            r'Telephone[:\s]+([\d\(\)\-\s\.]+)',
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, full_text)
            if match:
                phone = match.group(1) if 'group' in dir(match) and match.lastindex else match.group(0)
                if len(phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')) >= 10:
                    fields['phone_number'] = phone.strip()
                    break
        
        # Extract Authorized Representative Name
        auth_rep_patterns = [
            r'Authorized Representative[:\s\n]+([A-Za-z]+)\s+([A-Za-z]+)',
            r'First Name[:\s]+([A-Za-z]+).*Last Name[:\s]+([A-Za-z]+)',
        ]
        for pattern in auth_rep_patterns:
            match = re.search(pattern, full_text, re.DOTALL | re.IGNORECASE)
            if match:
                fields['authorized_representative_first_name'] = match.group(1).strip()
                fields['authorized_representative_last_name'] = match.group(2).strip()
                break
        
        # Extract City, State, Zip
        city_match = re.search(r'City[:\s]+([A-Za-z\s]+)', full_text)
        if city_match:
            fields['applicant_city'] = city_match.group(1).strip()
        
        state_match = re.search(r'State[:\s]+([A-Z]{2})', full_text)
        if state_match:
            fields['applicant_state'] = state_match.group(1)
        
        zip_match = re.search(r'ZIP[:\s]+(\d{5}(?:-\d{4})?)', full_text, re.IGNORECASE)
        if zip_match:
            fields['applicant_zip_postal_code'] = zip_match.group(1)
        
        # Extract Federal Award Identifier (Grant Number)
        grant_patterns = [
            r'Federal Identifier[:\s]+([A-Z]\d{2}[A-Z]{2}\d{5,8})',
            r'Grant Number[:\s]+([A-Z]\d{2}[A-Z]{2}\d{5,8})',
            r'5b[.\s]+Federal Award Identifier[:\s]+([A-Z]\d{2}[A-Z]{2}\d{5,8})',
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
