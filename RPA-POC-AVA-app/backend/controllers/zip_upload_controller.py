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
import re
from services.comprehensive_zip_processor_v2 import ComprehensiveZipProcessorV2
from services.database_service import DatabaseService
from services.session_manager import SessionManager
from services.file_validator import FileValidator
from services.logging_service import get_logger
from services.file_lifecycle_manager import FileLifecycleManager
from config.runtime import resolve_app_path
from werkzeug.utils import secure_filename

zip_bp = Blueprint('zip', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'uploads', 'zips')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize session manager
session_manager = SessionManager(
    resolve_app_path(os.getenv('SESSION_STORAGE_PATH'), 'data/sessions.json'),
    upload_folder=UPLOAD_FOLDER,
)

# Initialize file validator and logger
file_validator = FileValidator()
logger = get_logger()
lifecycle_manager = FileLifecycleManager()

# Initialize database service for validations (lazy initialization)
def get_db_service():
    """Get database service instance (created on demand)"""
    use_db = os.getenv('USE_SQL_SERVER', 'false').lower() == 'true'
    return DatabaseService(use_sql_server=use_db)

@zip_bp.route('/api/zip/test', methods=['GET'])
def test_endpoint():
    """Test endpoint to verify blueprint is registered"""
    print("=== TEST ENDPOINT HIT ===")
    return jsonify({'status': 'ok', 'message': 'ZIP blueprint is working'}), 200

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
    print("\n=== ZIP UPLOAD ENDPOINT HIT ===")
    print(f"Request method: {request.method}")
    print(f"Request files: {request.files}")
    
    # Get client IP for logging
    client_ip = logger.get_client_ip(request)
    user_agent = request.headers.get('User-Agent', 'unknown')
    
    try:
        if 'file' not in request.files:
            logger.log_error(None, 'VALIDATION_ERROR', 'No file provided', client_ip)
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.log_error(None, 'VALIDATION_ERROR', 'No file selected', client_ip)
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.zip'):
            logger.log_error(None, 'VALIDATION_ERROR', f'Invalid file type: {file.filename}', client_ip)
            return jsonify({'error': 'Invalid Application filename extension - Please use a zip file with a Funding Opportunity Number'}), 400
        
        # Validate ZIP filename format (must match HRSA-XX-YYY pattern)
        # Extract filename without extension
        filename_without_ext = file.filename.rsplit('.', 1)[0]
        # Pattern: HRSA-YY-NNN where YY is 2-digit year and NNN is 3-digit funding opportunity number
        hrsa_pattern = re.compile(r'^HRSA-\d{2}-\d{3}$', re.IGNORECASE)
        
        if not hrsa_pattern.match(filename_without_ext):
            error_msg = f'Invalid Application filename format. Expected format: HRSA-XX-YYY (e.g., HRSA-26-091). Received: {file.filename}'
            logger.log_error(None, 'FILENAME_VALIDATION_ERROR', error_msg, client_ip)
            return jsonify({'error': 'Invalid Application filename format - Please rename it to Funding Opportunity Number'}), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        # 200MB limit for zip files
        if file_size > 200 * 1024 * 1024:
            logger.log_error(None, 'FILE_SIZE_ERROR', f'File too large: {file_size} bytes', client_ip)
            return jsonify({'error': 'File size exceeds 200MB limit'}), 413
        
        # Generate unique ID and save file
        file_id = str(uuid.uuid4())
        safe_filename_str = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{safe_filename_str}")
        file.save(upload_path)
        
        # Log upload
        logger.log_upload(file_id, file.filename, file_size, client_ip, user_agent)
        
        # Validate ZIP file
        validation_result = file_validator.validate_zip_file(upload_path)
        if not validation_result['valid']:
            logger.log_security_event(
                'MALICIOUS_FILE_DETECTED',
                f"File: {file.filename}, Errors: {', '.join(validation_result['errors'])}",
                client_ip,
                severity='ERROR'
            )
            # Clean up invalid file
            try:
                os.remove(upload_path)
            except:
                pass
            return jsonify({
                'error': 'File validation failed',
                'details': validation_result['errors']
            }), 400
        
        # Process the zip file using Comprehensive Processor V2
        try:
            processor = ComprehensiveZipProcessorV2(get_db_service())
        except Exception as e:
            print(f"ERROR: Failed to initialize processor: {str(e)}")
            return jsonify({'error': f'Failed to initialize processor: {str(e)}'}), 500
        
        try:
            print(f"Processing ZIP: {upload_path}")
            result = processor.process_zip(upload_path)
            print(f"Processing complete. Success: {result.get('success')}")
            
            # Log validation results
            if result.get('sf424_validation'):
                sf424_result = 'PASS' if result['sf424_validation'].get('extracted') else 'FAIL'
                logger.log_validation(file_id, 'SF424', sf424_result, client_ip)
            
            if result.get('ppop_validation'):
                ppop_result = 'PASS' if result['ppop_validation'].get('extracted') else 'FAIL'
                logger.log_validation(file_id, 'PPOP', ppop_result, client_ip)
            
            if result.get('attachments'):
                page_limit_ok = result['attachments'].get('page_count_ok', True)
                page_result = 'PASS' if page_limit_ok else 'FAIL'
                logger.log_validation(file_id, 'PAGE_COUNT', page_result, client_ip)
            
            # Prepare response - include fields for display
            sf424_with_fields = result['sf424_validation'].copy() if result['sf424_validation'] else {}
            
            response = {
                'file_id': file_id,
                'file_name': file.filename,
                'original_filename': file.filename,
                'status': 'success' if result['success'] else 'failed',
                'sf424_validation': sf424_with_fields,
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
            
            # Attachment page count message (only attachments count, forms excluded)
            attachments = result['attachments']
            max_att_pages = attachments.get('max_attachment_page_count')
            att_pages = attachments.get('attachment_pages', 0)
            form_pages = attachments.get('form_pages', 0)
            
            if max_att_pages is not None:
                if attachments['page_count_ok']:
                    response['page_count_message'] = f"✓ Page count OK: {att_pages} pages (limit: {max_att_pages}) + {form_pages} form pages (excluded)"
                else:
                    response['page_count_message'] = f"⚠ Page count EXCEEDED: {att_pages} pages (limit: {max_att_pages}) + {form_pages} form pages (excluded)"
            else:
                response['page_count_message'] = f"Page count: {att_pages} attachment pages, {form_pages} form pages"
            
            # Store session data for chat to access
            session_data = {
                'file_id': file_id,
                'file_name': file.filename,
                'form_type': 'ZIP',
                'form_data': {
                    'sf424': result['sf424_validation'],
                    'ppop': result['ppop_validation'],
                    'attachments': result['attachments']
                },
                'validation_errors': result['errors']
            }
            session_manager.save_session(file_id, session_data)
            print(f"Session saved for file_id: {file_id}")
            
            # Set file expiration
            response['expires_at'] = lifecycle_manager.set_file_expiration(file_id)
            
            return jsonify(response), 200
            
        except Exception as e:
            print(f"ERROR during ZIP processing: {str(e)}")
            logger.log_error(file_id, 'PROCESSING_ERROR', str(e), client_ip)
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': f'ZIP processing failed: {str(e)}',
                'details': 'Check backend logs for full error'
            }), 500
            
        finally:
            # Optionally delete uploaded zip after processing
            # os.remove(upload_path)
            pass
        
    except Exception as e:
        print(f"ERROR in ZIP upload endpoint: {str(e)}")
        try:
            logger.log_error(None, 'UPLOAD_ERROR', str(e), client_ip)
        except:
            pass
        import traceback
        traceback.print_exc()
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
