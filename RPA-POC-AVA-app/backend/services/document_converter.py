"""
Document Converter
Converts Office documents to PDF using MS Office (Windows COM) or LibreOffice
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

class DocumentConverter:
    """Convert various document formats to PDF"""
    
    def __init__(self):
        """Initialize converter (detect available tools)"""
        self.has_office = self._check_ms_office()
        self.has_libreoffice = self._check_libreoffice()
        
        if self.has_office:
            print("✓ MS Office detected - will use for conversions")
        elif self.has_libreoffice:
            print("✓ LibreOffice detected - will use for conversions")
        else:
            print("⚠ No conversion tool detected (MS Office or LibreOffice)")
    
    def _check_ms_office(self) -> bool:
        """Check if MS Office is available (Windows only)"""
        if sys.platform != 'win32':
            return False
        
        try:
            import win32com.client
            return True
        except ImportError:
            return False
    
    def _check_libreoffice(self) -> bool:
        """Check if LibreOffice is available"""
        try:
            result = subprocess.run(
                ['libreoffice', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def can_convert(self) -> bool:
        """Check if converter is available"""
        return self.has_office or self.has_libreoffice
    
    def convert_to_pdf(self, input_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Convert document to PDF
        
        Args:
            input_path: Path to input document
            output_dir: Directory for output PDF (default: same as input)
        
        Returns:
            Path to converted PDF or None if conversion failed
        """
        if not os.path.exists(input_path):
            print(f"❌ Input file not found: {input_path}")
            return None
        
        # Determine output path
        if output_dir is None:
            output_dir = os.path.dirname(input_path)
        
        input_name = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{input_name}.pdf")
        
        # Try conversion methods
        if self.has_office:
            return self._convert_with_office(input_path, output_path)
        elif self.has_libreoffice:
            return self._convert_with_libreoffice(input_path, output_path)
        else:
            print(f"❌ No conversion tool available")
            return None
    
    def _convert_with_office(self, input_path: str, output_path: str) -> Optional[str]:
        """Convert using MS Office COM automation (Windows)"""
        try:
            import win32com.client
            
            ext = os.path.splitext(input_path)[1].lower()
            
            # Convert Word documents
            if ext in ['.doc', '.docx', '.rtf', '.txt', '.wpd']:
                return self._convert_word(input_path, output_path)
            
            # Convert Excel documents
            elif ext in ['.xls', '.xlsx']:
                return self._convert_excel(input_path, output_path)
            
            # Convert Visio documents
            elif ext in ['.vsd', '.vsdx']:
                return self._convert_visio(input_path, output_path)
            
            else:
                print(f"❌ Unsupported file type: {ext}")
                return None
        
        except Exception as e:
            print(f"❌ Office conversion failed: {str(e)}")
            return None
    
    def _convert_word(self, input_path: str, output_path: str) -> Optional[str]:
        """Convert Word document to PDF"""
        try:
            import win32com.client
            
            # Get absolute paths
            input_path = os.path.abspath(input_path)
            output_path = os.path.abspath(output_path)
            
            print(f"Converting Word: {os.path.basename(input_path)}...")
            
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            
            try:
                doc = word.Documents.Open(input_path)
                doc.SaveAs(output_path, FileFormat=17)  # 17 = wdFormatPDF
                doc.Close()
                print(f"✓ Converted: {os.path.basename(output_path)}")
                return output_path
            finally:
                word.Quit()
        
        except Exception as e:
            print(f"❌ Word conversion failed: {str(e)}")
            return None
    
    def _convert_excel(self, input_path: str, output_path: str) -> Optional[str]:
        """Convert Excel document to PDF"""
        try:
            import win32com.client
            
            # Get absolute paths
            input_path = os.path.abspath(input_path)
            output_path = os.path.abspath(output_path)
            
            print(f"Converting Excel: {os.path.basename(input_path)}...")
            
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            
            try:
                workbook = excel.Workbooks.Open(input_path)
                workbook.ExportAsFixedFormat(0, output_path)  # 0 = xlTypePDF
                workbook.Close(SaveChanges=False)
                print(f"✓ Converted: {os.path.basename(output_path)}")
                return output_path
            finally:
                excel.Quit()
        
        except Exception as e:
            print(f"❌ Excel conversion failed: {str(e)}")
            return None
    
    def _convert_visio(self, input_path: str, output_path: str) -> Optional[str]:
        """Convert Visio document to PDF"""
        try:
            import win32com.client
            
            # Get absolute paths
            input_path = os.path.abspath(input_path)
            output_path = os.path.abspath(output_path)
            
            print(f"Converting Visio: {os.path.basename(input_path)}...")
            
            visio = win32com.client.Dispatch("Visio.Application")
            visio.Visible = False
            
            try:
                doc = visio.Documents.Open(input_path)
                doc.ExportAsFixedFormat(1, output_path, 0, 0)  # 1 = visFixedFormatPDF
                doc.Close()
                print(f"✓ Converted: {os.path.basename(output_path)}")
                return output_path
            finally:
                visio.Quit()
        
        except Exception as e:
            print(f"❌ Visio conversion failed: {str(e)}")
            return None
    
    def _convert_with_libreoffice(self, input_path: str, output_path: str) -> Optional[str]:
        """Convert using LibreOffice command line"""
        try:
            output_dir = os.path.dirname(output_path)
            
            print(f"Converting with LibreOffice: {os.path.basename(input_path)}...")
            
            result = subprocess.run(
                [
                    'libreoffice',
                    '--headless',
                    '--convert-to', 'pdf',
                    '--outdir', output_dir,
                    input_path
                ],
                capture_output=True,
                timeout=60,
                text=True
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                print(f"✓ Converted: {os.path.basename(output_path)}")
                return output_path
            else:
                print(f"❌ LibreOffice conversion failed: {result.stderr}")
                return None
        
        except Exception as e:
            print(f"❌ LibreOffice conversion failed: {str(e)}")
            return None


# Test if converter is available
if __name__ == '__main__':
    converter = DocumentConverter()
    print(f"\nConverter available: {converter.can_convert()}")
    print(f"MS Office: {converter.has_office}")
    print(f"LibreOffice: {converter.has_libreoffice}")
