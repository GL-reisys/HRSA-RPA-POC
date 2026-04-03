import pdfplumber
import os
from typing import Dict, List, Optional

class PDFReader:
    @staticmethod
    def extract_text(pdf_path: str) -> str:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ''
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
                return text.strip()
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    @staticmethod
    def get_metadata(pdf_path: str) -> Dict:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                metadata = {
                    'page_count': len(pdf.pages),
                    'metadata': pdf.metadata if hasattr(pdf, 'metadata') else {},
                }
                
                if pdf.pages:
                    first_page = pdf.pages[0]
                    metadata['page_dimensions'] = {
                        'width': first_page.width,
                        'height': first_page.height
                    }
                
                return metadata
        except Exception as e:
            raise Exception(f"Error reading PDF metadata: {str(e)}")
    
    @staticmethod
    def validate_pdf_structure(pdf_path: str) -> Dict:
        validation_result = {
            'is_valid': False,
            'has_text': False,
            'page_count': 0,
            'file_size': 0,
            'errors': []
        }
        
        try:
            if not os.path.exists(pdf_path):
                validation_result['errors'].append('File does not exist')
                return validation_result
            
            validation_result['file_size'] = os.path.getsize(pdf_path)
            
            if validation_result['file_size'] == 0:
                validation_result['errors'].append('File is empty')
                return validation_result
            
            if validation_result['file_size'] > 50 * 1024 * 1024:
                validation_result['errors'].append('File size exceeds 50MB limit')
                return validation_result
            
            with pdfplumber.open(pdf_path) as pdf:
                validation_result['page_count'] = len(pdf.pages)
                
                if validation_result['page_count'] == 0:
                    validation_result['errors'].append('PDF has no pages')
                    return validation_result
                
                text_content = ''
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text
                
                validation_result['has_text'] = len(text_content.strip()) > 0
                
                if not validation_result['has_text']:
                    validation_result['errors'].append('PDF contains no extractable text')
                
                validation_result['is_valid'] = len(validation_result['errors']) == 0
                
        except Exception as e:
            validation_result['errors'].append(f'Error validating PDF: {str(e)}')
        
        return validation_result
