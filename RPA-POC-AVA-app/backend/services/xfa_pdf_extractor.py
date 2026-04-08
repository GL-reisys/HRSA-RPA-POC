import pikepdf
from lxml import etree
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

class XFAPdfExtractor:
    """
    Extracts XFA form data from SF-424 PDFs.
    Based on C# XfaPdfExtractor.cs implementation.
    """
    
    def __init__(self):
        self.field_mapping = self._load_field_mapping()
    
    def extract_form_fields(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract form fields from XFA PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with:
            - raw_fields: Dict of field_name -> string value
            - fields: Dict of field_name -> parsed value (typed)
            - metadata: Form metadata (page_count, form_type, etc.)
        """
        result = {
            'raw_fields': {},
            'fields': {},
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'page_count': 0,
                'field_count': 0,
                'form_type': 'Unknown',
                'form_id': None,
                'form_version': None,
                'all_field_names': []
            }
        }
        
        try:
            pdf = pikepdf.open(pdf_path)
            result['metadata']['page_count'] = len(pdf.pages)
            
            self._extract_pdf_metadata(pdf, result)
            
            if self._try_extract_xfa_data(pdf, result):
                print(f"XFA extraction successful: {len(result['raw_fields'])} fields")
            elif self._try_extract_acroform_data(pdf, result):
                print(f"AcroForm extraction successful: {len(result['raw_fields'])} fields")
            else:
                print("Falling back to text extraction")
                self._extract_text_content(pdf, result)
            
            self._detect_form_type(result)
            
            result['metadata']['field_count'] = len(result['raw_fields'])
            
            pdf.close()
            
        except Exception as e:
            print(f"Error extracting PDF: {str(e)}")
            raise Exception(f"PDF extraction failed: {str(e)}")
        
        return result
    
    def _extract_pdf_metadata(self, pdf: pikepdf.Pdf, result: Dict):
        """Extract PDF document metadata (Title, Subject, Author, Creator)"""
        try:
            if pdf.docinfo:
                if '/Title' in pdf.docinfo:
                    title = str(pdf.docinfo['/Title'])
                    result['raw_fields']['_PDF_Title'] = title
                    print(f"PDF Title: {title}")
                
                if '/Subject' in pdf.docinfo:
                    subject = str(pdf.docinfo['/Subject'])
                    result['raw_fields']['_PDF_Subject'] = subject
                
                if '/Author' in pdf.docinfo:
                    author = str(pdf.docinfo['/Author'])
                    result['raw_fields']['_PDF_Author'] = author
                
                if '/Creator' in pdf.docinfo:
                    creator = str(pdf.docinfo['/Creator'])
                    result['raw_fields']['_PDF_Creator'] = creator
        except Exception as e:
            print(f"Error extracting PDF metadata: {str(e)}")
    
    def _try_extract_xfa_data(self, pdf: pikepdf.Pdf, result: Dict) -> bool:
        """
        Try to extract XFA form data.
        Returns True if successful, False otherwise.
        """
        try:
            if '/AcroForm' not in pdf.Root:
                return False
            
            acro_form = pdf.Root.AcroForm
            
            if '/XFA' not in acro_form:
                return False
            
            xfa_data = acro_form.XFA
            print("XFA data detected in PDF")
            result['metadata']['form_type'] = 'XFA'
            
            if isinstance(xfa_data, pikepdf.Array):
                xml_data = self._extract_xfa_xml_from_array(xfa_data)
                if xml_data:
                    self._parse_xfa_xml(xml_data, result)
                    return True
            elif isinstance(xfa_data, pikepdf.Stream):
                xml_data = bytes(xfa_data.read_bytes()).decode('utf-8')
                if xml_data:
                    self._parse_xfa_xml(xml_data, result)
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error extracting XFA data: {str(e)}")
            return False
    
    def _extract_xfa_xml_from_array(self, xfa_array: pikepdf.Array) -> Optional[str]:
        """
        Extract XML from XFA array.
        XFA array format: [tag1, stream1, tag2, stream2, ...]
        We need the 'datasets' stream which contains form data.
        """
        try:
            xml_parts = []
            
            for i in range(0, len(xfa_array), 2):
                if i + 1 < len(xfa_array):
                    tag = str(xfa_array[i])
                    stream_obj = xfa_array[i + 1]
                    
                    if isinstance(stream_obj, pikepdf.Stream):
                        xml_part = bytes(stream_obj.read_bytes()).decode('utf-8')
                        xml_parts.append(xml_part)
                        
                        if 'datasets' in tag.lower():
                            return xml_part
            
            return '\n'.join(xml_parts) if xml_parts else None
            
        except Exception as e:
            print(f"Error extracting XFA XML from array: {str(e)}")
            return None
    
    def _parse_xfa_xml(self, xml_string: str, result: Dict):
        """
        Parse XFA XML to extract form field values.
        XFA structure: <xfa:datasets><xfa:data><form>...</form></xfa:data></xfa:datasets>
        """
        try:
            print(f"Parsing XFA XML ({len(xml_string)} chars)")
            
            root = etree.fromstring(xml_string.encode('utf-8'))
            
            datasets_node = root.find('.//{http://www.xfa.org/schema/xfa-data/1.0/}datasets')
            if datasets_node is None:
                datasets_node = root.find('.//datasets')
            
            if datasets_node is not None:
                print("Found datasets node, extracting fields...")
                self._extract_xml_leaf_nodes(datasets_node, "", result)
            else:
                self._extract_xml_leaf_nodes(root, "", result)
            
            xml_sample = xml_string[:5000] if len(xml_string) > 5000 else xml_string
            result['raw_fields']['_XFA_XML_Sample'] = xml_sample
            
            print(f"Extracted {len(result['raw_fields'])} fields from XFA")
            
        except Exception as e:
            print(f"Error parsing XFA XML: {str(e)}")
            result['raw_fields']['_XFA_ParseError'] = f"Failed to parse XFA XML: {str(e)}"
    
    def _extract_xml_leaf_nodes(self, node: etree.Element, path: str, result: Dict):
        """
        Recursively extract leaf nodes (nodes with text content) from XML.
        Builds hierarchical field names like: form1_Page1_OrganizationName
        """
        if node is None:
            return
        
        node_name = node.tag.split('}')[-1] if '}' in node.tag else node.tag
        
        current_path = node_name if not path else f"{path}_{node_name}"
        
        has_text = node.text and node.text.strip()
        has_element_children = any(isinstance(child.tag, str) for child in node)
        
        if has_text and not has_element_children:
            value = node.text.strip()
            if value and len(value) < 1000:
                clean_path = self._clean_field_name(current_path)
                if clean_path not in result['raw_fields']:
                    result['raw_fields'][clean_path] = value
                    result['fields'][clean_path] = self._parse_field_value(value)
                    result['metadata']['all_field_names'].append(clean_path)
        else:
            for child in node:
                if isinstance(child.tag, str):
                    self._extract_xml_leaf_nodes(child, current_path, result)
    
    def _try_extract_acroform_data(self, pdf: pikepdf.Pdf, result: Dict) -> bool:
        """
        Fallback: Extract standard AcroForm fields if XFA not available.
        """
        try:
            if '/AcroForm' not in pdf.Root:
                return False
            
            acro_form = pdf.Root.AcroForm
            
            if '/Fields' not in acro_form:
                return False
            
            fields = acro_form.Fields
            print(f"AcroForm found with {len(fields)} fields")
            result['metadata']['form_type'] = 'AcroForm'
            
            for field in fields:
                field_name = str(field.T) if '/T' in field else None
                field_value = str(field.V) if '/V' in field else None
                
                if field_name:
                    clean_name = self._clean_field_name(field_name)
                    result['raw_fields'][clean_name] = field_value or ""
                    result['fields'][clean_name] = self._parse_field_value(field_value)
                    result['metadata']['all_field_names'].append(clean_name)
            
            return len(result['raw_fields']) > 0
            
        except Exception as e:
            print(f"Error extracting AcroForm data: {str(e)}")
            return False
    
    def _extract_text_content(self, pdf: pikepdf.Pdf, result: Dict):
        """
        Last resort: Extract text content from PDF pages.
        This is NOT ideal for form data but better than nothing.
        """
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf) as pdf_plumber:
                for i, page in enumerate(pdf_plumber.pages, 1):
                    text = page.extract_text()
                    field_name = f"Page_{i}_Text"
                    result['raw_fields'][field_name] = text
                    result['fields'][field_name] = text
                    result['metadata']['all_field_names'].append(field_name)
            
            result['metadata']['form_type'] = 'TextExtracted'
            print(f"Extracted text from {len(pdf.pages)} pages")
            
        except Exception as e:
            print(f"Error extracting text content: {str(e)}")
    
    def _clean_field_name(self, field_name: str) -> str:
        r"""
        Clean field name: remove special characters, replace with underscores.
        Matches C# implementation: Regex.Replace(fieldName, @"[\[\]\.]", "_")
        """
        if not field_name:
            return ""
        
        field_name = re.sub(r'[\[\]\.]', '_', field_name)
        field_name = re.sub(r'[^a-zA-Z0-9_]', '', field_name)
        
        return field_name
    
    def _parse_field_value(self, value: str) -> Any:
        """
        Parse field value to appropriate type (decimal, date, bool, or string).
        Matches C# implementation.
        """
        if not value or not value.strip():
            return None
        
        value = value.strip()
        
        try:
            return float(value)
        except ValueError:
            pass
        
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
        
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        return value
    
    def _detect_form_type(self, result: Dict):
        """
        Detect form type based on field names and PDF metadata.
        Matches C# DetectFormType logic.
        """
        field_names_lower = [f.lower() for f in result['metadata']['all_field_names']]
        
        form_id = result['raw_fields'].get('_PDF_Title')
        if not form_id:
            form_id = result['raw_fields'].get('_PDF_Subject')
        
        result['metadata']['form_id'] = form_id
        
        if any('sf424' in f or 'sf_424' in f for f in field_names_lower):
            result['metadata']['form_type'] = 'SF-424'
        elif (any('legalname' in f or 'organizationname' in f for f in field_names_lower) and
              any('ein' in f or 'employer' in f for f in field_names_lower) and
              any('applicanttype' in f for f in field_names_lower)):
            result['metadata']['form_type'] = 'SF-424'
        elif any('sf424a' in f or 'budget' in f for f in field_names_lower):
            result['metadata']['form_type'] = 'SF-424A'
        elif any('sf424b' in f or 'assurance' in f for f in field_names_lower):
            result['metadata']['form_type'] = 'SF-424B'
        elif any('sflll' in f or 'lobbying' in f for f in field_names_lower):
            result['metadata']['form_type'] = 'SF-LLL'
    
    def _load_field_mapping(self) -> Dict[str, List[str]]:
        """
        Load field name mapping configuration.
        Maps standard field names to possible XFA variations.
        """
        return {
            'OrganizationName': ['OrganizationName', 'LegalName', 'Applicant_Name', 'APPLICANT_LEGAL_NAME'],
            'SAMUEI': ['SAMUEI', 'UEI', 'SAM_UEI', 'UniqueEntityIdentifier'],
            'EmployerTaxpayerIdentificationNumber': ['EIN', 'TaxID', 'EmployerID', 'EMPLOYER_ID'],
            'ProjectTitle': ['ProjectTitle', 'Project_Title', 'PROJECT_TITLE'],
            'FederalEstimatedFunding': ['FederalEstimatedFunding', 'FederalFunds', 'FEDERAL_FUNDS'],
        }
