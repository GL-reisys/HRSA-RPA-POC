import os
from typing import Dict, Optional
from werkzeug.utils import secure_filename
from utils.pdf_reader import PDFReader

class PDFValidatorService:
    ALLOWED_EXTENSIONS = {'pdf'}
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    def __init__(self, upload_folder: str = 'uploads'):
        self.upload_folder = upload_folder
        self._ensure_upload_folder()
    
    def _ensure_upload_folder(self):
        upload_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.upload_folder)
        os.makedirs(upload_path, exist_ok=True)
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in PDFValidatorService.ALLOWED_EXTENSIONS
    
    def save_uploaded_file(self, file, filename: Optional[str] = None) -> Dict:
        if not filename:
            filename = file.filename
        
        if not self.allowed_file(filename):
            return {
                'success': False,
                'error': 'Invalid file type. Only PDF files are allowed.'
            }
        
        secure_name = secure_filename(filename)
        
        base_name, extension = os.path.splitext(secure_name)
        counter = 1
        final_name = secure_name
        
        upload_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.upload_folder)
        file_path = os.path.join(upload_path, final_name)
        
        while os.path.exists(file_path):
            final_name = f"{base_name}_{counter}{extension}"
            file_path = os.path.join(upload_path, final_name)
            counter += 1
        
        try:
            file.save(file_path)
            
            return {
                'success': True,
                'filename': final_name,
                'file_path': os.path.join(self.upload_folder, final_name)
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error saving file: {str(e)}'
            }
    
    def validate_pdf(self, file_path: str) -> Dict:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)
        
        validation_result = PDFReader.validate_pdf_structure(full_path)
        
        if validation_result['is_valid']:
            try:
                metadata = PDFReader.get_metadata(full_path)
                validation_result['metadata'] = metadata
                
                text_preview = PDFReader.extract_text(full_path)
                validation_result['text_preview'] = text_preview[:500] if text_preview else ''
                
            except Exception as e:
                validation_result['errors'].append(f'Error extracting additional info: {str(e)}')
        
        return validation_result
    
    def process_and_validate(self, file) -> Dict:
        save_result = self.save_uploaded_file(file)
        
        if not save_result['success']:
            return {
                'success': False,
                'error': save_result['error']
            }
        
        validation_result = self.validate_pdf(save_result['file_path'])
        
        return {
            'success': True,
            'filename': save_result['filename'],
            'file_path': save_result['file_path'],
            'validation': validation_result
        }
