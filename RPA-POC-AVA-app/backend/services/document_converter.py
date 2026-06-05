"""
Document Converter
Converts Office documents to PDF using LibreOffice
"""
import os
import subprocess
from typing import Optional

class DocumentConverter:
    """Convert various document formats to PDF using LibreOffice"""
    
    def __init__(self):
        """Initialize converter (detect LibreOffice)"""
        self.libreoffice_path = None
        self.has_libreoffice = self._check_libreoffice()
        
        if self.has_libreoffice:
            print("✓ LibreOffice detected - ready for conversions")
        else:
            print("⚠ LibreOffice not detected - document conversion unavailable")
    
    def _check_libreoffice(self) -> bool:
        """Check if LibreOffice is available"""
        # Try standard command first
        try:
            result = subprocess.run(
                ['libreoffice', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.libreoffice_path = 'libreoffice'
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # On Windows, check common installation paths
        if os.name == 'nt':
            possible_paths = [
                r'C:\Program Files\LibreOffice\program\soffice.exe',
                r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
                r'C:\Program Files\LibreOffice 7\program\soffice.exe',
                r'C:\Program Files\LibreOffice 24\program\soffice.exe',
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    # File exists, use it (don't check version - can fail silently)
                    self.libreoffice_path = path
                    print(f"✓ Found LibreOffice at: {path}")
                    return True
        
        return False
    
    def can_convert(self) -> bool:
        """Check if converter is available"""
        return self.has_libreoffice
    
    def convert_to_pdf(self, input_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Convert document to PDF using LibreOffice
        
        Supported formats:
        - Word: .doc, .docx, .rtf, .txt
        - Excel: .xls, .xlsx
        - Visio: .vsd, .vsdx
        - WordPerfect: .wpd (two-step conversion)
        
        Args:
            input_path: Path to input document
            output_dir: Directory for output PDF (default: same as input)
        
        Returns:
            Path to converted PDF or None if conversion failed
        """
        if not os.path.exists(input_path):
            print(f"❌ Input file not found: {input_path}")
            return None
        
        if not self.has_libreoffice:
            print(f"❌ LibreOffice not available for conversion")
            return None
        
        # Check file extension
        ext = os.path.splitext(input_path)[1].lower()
        supported_formats = ['.doc', '.docx', '.rtf', '.txt', '.xls', '.xlsx', '.vsd', '.vsdx', '.wpd']
        
        if ext not in supported_formats:
            print(f"❌ Unsupported file type: {ext}")
            return None
        
        # Determine output directory
        if output_dir is None:
            output_dir = os.path.dirname(input_path)
        
        # Special handling for .wpd files (two-step conversion)
        if ext == '.wpd':
            return self._convert_wpd_to_pdf(input_path, output_dir)
        
        # Standard conversion for other formats
        input_name = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{input_name}.pdf")
        return self._convert_with_libreoffice(input_path, output_dir, 'pdf')
    
    def _convert_with_libreoffice(self, input_path: str, output_dir: str, output_format: str) -> Optional[str]:
        """Convert using LibreOffice command line
        
        Args:
            input_path: Path to input file
            output_dir: Directory for output file
            output_format: Target format (pdf, docx, etc.)
        
        Returns:
            Path to converted file or None if conversion failed
        """
        try:
            # Get absolute paths
            input_path = os.path.abspath(input_path)
            input_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(output_dir, f"{input_name}.{output_format}")
            
            print(f"Converting with LibreOffice: {os.path.basename(input_path)} → {output_format}...")
            
            # Prepare subprocess arguments
            subprocess_kwargs = {
                'capture_output': True,
                'timeout': 60,
                'text': True
            }
            
            # On Windows, hide console window (0x08000000 = CREATE_NO_WINDOW)
            if os.name == 'nt':
                subprocess_kwargs['creationflags'] = 0x08000000
            
            result = subprocess.run(
                [
                    self.libreoffice_path,
                    '--headless',
                    '--invisible',
                    '--nodefault',
                    '--nofirststartwizard',
                    '--norestore',
                    '--convert-to', output_format,
                    '--outdir', output_dir,
                    input_path
                ],
                **subprocess_kwargs
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                print(f"✓ Converted: {os.path.basename(output_path)}")
                return output_path
            else:
                stderr = result.stderr.strip() if result.stderr else "Unknown error"
                print(f"❌ LibreOffice conversion failed: {stderr}")
                return None
        
        except subprocess.TimeoutExpired:
            print(f"❌ LibreOffice conversion timed out (>60 seconds)")
            return None
        except Exception as e:
            print(f"❌ LibreOffice conversion failed: {str(e)}")
            return None
    
    def _convert_wpd_to_pdf(self, wpd_path: str, output_dir: str) -> Optional[str]:
        """Convert WordPerfect (.wpd) to PDF using two-step conversion
        
        LibreOffice cannot directly convert .wpd to .pdf, so we use:
        Step 1: .wpd → .docx (intermediate format)
        Step 2: .docx → .pdf
        
        The intermediate .docx file is automatically cleaned up.
        
        Args:
            wpd_path: Path to .wpd file
            output_dir: Directory for output PDF
        
        Returns:
            Path to converted PDF or None if conversion failed
        """
        intermediate_path = None
        try:
            print(f"Two-step conversion for .wpd file: {os.path.basename(wpd_path)}")
            
            # Step 1: Convert .wpd → .docx
            print("  Step 1/2: Converting .wpd → .docx (intermediate)...")
            intermediate_path = self._convert_with_libreoffice(wpd_path, output_dir, 'docx')
            
            if not intermediate_path or not os.path.exists(intermediate_path):
                print("❌ Step 1 failed: Could not convert .wpd to .docx")
                return None
            
            print(f"  ✓ Intermediate file created: {os.path.basename(intermediate_path)}")
            
            # Step 2: Convert .docx → .pdf
            print("  Step 2/2: Converting .docx → .pdf...")
            pdf_path = self._convert_with_libreoffice(intermediate_path, output_dir, 'pdf')
            
            if not pdf_path or not os.path.exists(pdf_path):
                print("❌ Step 2 failed: Could not convert .docx to .pdf")
                return None
            
            print(f"✓ Two-step conversion complete: {os.path.basename(pdf_path)}")
            return pdf_path
        
        except Exception as e:
            print(f"❌ Two-step .wpd conversion failed: {str(e)}")
            return None
        
        finally:
            # Clean up intermediate .docx file
            if intermediate_path and os.path.exists(intermediate_path):
                try:
                    os.remove(intermediate_path)
                    print(f"  🧹 Cleaned up intermediate file: {os.path.basename(intermediate_path)}")
                except Exception as e:
                    print(f"  ⚠️  Could not delete intermediate file: {str(e)}")


# Test if converter is available
if __name__ == '__main__':
    converter = DocumentConverter()
    print(f"\nConverter available: {converter.can_convert()}")
    print(f"LibreOffice: {converter.has_libreoffice}")
