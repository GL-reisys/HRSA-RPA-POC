"""
Basic File Validation Service
Performs basic security checks on uploaded files
"""

import os
import zipfile
from pathlib import Path

# Try to import python-magic, but make it optional
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    print("WARNING: python-magic not installed. MIME type validation will be skipped.")
    print("To install: pip install python-magic python-magic-bin")


class FileValidator:
    """Basic file validation and security checks"""
    
    # Allowed file extensions
    ALLOWED_ZIP_EXTENSIONS = ['.zip']
    ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.rtf', '.txt', '.wpd', '.vsd']
    
    # Maximum file sizes (in bytes)
    MAX_ZIP_SIZE = 200 * 1024 * 1024  # 200 MB
    MAX_EXTRACTED_SIZE = 500 * 1024 * 1024  # 500 MB total extracted
    
    # Suspicious patterns
    SUSPICIOUS_EXTENSIONS = ['.exe', '.dll', '.bat', '.cmd', '.sh', '.ps1', '.vbs', '.js', '.jar', '.scr', '.msi']
    SUSPICIOUS_FILENAMES = ['__MACOSX', '.DS_Store', 'desktop.ini']
    
    def __init__(self):
        if HAS_MAGIC:
            self.mime = magic.Magic(mime=True)
        else:
            self.mime = None
    
    def validate_zip_file(self, file_path):
        """
        Validate ZIP file for security
        
        Args:
            file_path: Path to the ZIP file
            
        Returns:
            dict with 'valid' boolean and 'errors' list
        """
        errors = []
        
        try:
            file_path = Path(file_path)
            
            # Check file exists
            if not file_path.exists():
                return {'valid': False, 'errors': ['File does not exist']}
            
            # Check file extension
            if file_path.suffix.lower() not in self.ALLOWED_ZIP_EXTENSIONS:
                errors.append(f'Invalid file extension. Only .zip files are allowed.')
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.MAX_ZIP_SIZE:
                errors.append(f'File too large. Maximum size is {self.MAX_ZIP_SIZE // (1024*1024)} MB.')
            
            # Check MIME type (only if python-magic is available)
            if HAS_MAGIC and self.mime:
                try:
                    mime_type = self.mime.from_file(str(file_path))
                    if mime_type not in ['application/zip', 'application/x-zip-compressed']:
                        errors.append(f'Invalid file type. File appears to be {mime_type}, not a ZIP archive.')
                except Exception as e:
                    print(f"[VALIDATOR] Warning: Could not verify MIME type: {e}")
            else:
                print(f"[VALIDATOR] Skipping MIME type validation (python-magic not available)")
            
            # Check if valid ZIP file
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_file:
                    # Check for suspicious files
                    suspicious_files = []
                    total_extracted_size = 0
                    
                    for file_info in zip_file.infolist():
                        filename = file_info.filename
                        file_ext = Path(filename).suffix.lower()
                        
                        # Check for suspicious extensions
                        if file_ext in self.SUSPICIOUS_EXTENSIONS:
                            suspicious_files.append(f'{filename} (suspicious extension: {file_ext})')
                        
                        # Check for suspicious filenames
                        for sus_name in self.SUSPICIOUS_FILENAMES:
                            if sus_name in filename:
                                # Just warn, don't reject
                                print(f"[VALIDATOR] Warning: System file detected: {filename}")
                        
                        # Check extracted size
                        total_extracted_size += file_info.file_size
                    
                    if suspicious_files:
                        errors.append(f'Suspicious files detected: {", ".join(suspicious_files)}')
                    
                    if total_extracted_size > self.MAX_EXTRACTED_SIZE:
                        errors.append(f'Extracted content too large. Maximum is {self.MAX_EXTRACTED_SIZE // (1024*1024)} MB.')
                    
                    # Test ZIP integrity
                    bad_files = zip_file.testzip()
                    if bad_files:
                        errors.append(f'Corrupted files in ZIP: {bad_files}')
                        
            except zipfile.BadZipFile:
                errors.append('File is not a valid ZIP archive or is corrupted.')
            except Exception as e:
                errors.append(f'Error reading ZIP file: {str(e)}')
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}']
            }
    
    def validate_extracted_file(self, file_path):
        """
        Validate a file extracted from the ZIP
        
        Args:
            file_path: Path to the extracted file
            
        Returns:
            dict with 'valid' boolean and 'errors' list
        """
        errors = []
        
        try:
            file_path = Path(file_path)
            file_ext = file_path.suffix.lower()
            
            # Check for suspicious extensions
            if file_ext in self.SUSPICIOUS_EXTENSIONS:
                errors.append(f'File type not allowed: {file_ext}')
            
            # Check if extension is in allowed list (except system files)
            if file_ext and file_ext not in self.ALLOWED_DOCUMENT_EXTENSIONS:
                # Allow files without extensions (like manifest)
                if file_path.suffix:
                    print(f"[VALIDATOR] Warning: Unusual file extension: {file_ext}")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}']
            }
    
    def sanitize_filename(self, filename):
        """
        Sanitize filename to prevent path traversal attacks
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Remove leading dots
        filename = filename.lstrip('.')
        
        return filename
