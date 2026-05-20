"""
ZIP Upload Controller - IDEAL SOLUTION
Handles zip file uploads containing:
- SF-424 form (validates UEI, Grant#, App Type, FON)
- PPOP form (validates congressional district, etc.)
- Attachments (counts pages, checks limits)
"""
from flask import Blueprint, request, jsonify, send_file
import os
import uuid
from services.comprehensive_zip_processor import ComprehensiveZipProcessor
from services.database_service import DatabaseService
from werkzeug.utils import secure_filename

zip_bp = Blueprint('zip', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'uploads', 'zips')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database service for validations (lazy initialization)
def get_db_service():
    """Get database service instance (created on demand)"""
    use_db = os.getenv('USE_SQL_SERVER', 'false').lower() == 'true'
    return DatabaseService(use_sql_server=use_db)

@zip_bp.route('/api/zip/upload', methods=['POST'])
def upload_zip():
    """
    Upload a zip file - IDEAL SOLUTION
    
    Expected form data:
        - file: ZIP file containing SF-424, PPOP, and attachments
    
    Returns:
        JSON with:
        - SF-424 validation results
        - PPOP validation results
        - Attachment page count and validation
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.zip'):
            return jsonify({'error': 'Invalid file type. Only ZIP files are allowed.'}), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        # 200MB limit for zip files
        if file_size > 200 * 1024 * 1024:
            return jsonify({'error': 'File size exceeds 200MB limit'}), 413
        
        # Generate unique ID and save file
        file_id = str(uuid.uuid4())
        safe_filename_str = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{safe_filename_str}")
        file.save(upload_path)
        
        # Process the zip file using Comprehensive Processor
        processor = ComprehensiveZipProcessor(get_db_service())
        
        try:
            result = processor.process_zip(upload_path)
            
            # Prepare response
            response = {
                'file_id': file_id,
                'original_filename': file.filename,
                'status': 'success' if result['success'] else 'failed',
                'sf424_validation': result['sf424_validation'],
                'ppop_validation': result['ppop_validation'],
                'attachments': result['attachments'],
                'errors': result['errors']
            }
            
            # Add user-friendly messages
            if result['sf424_validation']:
                sf424 = result['sf424_validation']
                if sf424.get('extracted'):
                    sf424_msg = f"SF-424 extracted via {sf424.get('extraction_method', 'unknown')}"
                    if sf424.get('errors'):
                        sf424_msg += f" - {len(sf424['errors'])} validation errors found"
                    else:
                        sf424_msg += " - All validations passed ✓"
                    response['sf424_message'] = sf424_msg
                else:
                    response['sf424_message'] = "SF-424 not found or could not be extracted"
            
            if result['ppop_validation']:
                ppop = result['ppop_validation']
                if ppop.get('extracted'):
                    ppop_msg = f"PPOP extracted via {ppop.get('extraction_method', 'unknown')}"
                    if ppop.get('validated'):
                        if ppop.get('errors'):
                            ppop_msg += f" - {len(ppop['errors'])} validation errors found"
                        else:
                            ppop_msg += " - All validations passed ✓"
                    response['ppop_message'] = ppop_msg
                else:
                    response['ppop_message'] = ppop.get('message', 'PPOP not found')
            
            # Attachment page count message
            attachments = result['attachments']
            if attachments['page_count_ok']:
                response['page_count_message'] = f"✓ Page count OK: {attachments['total_pages']} pages (limit: 150)"
            else:
                response['page_count_message'] = f"⚠ Page count EXCEEDED: {attachments['total_pages']} pages (limit: 150)"
            
            return jsonify(response), 200
            
        finally:
            # Optionally delete uploaded zip after processing
            # os.remove(upload_path)
            pass
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@zip_bp.route('/api/zip/download/<file_id>', methods=['GET'])
def download_converted_zip(file_id):
    """
    Download the converted/processed zip file
    
    Args:
        file_id: The file ID from upload
    
    Returns:
        ZIP file download
    """
    try:
        # Find the output zip file
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith(f"output_{file_id}_"):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                return send_file(
                    file_path,
                    mimetype='application/zip',
                    as_attachment=True,
                    download_name=filename.replace(f"output_{file_id}_", "")
                )
        
        return jsonify({'error': 'File not found'}), 404
        
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500


@zip_bp.route('/api/zip/info/<file_id>', methods=['GET'])
def get_zip_info(file_id):
    """
    Get information about a processed zip file
    
    Args:
        file_id: The file ID from upload
    
    Returns:
        JSON with file information
    """
    try:
        # This would typically query a database
        # For now, return a placeholder
        return jsonify({
            'file_id': file_id,
            'status': 'processed',
            'message': 'Use the upload response for detailed information'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Info retrieval failed: {str(e)}'}), 500
