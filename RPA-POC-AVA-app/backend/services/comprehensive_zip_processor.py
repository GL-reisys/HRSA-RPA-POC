"""
Comprehensive ZIP Processor - IDEAL SOLUTION
Processes zip file containing:
1. SF-424 form - extracts and validates (UEI, Grant#, App Type, FON)
2. PPOP form - extracts and validates (congressional district, etc.)
3. Other attachments - counts total pages

Supports both XFA and flattened PDFs
"""
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from werkzeug.utils import secure_filename
import pikepdf

from services.xfa_pdf_extractor import XFAPdfExtractor
from services.flattened_pdf_extractor import FlattenedPdfExtractor
from services.form_detector import FormDetector, FormType
from services.sf424_validator import SF424Validator
from services.document_converter import DocumentConverter
# from services.ppop_validator import PPOPValidator  # TODO: Implement

class ComprehensiveZipProcessor:
    """
    Process zip file containing grant application forms and attachments
    Implements IDEAL solution
    """
    
    # Accepted file formats (from HRSA requirements)
    ACCEPTED_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.rtf', '.txt', '.wpd', '.xls', '.xlsx', '.vsd'
    }
    
    # Maximum limits
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
    MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200MB total
    MAX_FILES = 100
    MAX_PAGES = 150  # Page count limit for attachments
    
    def __init__(self, db_service=None):
        """Initialize with database service for validations"""
        self.xfa_extractor = XFAPdfExtractor()
        self.flat_extractor = FlattenedPdfExtractor()
        self.form_detector = FormDetector()
        self.sf424_validator = SF424Validator(db_service) if db_service else None
        self.converter = DocumentConverter()
        # self.ppop_validator = PPOPValidator(db_service) if db_service else None
    
    def process_zip(self, zip_path: str) -> Dict[str, Any]:
        """
        Process zip file - IDEAL SOLUTION
        
        Returns:
            {
                'success': bool,
                'sf424_validation': {...},  # SF-424 validation results
                'ppop_validation': {...},   # PPOP validation results
                'attachments': {
                    'total_files': int,
                    'total_pages': int,
                    'page_count_ok': bool,
                    'files': [...]
                },
                'errors': [...]
            }
        """
        result = {
            'success': False,
            'sf424_validation': None,
            'ppop_validation': None,
            'attachments': {
                'total_files': 0,
                'total_pages': 0,
                'page_count_ok': False,
                'files': []
            },
            'errors': []
        }
        
        temp_dir = None
        
        try:
            # 1. Validate zip file
            validation = self._validate_zip(zip_path)
            if not validation['valid']:
                result['errors'].append(validation['error'])
                return result
            
            # 2. Extract zip securely
            temp_dir = tempfile.mkdtemp()
            extracted_files = self._extract_zip_secure(zip_path, temp_dir)
            
            if not extracted_files:
                result['errors'].append('No valid files found in zip')
                return result
            
            # 3. Identify SF-424 and PPOP forms
            sf424_file = None
            ppop_file = None
            attachment_files = []
            
            for file_path in extracted_files:
                filename = os.path.basename(file_path).lower()
                
                # Identify SF-424
                if 'sf-424' in filename or 'sf424' in filename:
                    sf424_file = file_path
                # Identify PPOP
                elif 'ppop' in filename or 'performance' in filename or 'site' in filename:
                    ppop_file = file_path
                # Other PDFs - check content
                elif file_path.endswith('.pdf'):
                    form_type = self._identify_pdf_form(file_path)
                    if form_type == 'SF-424':
                        sf424_file = file_path
                    elif form_type == 'PPOP':
                        ppop_file = file_path
                    else:
                        attachment_files.append(file_path)
                else:
                    attachment_files.append(file_path)
            
            # 4. Process SF-424 form
            if sf424_file:
                result['sf424_validation'] = self._process_sf424(sf424_file)
            else:
                result['errors'].append('SF-424 form not found in zip')
            
            # 5. Process PPOP form
            if ppop_file:
                result['ppop_validation'] = self._process_ppop(ppop_file)
            else:
                # PPOP is optional, just note it
                result['ppop_validation'] = {'status': 'not_found', 'message': 'PPOP form not included'}
            
            # 6. Count pages in attachments
            result['attachments'] = self._count_attachment_pages(attachment_files)
            
            # 7. Check if page count is within limit
            result['attachments']['page_count_ok'] = result['attachments']['total_pages'] <= self.MAX_PAGES
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(f'Processing failed: {str(e)}')
        
        finally:
            # Cleanup
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        return result
    
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
                
                # Security: Check for path traversal
                if '..' in info.filename or info.filename.startswith('/'):
                    continue
                
                # Get safe filename
                safe_name = secure_filename(os.path.basename(info.filename))
                if not safe_name:
                    continue
                
                # Check extension
                ext = os.path.splitext(safe_name)[1].lower()
                if ext not in self.ACCEPTED_EXTENSIONS:
                    continue
                
                # Check file size
                if info.file_size > self.MAX_FILE_SIZE:
                    continue
                
                # Extract
                extract_path = os.path.join(extract_dir, safe_name)
                
                # Handle duplicates
                counter = 1
                while os.path.exists(extract_path):
                    name, ext = os.path.splitext(safe_name)
                    extract_path = os.path.join(extract_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                with zf.open(info) as source:
                    with open(extract_path, 'wb') as target:
                        target.write(source.read())
                
                extracted_files.append(extract_path)
        
        return extracted_files
    
    def _identify_pdf_form(self, pdf_path: str) -> Optional[str]:
        """Identify which form type a PDF contains"""
        try:
            # Try XFA extraction first
            xfa_data = self.xfa_extractor.extract_form_fields(pdf_path)
            form_type = self.form_detector.detect_form_type(xfa_data)
            
            if form_type == FormType.SF424:
                return 'SF-424'
            elif form_type == FormType.PERFORMANCE_SITE:
                return 'PPOP'
            
            # Try flattened extraction
            flat_data = self.flat_extractor.extract_form_fields(pdf_path)
            if 'SF-424' in flat_data['metadata'].get('forms_found', []):
                return 'SF-424'
            elif 'PPOP' in flat_data['metadata'].get('forms_found', []):
                return 'PPOP'
            
        except Exception as e:
            print(f"Error identifying PDF form: {str(e)}")
        
        return None
    
    def _process_sf424(self, pdf_path: str) -> Dict[str, Any]:
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
            # Extract fields (try XFA first, then flattened)
            xfa_data = self.xfa_extractor.extract_form_fields(pdf_path)
            
            if xfa_data['metadata']['field_count'] > 0:
                result['fields'] = xfa_data['fields']
                result['extracted'] = True
                result['extraction_method'] = 'XFA'
            else:
                # Try flattened
                flat_data = self.flat_extractor.extract_form_fields(pdf_path)
                if flat_data['metadata']['field_count'] > 0:
                    result['fields'] = flat_data['fields']
                    result['extracted'] = True
                    result['extraction_method'] = 'text_parsing'
            
            # Validate if we have a validator
            if result['extracted'] and self.sf424_validator:
                validation = self.sf424_validator.validate(result['fields'])
                result['validated'] = True
                result['validation_results'] = validation
                
                # Extract errors from validation
                if validation.get('errors'):
                    result['errors'] = validation['errors']
                if validation.get('warnings'):
                    result['warnings'] = validation['warnings']
            
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
            # Extract fields (try XFA first, then flattened)
            xfa_data = self.xfa_extractor.extract_form_fields(pdf_path)
            form_type = self.form_detector.detect_form_type(xfa_data)
            
            if form_type == FormType.PERFORMANCE_SITE:
                result['fields'] = xfa_data['fields']
                result['extracted'] = True
                result['extraction_method'] = 'XFA'
            else:
                # Try flattened
                flat_data = self.flat_extractor.extract_form_fields(pdf_path)
                if 'PPOP' in flat_data['metadata'].get('forms_found', []):
                    result['fields'] = flat_data['fields']
                    result['extracted'] = True
                    result['extraction_method'] = 'text_parsing'
            
            # TODO: Validate PPOP when validator is implemented
            # if result['extracted'] and self.ppop_validator:
            #     validation = self.ppop_validator.validate(result['fields'])
            #     result['validated'] = True
            #     result['validation_results'] = validation
            
        except Exception as e:
            result['errors'].append(f'PPOP processing failed: {str(e)}')
        
        return result
    
    def _count_attachment_pages(self, file_paths: List[str]) -> Dict[str, Any]:
        """Count pages in attachment files (converts non-PDF files first)"""
        result = {
            'total_files': len(file_paths),
            'total_pages': 0,
            'files': [],
            'converted': 0
        }
        
        for file_path in file_paths:
            file_info = {
                'name': os.path.basename(file_path),
                'pages': 0,
                'size_kb': os.path.getsize(file_path) / 1024,
                'type': os.path.splitext(file_path)[1].lower(),
                'original_type': os.path.splitext(file_path)[1].lower()
            }
            
            pdf_to_count = file_path
            
            # Convert non-PDF files to PDF if converter available
            if file_info['type'] != '.pdf':
                if self.converter.can_convert():
                    print(f"Converting {file_info['name']} to PDF...")
                    converted_pdf = self.converter.convert_to_pdf(file_path)
                    if converted_pdf:
                        pdf_to_count = converted_pdf
                        file_info['converted'] = True
                        file_info['type'] = '.pdf'
                        result['converted'] += 1
                    else:
                        file_info['conversion_failed'] = True
                        file_info['error'] = 'Conversion failed'
                else:
                    file_info['needs_conversion'] = True
                    file_info['error'] = 'No conversion tool available (install MS Office or LibreOffice)'
            
            # Count pages in PDF
            if pdf_to_count.endswith('.pdf'):
                try:
                    with pikepdf.open(pdf_to_count) as pdf:
                        file_info['pages'] = len(pdf.pages)
                        result['total_pages'] += file_info['pages']
                except Exception as e:
                    file_info['pages'] = 0
                    file_info['error'] = f'Could not count pages: {str(e)}'
            
            result['files'].append(file_info)
        
        return result
