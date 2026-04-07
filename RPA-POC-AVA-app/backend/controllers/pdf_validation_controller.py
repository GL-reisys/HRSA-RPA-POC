from flask import Blueprint, request, jsonify
import os
import uuid
from services.xfa_pdf_extractor import XFAPdfExtractor
from services.form_mapper import FormMapper
from services.sf424_validator import SF424Validator
from services.ai_service import AIService
from services.session_manager import SessionManager
from datetime import datetime

pdf_bp = Blueprint('pdf', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

extractor = XFAPdfExtractor()
mapper = FormMapper()
validator = SF424Validator()
ai_service = AIService()
session_manager = SessionManager('data/sessions.json')

@pdf_bp.route('/api/pdf/upload', methods=['POST'])
def upload_pdf():
    """
    Upload PDF file and return file_id.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400
        
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File size exceeds 10MB limit'}), 413
        
        file_id = str(uuid.uuid4())
        
        upload_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
        file.save(upload_path)
        
        is_valid = validator.validate_pdf_structure(upload_path)
        
        if not is_valid:
            os.remove(upload_path)
            return jsonify({
                'error': 'Invalid PDF structure. Please upload a valid SF-424 form.',
                'status': 'invalid'
            }), 400
        
        return jsonify({
            'file_id': file_id,
            'file_name': file.filename,
            'file_size': file_size,
            'status': 'valid',
            'message': 'File uploaded successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@pdf_bp.route('/api/pdf/analyze', methods=['POST'])
def analyze_pdf():
    """
    Extract form fields, validate data, and get AI analysis.
    """
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        message = data.get('message', 'Please analyze this form.')
        
        if not file_id:
            return jsonify({'error': 'file_id is required'}), 400
        
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
        
        if not os.path.exists(pdf_path):
            return jsonify({'error': 'File not found'}), 404
        
        xfa_data = extractor.extract_form_fields(pdf_path)
        
        form_data = mapper.map_to_sf424(xfa_data)
        
        validation_errors = validator.validate_form_data(form_data)
        
        # Get funding opportunity to check type_of_app_by_fo for Grant Number display
        funding_opportunity = None
        fon = form_data.get('funding_opportunity_number')
        if fon:
            funding_opportunity = validator.db_service.get_funding_cycle_by_code(fon)
        
        # Build consistent status section
        app_type = form_data.get('application_type', 'Not specified')
        grant_number = form_data.get('federal_award_identifier')
        app_type_normalized = validator._normalize_application_type(app_type)
        
        if validation_errors:
            consistent_section = "<strong>Form Status: Not Ready for Submission to Grants.gov</strong><br><br>"
            
            # Add form fields section first
            consistent_section += "<strong>Form fields:</strong><br>"
            consistent_section += f"• <strong>UEI:</strong> {form_data.get('samuei', 'Not provided')}<br>"
            consistent_section += f"• <strong>Funding Opportunity:</strong> {fon or 'Not provided'}<br>"
            consistent_section += f"• <strong>Application Type:</strong> {app_type}<br>"
            
            # Show Grant Number only if NOT "New only" funding opportunity
            if (grant_number and 
                app_type_normalized in ['2', '3'] and
                funding_opportunity and 
                funding_opportunity.type_of_app_by_fo != 1):
                consistent_section += f"• <strong>Grant Number:</strong> {grant_number}<br>"
            
            consistent_section += "<br>"
            
            # Add validation issues after form fields
            consistent_section += "<strong>Validation issues found:</strong><br>"
            for error in validation_errors:
                consistent_section += f"• {error}<br>"
        else:
            consistent_section = "<strong>Form Status: Ready for Submission to Grants.gov</strong> ✅<br><br>"
            consistent_section += "All validation checks passed:<br>"
            consistent_section += f"• <strong>UEI:</strong> {form_data.get('samuei', 'Not provided')} — Verified<br>"
            consistent_section += f"• <strong>Funding Opportunity:</strong> {fon or 'Not provided'} — Entered<br>"
            consistent_section += f"• <strong>Application Type:</strong> {app_type}<br>"
            
            # Show Grant Number only if NOT "New only" funding opportunity
            if (grant_number and 
                app_type_normalized in ['2', '3'] and
                funding_opportunity and 
                funding_opportunity.type_of_app_by_fo != 1):
                consistent_section += f"• <strong>Grant Number:</strong> {grant_number}<br>"
        
        consistent_section += "<br>"
        
        # Get AI-generated troubleshooting guidance
        import asyncio
        ai_guidance = asyncio.run(ai_service.get_troubleshooting_guidance(form_data, validation_errors))
        
        # Combine consistent section + AI guidance
        ai_response = consistent_section + ai_guidance
        
        session_manager.save_session(file_id, {
            'file_name': data.get('file_name', 'unknown.pdf'),
            'uploaded_at': datetime.utcnow().isoformat() + 'Z',
            'form_data': form_data,
            'validation_errors': validation_errors,
            'chat_history': [
                {'role': 'user', 'content': message, 'timestamp': datetime.utcnow().isoformat() + 'Z'},
                {'role': 'assistant', 'content': ai_response, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
            ]
        })
        
        return jsonify({
            'file_id': file_id,
            'form_data': form_data,
            'validation_errors': validation_errors,
            'validation_status': 'PASSED' if len(validation_errors) == 0 else 'FAILED',
            'ai_response': ai_response,
            'metadata': xfa_data.get('metadata', {})
        }), 200
        
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@pdf_bp.route('/api/chat/message', methods=['POST'])
def chat_message():
    """
    Send chat message and get AI response with form context.
    """
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])
        
        if not file_id or not message:
            return jsonify({'error': 'file_id and message are required'}), 400
        
        session_data = session_manager.get_session(file_id)
        
        if not session_data:
            return jsonify({'error': 'Session not found or expired'}), 404
        
        import asyncio
        response = asyncio.run(ai_service.chat_completion(
            message=message,
            chat_history=chat_history,
            form_context={
                'form_data': session_data.get('form_data'),
                'validation_errors': session_data.get('validation_errors')
            }
        ))
        
        session_manager.update_chat_history(file_id, message, response)
        
        return jsonify({'response': response}), 200
        
    except Exception as e:
        print(f"Chat error: {str(e)}")
        return jsonify({
            'error': 'AI service unavailable',
            'details': str(e)
        }), 503

@pdf_bp.route('/api/session/clear', methods=['DELETE'])
def clear_session():
    """
    Clear session data and delete temporary files.
    """
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        
        if not file_id:
            return jsonify({'error': 'file_id is required'}), 400
        
        session_manager.clear_session(file_id)
        
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.pdf")
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        return jsonify({
            'status': 'success',
            'message': 'Session cleared successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Clear session failed: {str(e)}'}), 500

@pdf_bp.route('/api/health', methods=['GET'])
def health_check():
    """
    Check API health status.
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'services': {
            'ai_service': 'connected',
            'storage': 'available'
        }
    }), 200
