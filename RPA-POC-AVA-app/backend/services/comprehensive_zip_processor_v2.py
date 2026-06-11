"""
Comprehensive ZIP Processor V2 - NOFO-based validation
Processes zip file containing grant application forms and attachments.

Key requirements:
1. Extract NOFO from ZIP filename
2. Query database for package forms and max attachment page count
3. Classify files as forms vs attachments based on database
4. Only count attachment pages (forms excluded)
5. Handle all scenarios: SF-424 only, PPOP only, both, forms+attachments
"""
import os
import re
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from werkzeug.utils import secure_filename
import pikepdf

from services.xfa_pdf_extractor import XFAPdfExtractor
from services.flattened_pdf_extractor import FlattenedPdfExtractor
from services.form_detector import FormDetector, FormType
from services.form_mapper import FormMapper
from services.sf424_validator import SF424Validator
from services.document_converter import DocumentConverter
from services.ppop_validator import PPOPValidator
from services.ppop_field_mapper import PPOPFieldMapper

class ComprehensiveZipProcessorV2:
    """
    Process zip file containing grant application forms and attachments
    with NOFO-based validation
    """
    
    # Accepted file formats
    ACCEPTED_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.rtf', '.txt', '.wpd', '.xls', '.xlsx', '.vsd', '.vsdx'
    }
    
    # Maximum limits
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
    MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200MB total
    MAX_FILES = 100
    
    def __init__(self, db_service=None):
        """Initialize with database service for validations"""
        self.db_service = db_service
        self.xfa_extractor = XFAPdfExtractor()
        self.flat_extractor = FlattenedPdfExtractor()
        self.form_detector = FormDetector()
        self.form_mapper = FormMapper()
        self.sf424_validator = SF424Validator(db_service) if db_service else None
        self.converter = DocumentConverter()
        self.ppop_validator = PPOPValidator()
        self.ppop_field_mapper = PPOPFieldMapper()
    
    def extract_nofo_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract NOFO (funding opportunity number) from ZIP filename.
        Expected format: HRSA-YY-XXX anywhere in filename
        """
        # Pattern: HRSA-##-###
        pattern = r'HRSA-\d{2}-\d{3}'
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return None
    
    def match_form_name(self, filename: str, form_names: List[str]) -> Optional[str]:
        """
        Check if filename matches any of the expected form names.
        Handles fuzzy matching and special cases like PerformanceSite = PPOP.
        Patterns: SF424_4, PerformanceSite_4, etc.
        """
        filename_lower = filename.lower()
        
        # First check for common form patterns regardless of database
        # SF-424 variations: Accept only ACTUAL SF-424 forms, not attachments with SF424 in name
        # VALID: Form SF424_4_0-V4.0.pdf, SF-424.pdf, sf424.pdf
        # INVALID (attachments): SF424_4_0-AdditionalProjectTitle-1235-xxx.pdf, SF424_4_0-1234-CustomName.pdf
        # INVALID (R&R forms): RR_SF424 (Research & Related forms - different structure, should count in page limit)
        if ('sf424' in filename_lower or 'sf-424' in filename_lower):
            # Exclude SF-424A, SF-424R, and R&R SF-424 (different forms that should count in page limit)
            if ('sf424a' in filename_lower or 'sf-424a' in filename_lower or
                'sf424r' in filename_lower or 'sf-424r' in filename_lower or
                'rr_sf424' in filename_lower or 'rr-sf424' in filename_lower):
                return None  # Not standard SF-424
            
            # Exclude attachments with "AdditionalProjectTitle" or numeric IDs after SF424
            # Pattern: SF424_4_0-1234-xxx or SF424_4_0-AdditionalProjectTitle-xxx
            if 'additionalprojecttitle' in filename_lower:
                return None  # This is an attachment, not the form
            
            # Exclude files with pattern: SF424_4_0-[numbers]-[text]
            # Example: SF424_4_0-1234-Homeless Map.pdf
            import re
            if re.search(r'sf424[_-]?\d+[_-]?\d+-\d+-', filename_lower):
                return None  # This is an attachment with custom ID
            
            return 'SF-424'
        
        # PPOP/PerformanceSite variations: PerformanceSite_4, PPOP
        if 'performancesite_4' in filename_lower or 'ppop' in filename_lower:
            return 'PerformanceSite'
        
        # Any file starting with "Form " (followed by something other than Attachment) is a form
        # This catches Key_Contacts, Project_AbstractSummary, SFLLL, GG_LobbyingForm, etc.
        if filename_lower.startswith('form '):
            # Exception: Form AttachmentForm or Form ...Attachments are attachments
            if 'attachmentform' not in filename_lower and 'attachments' not in filename_lower:
                return 'OTHER_FORM'  # Generic form type
        
        # Then check against database form names
        for form_name in form_names:
            form_lower = form_name.lower()
            
            # Direct match
            if form_lower in filename_lower:
                return form_name
        
        return None
    
    def is_attachment_file(self, filename: str) -> bool:
        """
        Check if file is an attachment by name.
        Attachments contain 'AttachmentForm' or 'Attachments' in filename.
        ONLY these patterns count as attachments.
        """
        filename_lower = filename.lower()
        # Must explicitly have "attachmentform" or "attachments" (not just "attachment")
        return 'attachmentform' in filename_lower or 'attachments' in filename_lower
    
    def process_zip(self, zip_path: str) -> Dict[str, Any]:
        """
        Process ZIP file and return validation results.
        """
        result = {
            'success': False,
            'nofo': None,
            'sf424_validation': None,
            'ppop_validation': None,
            'attachments': {
                'total_files': 0,
                'total_pages': 0,
                'attachment_pages': 0,
                'form_pages': 0,
                'page_count_ok': False,
                'max_attachment_page_count': None,
                'files': []
            },
            'errors': []
        }
        
        temp_dir = None
        
        try:
            # 1. Extract NOFO from filename
            zip_filename = os.path.basename(zip_path)
            nofo = self.extract_nofo_from_filename(zip_filename)
            
            if not nofo:
                result['errors'].append('Invalid ZIP filename format. ZIP must contain funding opportunity number (e.g., HRSA-26-091)')
                return result
            
            result['nofo'] = nofo
            print(f"Extracted NOFO: {nofo}")
            
            # 2. Query database for package configuration
            if not self.db_service:
                result['errors'].append('Database service not available')
                return result
            
            try:
                max_attachment_pages = self.db_service.get_max_attachment_page_count(nofo)
                package_forms = self.db_service.get_package_forms(nofo)
                
                if max_attachment_pages is None:
                    # NOFO not in database - continue processing but can't validate page count
                    result['errors'].append(f'Funding opportunity {nofo} not found in database')
                    max_attachment_pages = None
                    package_forms = []  # Will use default form detection patterns
                    print(f"NOFO {nofo} not found - using default form patterns")
                else:
                    result['attachments']['max_attachment_page_count'] = max_attachment_pages
                    print(f"Max attachment pages: {max_attachment_pages}")
                    print(f"Expected forms: {package_forms}")
                
            except Exception as e:
                # Database query failed - continue with default patterns
                result['errors'].append(f'Database query failed: {str(e)}')
                max_attachment_pages = None
                package_forms = []
                print(f"Database error - using default form patterns")
            
            # 3. Validate zip file
            validation = self._validate_zip(zip_path)
            if not validation['valid']:
                result['errors'].append(validation['error'])
                return result
            
            # 4. Extract zip securely
            temp_dir = tempfile.mkdtemp()
            extracted_files = self._extract_zip_secure(zip_path, temp_dir)
            
            if not extracted_files:
                result['errors'].append('No valid files found in zip')
                return result
            
            # 5. Classify files as forms or attachments
            sf424_file = None
            ppop_file = None
            page_count_files = []  # Files to count towards page limit
            excluded_files = []  # SF-424, PPOP, GrantApplication, manifest
            
            for file_path in extracted_files:
                filename = os.path.basename(file_path)
                file_ext = os.path.splitext(filename)[1].lower()
                filename_lower = filename.lower()
                
                # Skip non-accepted file formats
                if file_ext not in self.ACCEPTED_EXTENSIONS:
                    print(f"Skipping unsupported file format: {filename}")
                    continue
                
                # Skip manifest and system files (excluded from page count)
                if filename_lower in ['manifest.txt', 'manifest.xml', 'readme.txt']:
                    print(f"Skipping system file: {filename}")
                    excluded_files.append({'path': file_path, 'name': filename, 'reason': 'System file'})
                    continue
                
                # Skip GrantApplication files (excluded from page count)
                if 'grantapplication' in filename_lower:
                    print(f"Excluding GrantApplication file: {filename}")
                    excluded_files.append({'path': file_path, 'name': filename, 'reason': 'GrantApplication'})
                    continue
                
                # Check if this is a known form by pattern
                matched_form = self.match_form_name(filename, package_forms)
                
                if matched_form:
                    # This is a form - identify which one
                    if matched_form in ['SF-424', 'sf-424', 'SF424']:
                        sf424_file = file_path
                        excluded_files.append({'path': file_path, 'name': filename, 'reason': 'SF-424 form'})
                        print(f"Identified SF-424 (excluded from page count): {filename}")
                    elif matched_form in ['PerformanceSite', 'PPOP']:
                        ppop_file = file_path
                        excluded_files.append({'path': file_path, 'name': filename, 'reason': 'PPOP form'})
                        print(f"Identified PPOP (excluded from page count): {filename}")
                    else:
                        # Other forms count towards page limit
                        page_count_files.append({'path': file_path, 'name': filename, 'type': 'form', 'form_name': matched_form})
                        print(f"Identified form {matched_form} (counted): {filename}")
                else:
                    # All other files count towards page limit
                    page_count_files.append({'path': file_path, 'name': filename, 'type': 'attachment'})
                    print(f"Identified file (counted): {filename}")
            
            print(f"\nSummary - Files counted towards page limit: {len(page_count_files)}")
            print(f"Summary - Files excluded from page count: {len(excluded_files)}")
            
            # 6. Process SF-424 if present
            if sf424_file:
                result['sf424_validation'] = self._process_sf424(sf424_file, nofo)
            
            # 7. Process PPOP if present
            if ppop_file:
                result['ppop_validation'] = self._process_ppop(ppop_file)
            
            # 8. Count pages - NEW LOGIC: Count everything except SF-424, PPOP, GrantApplication, manifest
            all_files_info = []
            excluded_files_info = []
            total_counted_pages = 0
            
            # Count pages for files that count towards limit
            for file_info in page_count_files:
                page_info = self._count_file_pages(file_info['path'])
                page_info['file_type'] = file_info.get('type', 'attachment')
                if 'form_name' in file_info:
                    page_info['form_name'] = file_info['form_name']
                all_files_info.append(page_info)
                total_counted_pages += page_info['pages']
            
            # Count pages for excluded files (for information only)
            # BUT: Don't convert system files like manifest.txt - only count SF-424 and PPOP
            for file_info in excluded_files:
                # Skip system files and GrantApplication - don't convert them
                if file_info['reason'] in ['System file', 'GrantApplication']:
                    continue
                
                page_info = self._count_file_pages(file_info['path'])
                page_info['file_type'] = 'excluded'
                page_info['exclusion_reason'] = file_info['reason']
                excluded_files_info.append(page_info)
            
            result['attachments']['files'] = all_files_info
            result['attachments']['excluded_files'] = excluded_files_info
            result['attachments']['total_files'] = len(all_files_info)
            result['attachments']['total_pages'] = total_counted_pages
            result['attachments']['excluded_file_count'] = len(excluded_files_info)
            
            # 9. Validate page count against limit
            if max_attachment_pages and total_counted_pages <= max_attachment_pages:
                result['attachments']['page_count_ok'] = True
            elif max_attachment_pages:
                result['attachments']['page_count_ok'] = False
            else:
                # No limit available from database
                result['attachments']['page_count_ok'] = None
            
            print(f"Total pages counted: {total_counted_pages}")
            print(f"Max allowed pages: {max_attachment_pages}")
            print(f"Page count OK: {result['attachments']['page_count_ok']}")
            print(f"Excluded files: {len(excluded_files_info)}")
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(f'Processing failed: {str(e)}')
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        return result
    
    def _count_file_pages(self, file_path: str) -> Dict[str, Any]:
        """Count pages in a file (convert to PDF if needed)"""
        file_info = {
            'name': os.path.basename(file_path),
            'pages': 0,
            'size_kb': os.path.getsize(file_path) / 1024,
            'type': os.path.splitext(file_path)[1].lower(),
            'original_type': os.path.splitext(file_path)[1].lower()
        }
        
        pdf_to_count = file_path
        converted_pdf_path = None
        
        try:
            # Convert non-PDF files to PDF if converter available
            if file_info['type'] != '.pdf':
                if self.converter.can_convert():
                    converted_pdf = self.converter.convert_to_pdf(file_path)
                    if converted_pdf:
                        pdf_to_count = converted_pdf
                        converted_pdf_path = converted_pdf
                        file_info['converted'] = True
                        file_info['type'] = '.pdf'
                    else:
                        file_info['conversion_failed'] = True
                        file_info['error'] = 'Conversion failed'
                else:
                    file_info['needs_conversion'] = True
                    file_info['error'] = 'No conversion tool available'
            
            # Count pages in PDF
            if pdf_to_count.endswith('.pdf'):
                try:
                    with pikepdf.open(pdf_to_count) as pdf:
                        file_info['pages'] = len(pdf.pages)
                except Exception as e:
                    file_info['pages'] = 0
                    file_info['error'] = f'Could not count pages: {str(e)}'
            
            return file_info
        
        finally:
            # Clean up converted PDF to prevent temp file accumulation
            if converted_pdf_path and os.path.exists(converted_pdf_path):
                try:
                    os.remove(converted_pdf_path)
                    print(f"  🧹 Cleaned up converted PDF: {os.path.basename(converted_pdf_path)}")
                except Exception as e:
                    print(f"  ⚠️  Could not delete converted PDF: {str(e)}")
    
    def _validate_zip(self, zip_path: str) -> Dict[str, Any]:
        """Validate zip file security"""
        if not os.path.exists(zip_path):
            return {'valid': False, 'error': 'ZIP file not found'}
        
        file_size = os.path.getsize(zip_path)
        if file_size > self.MAX_TOTAL_SIZE:
            return {'valid': False, 'error': f'ZIP file too large: {file_size / 1024 / 1024:.1f}MB (max: 200MB)'}
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Check for zip bomb
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > self.MAX_TOTAL_SIZE * 10:
                    return {'valid': False, 'error': 'Suspicious zip file (possible zip bomb)'}
                
                # Check file count
                file_count = len([f for f in zf.infolist() if not f.is_dir()])
                if file_count > self.MAX_FILES:
                    return {'valid': False, 'error': f'Too many files: {file_count} (max: {self.MAX_FILES})'}
        
        except zipfile.BadZipFile:
            return {'valid': False, 'error': 'Invalid ZIP file format'}
        
        return {'valid': True}
    
    def _extract_zip_secure(self, zip_path: str, extract_dir: str) -> List[str]:
        """Extract zip securely (prevent path traversal)"""
        extracted_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                # Skip directories
                if info.is_dir():
                    continue
                
                # Security: explicit path traversal check
                if '..' in info.filename or info.filename.startswith('/') or info.filename.startswith('\\'):
                    print(f"Security warning: Path traversal detected in {info.filename}")
                    continue
                
                # Security: prevent path traversal (additional safeguard)
                filename = os.path.basename(info.filename)
                if not filename or filename.startswith('.'):
                    continue
                
                # Extract file
                try:
                    extract_path = os.path.join(extract_dir, filename)
                    with zf.open(info) as source, open(extract_path, 'wb') as target:
                        target.write(source.read())
                    extracted_files.append(extract_path)
                except Exception as e:
                    print(f"Warning: Could not extract {filename}: {e}")
        
        return extracted_files
    
    def _process_sf424(self, pdf_path: str, expected_nofo: str = None) -> Dict[str, Any]:
        """Extract and validate SF-424 form"""
        result = {
            'form_type': 'SF-424',
            'extracted': False,
            'validated': False,
            'fields': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            print(f"DEBUG: Processing SF-424 from: {pdf_path}")
            
            # Extract fields
            xfa_data = self.xfa_extractor.extract_form_fields(pdf_path)
            print(f"DEBUG: XFA extraction returned {len(xfa_data.get('fields', {}))} fields")
            
            if xfa_data.get('fields'):
                field_names = list(xfa_data['fields'].keys())
                print(f"DEBUG: First 10 field names: {field_names[:10]}")
                print(f"DEBUG: ALL SF-424 FIELD NAMES ({len(field_names)} total):")
                for fname in field_names[:50]:  # Show first 50
                    print(f"  - {fname}: {str(xfa_data['fields'][fname])[:100]}")
            
            form_type = self.form_detector.detect_form_type(xfa_data)
            print(f"DEBUG: Form type detected: {form_type}")
            
            if form_type == FormType.SF424:
                # Check if fields are already in standard format (from flattened extraction)
                # Flattened extraction returns fields like 'authorized_representative_first_name'
                # XFA extraction returns fields like 'AuthorizedRepresentative_FirstName'
                is_already_mapped = 'authorized_representative_email' in xfa_data.get('fields', {})
                
                if is_already_mapped:
                    # Fields are already in correct format from flattened extraction
                    mapped_fields = xfa_data['fields']
                    print(f"DEBUG: Using flattened extraction fields directly (already in correct format)")
                    result['extraction_method'] = 'Flattened'
                else:
                    # Map XFA fields to standard SF-424 fields
                    mapped_fields = self.form_mapper.map_to_sf424(xfa_data)
                    result['extraction_method'] = 'XFA'
                
                print(f"DEBUG: Mapped {len(mapped_fields)} SF-424 fields")
                print(f"DEBUG: Auth Rep fields after mapping:")
                print(f"  - authorized_representative_first_name: {mapped_fields.get('authorized_representative_first_name')}")
                print(f"  - authorized_representative_last_name: {mapped_fields.get('authorized_representative_last_name')}")
                print(f"  - authorized_representative_email: {mapped_fields.get('authorized_representative_email')}")
                result['fields'] = mapped_fields
                result['extracted'] = True
                
                # CRITICAL: Compare NOFO from ZIP filename with NOFO in SF-424
                if expected_nofo:
                    sf424_nofo = mapped_fields.get('funding_opportunity_number', '').strip().upper()
                    expected_nofo_clean = expected_nofo.strip().upper()
                    
                    print(f"DEBUG: NOFO Comparison - ZIP: {expected_nofo_clean}, SF-424: {sf424_nofo}")
                    
                    if sf424_nofo != expected_nofo_clean:
                        result['nofo_mismatch'] = True
                        result['nofo_error'] = {
                            'user_message': f'Funding Opportunity Number mismatch: ZIP filename has {expected_nofo_clean} but SF-424 form has {sf424_nofo}',
                            'expected': expected_nofo_clean,
                            'actual': sf424_nofo
                        }
                        result['errors'].append(result['nofo_error']['user_message'])
                        print(f"ERROR: NOFO mismatch - skipping validations")
                        # Return immediately - don't run validations
                        return result
                    else:
                        result['nofo_match'] = True
                        print(f"SUCCESS: NOFO match verified")
                
                # Validate SF-424
                if self.sf424_validator:
                    try:
                        validation_result = self.sf424_validator.validate_form_data(result['fields'])
                        result['validated'] = True
                        
                        if validation_result:
                            result['validation_results'] = {
                                'valid': False,
                                'error_count': len(validation_result),
                                'errors': [{
                                    'user_message': err.user_message,
                                    'ai_context': err.ai_context,
                                    'field_name': err.field_name,
                                    'page_number': err.page_number,
                                    'field_location': err.field_location,
                                    'current_value': err.current_value,
                                    'guidance': err.guidance,
                                    'image_path': err.image_path
                                } for err in validation_result]
                            }
                        else:
                            result['validation_results'] = {
                                'valid': True,
                                'error_count': 0,
                                'message': 'All SF-424 validations passed'
                            }
                    except Exception as e:
                        result['errors'].append(f'SF-424 validation failed: {str(e)}')
            
        except Exception as e:
            result['errors'].append(f'SF-424 processing failed: {str(e)}')
        
        return result
    
    def _process_ppop(self, pdf_path: str) -> Dict[str, Any]:
        """Extract and validate PPOP form"""
        result = {
            'form_type': 'PPOP',
            'extracted': False,
            'validated': False,
            'fields': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            print(f"DEBUG: Processing PPOP from: {pdf_path}")
            
            # Extract fields
            xfa_data = self.xfa_extractor.extract_form_fields(pdf_path)
            print(f"DEBUG: XFA extraction returned {len(xfa_data.get('fields', {}))} fields")
            
            if xfa_data.get('fields'):
                print(f"DEBUG: Field names: {list(xfa_data['fields'].keys())}")
            
            # Since we already identified this file as PPOP from the filename (PerformanceSite_4_0),
            # we should trust that and extract fields regardless of form type detection
            # (Form type detection fails on flattened PDFs with simple field names)
            
            if xfa_data.get('fields') and len(xfa_data['fields']) > 0:
                result['fields'] = xfa_data['fields']
                result['extracted'] = True
                result['extraction_method'] = xfa_data.get('metadata', {}).get('extraction_method', 'XFA')
                print(f"✓ PPOP extraction successful: {len(result['fields'])} fields")
                
                # Validate PPOP if validator available
                if self.ppop_validator:
                    try:
                        from services.ppop_field_mapper import PPOPFieldMapper
                        
                        # Map fields to PPOPFormData
                        mapper = PPOPFieldMapper()
                        # xfa_data has 'fields' dict but mapper expects 'raw_fields'
                        xfa_data_for_mapper = {'raw_fields': xfa_data['fields']}
                        ppop_data = mapper.map_to_ppop(xfa_data_for_mapper)
                        
                        # Run validation
                        validation_errors = self.ppop_validator.validate_ppop_form(ppop_data)
                        
                        result['validated'] = True
                        if validation_errors:
                            result['validation_results'] = {
                                'valid': False,
                                'error_count': len(validation_errors),
                                'errors': [{
                                    'user_message': err.user_message,
                                    'ai_context': err.ai_context,
                                    'field_name': err.field_name,
                                    'page_number': err.page_number,
                                    'field_location': err.field_location,
                                    'current_value': err.current_value,
                                    'guidance': err.guidance,
                                    'image_path': err.image_path
                                } for err in validation_errors]
                            }
                        else:
                            result['validation_results'] = {
                                'valid': True,
                                'error_count': 0,
                                'message': 'All PPOP validations passed'
                            }
                    except Exception as e:
                        result['errors'].append(f'PPOP validation failed: {str(e)}')
            
        except Exception as e:
            result['errors'].append(f'PPOP processing failed: {str(e)}')
        
        return result
