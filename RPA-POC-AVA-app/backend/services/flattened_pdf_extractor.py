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
        
        # Debug: Show section around Auth Rep fields (field 21)
        auth_rep_section = re.search(r'(21[a-z].*?(?:22|$))', full_text, re.DOTALL | re.IGNORECASE)
        if auth_rep_section:
            print(f"DEBUG: Auth Rep section from PDF:\n{auth_rep_section.group(1)[:500]}")
        
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
        
        # Extract Grant Number / Federal Award Identifier (field 5b)
        grant_patterns = [
            r'5b[.\s]*Federal\s+Award\s+Identifier:\s*([A-Z0-9]+)',
            r'Federal\s+Award\s+Identifier:\s*([A-Z0-9]+)',
            r'5b[.\s]*(?:Federal Award Identifier)?:\s*([A-Z0-9]+)',
        ]
        for pattern in grant_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                grant_num = match.group(1).strip()
                if grant_num and len(grant_num) > 5:
                    fields['federal_award_identifier'] = grant_num
                    print(f"DEBUG: Found Grant Number: {grant_num}")
                    break
        
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
        # Pattern matches: "Authorized Representative: Prefix: * First Name: Jane Middle Name: * Last Name: Doe"
        auth_rep_section = re.search(r'Authorized\s+Representative:.*?Prefix:.*?\*\s*First\s+Name:\s*([A-Za-z\'-]+).*?Middle\s+Name:.*?\*\s*Last\s+Name:\s*([A-Za-z\'-]+)', full_text, re.DOTALL | re.IGNORECASE)
        if auth_rep_section:
            first_name = auth_rep_section.group(1).strip()
            last_name = auth_rep_section.group(2).strip()
            if first_name and len(first_name) > 1:
                fields['authorized_representative_first_name'] = first_name
                print(f"DEBUG: Found Auth Rep First Name: {first_name}")
            if last_name and len(last_name) > 1:
                fields['authorized_representative_last_name'] = last_name
                print(f"DEBUG: Found Auth Rep Last Name: {last_name}")
        
        # Fallback: Try simpler patterns if main pattern failed
        if 'authorized_representative_first_name' not in fields:
            first_fallback = re.search(r'\*\s*First\s+Name:\s*([A-Za-z\'-]+)(?:\s+Middle|\s+\*\s*Last)', full_text, re.IGNORECASE)
            if first_fallback:
                name = first_fallback.group(1).strip()
                if name and name.lower() not in ['name', 'first', 'john', 'jane']:
                    fields['authorized_representative_first_name'] = name
                    print(f"DEBUG: Found Auth Rep First Name (fallback): {name}")
        
        if 'authorized_representative_last_name' not in fields:
            last_fallback = re.search(r'Middle\s+Name:.*?\*\s*Last\s+Name:\s*([A-Za-z\'-]+)', full_text, re.DOTALL | re.IGNORECASE)
            if last_fallback:
                name = last_fallback.group(1).strip()
                if name and name.lower() not in ['name', 'last', 'smith', 'doe']:
                    fields['authorized_representative_last_name'] = name
                    print(f"DEBUG: Found Auth Rep Last Name (fallback): {name}")
        
        # Extract Authorized Representative Email - field 21d
        auth_email_patterns = [
            r'21d[.\s]*(?:E-?Mail)?[:\s]+([\w\.-]+@[\w\.-]+\.\w+)',
            r'(?:AOR|Authorized Representative).*?(?:E-?Mail|Email Address)[:\s]+([\w\.-]+@[\w\.-]+\.\w+)',
        ]
        for pattern in auth_email_patterns:
            match = re.search(pattern, full_text, re.DOTALL | re.IGNORECASE)
            if match:
                email = match.group(1).strip()
                if '@' in email:
                    fields['authorized_representative_email'] = email
                    print(f"DEBUG: Found Auth Rep Email: {email}")
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
        
        print("DEBUG PPOP EXTRACTION: Starting PPOP field extraction")
        print(f"DEBUG PPOP EXTRACTION: Full text length: {len(full_text)} chars")
        
        # Extract Primary Site Street Address
        # Look for patterns like "Street1:", "Street 1:", "Address:", etc.
        street_patterns = [
            r'Street\s*1?[:\s]+([^\n]+)',
            r'Address[:\s]+([^\n]+)',
            r'Street Address[:\s]+([^\n]+)',
        ]
        for pattern in street_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                street = match.group(1).strip()
                # Filter out labels and empty values
                if street and street not in ['', '-', '*', 'N/A', 'Street2', 'City']:
                    fields['Street1'] = street
                    print(f"DEBUG PPOP EXTRACTION: Found Street1: {street}")
                    break
        
        # Extract Primary Site City
        city_patterns = [
            r'City[:\s]+([A-Za-z\s]+?)(?:\n|County|State)',
            r'City[:\s]+([A-Za-z\s]+)',
        ]
        for pattern in city_patterns:
            city_match = re.search(pattern, full_text)
            if city_match:
                city = city_match.group(1).strip()
                if city and city not in ['', '-', '*', 'N/A', 'State']:
                    fields['City'] = city
                    print(f"DEBUG PPOP EXTRACTION: Found City: {city}")
                    break
        
        # Extract Primary Site State
        state_patterns = [
            r'State[:\s]+([A-Z]{2})',
            r'State[:\s]+([A-Za-z\s]+?)(?:\n|ZIP)',
        ]
        for pattern in state_patterns:
            state_match = re.search(pattern, full_text)
            if state_match:
                state = state_match.group(1).strip()
                if len(state) == 2:  # State code
                    fields['State'] = state
                    print(f"DEBUG PPOP EXTRACTION: Found State: {state}")
                    break
        
        # Extract Primary Site ZIP Code
        # Look for patterns like "ZIP / Postal Code:", "ZIP:", "Postal Code:", etc.
        zip_patterns = [
            r'ZIP\s*/\s*Postal\s+Code[:\s]+(\d{5}(?:-\d{4})?)',
            r'ZIP[:\s]+(\d{5}(?:-\d{4})?)',
            r'Postal\s+Code[:\s]+(\d{5}(?:-\d{4})?)',
            r'Zip\s*Code[:\s]+(\d{5}(?:-\d{4})?)',
        ]
        for pattern in zip_patterns:
            zip_match = re.search(pattern, full_text, re.IGNORECASE)
            if zip_match:
                zip_code = zip_match.group(1).strip()
                if zip_code:
                    fields['ZIP / Postal Code'] = zip_code
                    print(f"DEBUG PPOP EXTRACTION: Found ZIP: {zip_code}")
                    break
        
        # Extract Primary Site Congressional District
        for line in lines:
            if 'Congressional District' in line:
                # Look for district pattern like "VA-10" or "10"
                district_match = re.search(r'District[:\s]+([A-Z]{2}-\d{1,2}|\d{1,2})', line)
                if district_match:
                    fields['congressional_district'] = district_match.group(1)
                    print(f"DEBUG PPOP EXTRACTION: Found District: {district_match.group(1)}")
        
        print(f"DEBUG PPOP EXTRACTION: Extracted {len(fields)} fields: {list(fields.keys())}")
        return fields
