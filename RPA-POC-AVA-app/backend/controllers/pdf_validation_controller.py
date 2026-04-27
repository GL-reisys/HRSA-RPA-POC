from flask import Blueprint, request, jsonify
import os
import uuid
import asyncio
from services.xfa_pdf_extractor import XFAPdfExtractor
from services.form_mapper import FormMapper
from services.sf424_validator import SF424Validator
from services.ai_service import AIService
from services.session_manager import SessionManager
from datetime import datetime

# Get backend URL from environment or use default
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5000')

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
        
        validation_errors_obj = validator.validate_form_data(form_data)
        
        # Generate AI guidance for each error dynamically
        
        for error_obj in validation_errors_obj:
            if error_obj.guidance is None and error_obj.ai_context:
                # Ask AI to explain the root cause and how to fix it
                try:
                    ai_guidance = asyncio.run(ai_service.chat_completion(
                        message=f"CRITICAL: Your response MUST start with the • character immediately. NO intro text, NO 'Fix these issues:', NO explanatory sentences. Just bullets. Combine related steps into concise bullets. Error context: {error_obj.ai_context}",
                        chat_history=[],
                        form_context={'form_data': form_data, 'validation_errors': [error_obj.ai_context]}
                    ))
                    error_obj.guidance = ai_guidance
                except Exception as e:
                    print(f"Failed to generate AI guidance: {str(e)}")
                    error_obj.guidance = None
        
        # Extract user messages for UI display
        validation_errors = [error.user_message for error in validation_errors_obj]
        
        # Extract AI context messages for AI model
        validation_errors_ai = [error.ai_context for error in validation_errors_obj]
        
        # Get funding opportunity to check type_of_app_by_fo for Grant Number display
        funding_opportunity = None
        fon = form_data.get('funding_opportunity_number')
        if fon:
            funding_opportunity = validator.db_service.get_funding_cycle_by_code(fon)
        
        # Build structured validation response
        app_type = form_data.get('application_type', 'Not specified')
        grant_number = form_data.get('federal_award_identifier')
        app_type_normalized = validator._normalize_application_type(app_type)
        
        if validation_errors:
            consistent_section = "<strong>Here is a quick summary:</strong><br><br>"
            consistent_section += "❌ <strong>Not ready for submission</strong><br><br>"
            
            # Determine which fields have errors by checking field_name
            error_field_names = set()
            for error_obj in validation_errors_obj:
                if error_obj.field_name:
                    error_field_names.add(error_obj.field_name.lower())
            
            # Define all major fields that are validated with their form data keys
            all_fields = [
                ('Organization Name', 'organization_name'),
                ('UEI', 'samuei'),
                ('EIN', 'employer_taxpayer_identification_number'),
                ('Application Type', 'application_type'),
                ('Funding Opportunity Number', 'funding_opportunity_number'),
                ('Project Title', 'project_title'),
                ('Contact Email', 'email'),
                ('Contact Phone', 'phone_number'),
            ]
            
            # Show fields that passed validation with green checkmarks
            passed_fields = []
            for field_name, form_key in all_fields:
                # Check if field has value and no errors
                if form_data.get(form_key) and field_name.lower() not in error_field_names:
                    passed_fields.append(field_name)
            
            if passed_fields:
                consistent_section += "<strong>Fields validated successfully:</strong><br>"
                # Display each field on a separate row
                for field in passed_fields:
                    consistent_section += f"&nbsp;&nbsp;&nbsp;✅ {field}<br>"
                consistent_section += "<br>"
            
            # Show fields that need fixes with cross marks
            error_fields = []
            for error_obj in validation_errors_obj:
                if error_obj.field_name:
                    error_fields.append(error_obj.field_name)
            
            if error_fields:
                consistent_section += "<strong>Need to Fix:</strong><br>"
                for field in error_fields:
                    consistent_section += f"&nbsp;&nbsp;&nbsp;❌ {field}<br>"
                consistent_section += "<br>"
            
            for idx, error_obj in enumerate(validation_errors_obj, 1):
                # Make field name bold in the message
                message = error_obj.user_message
                if error_obj.field_name:
                    message = message.replace(error_obj.field_name, f"<strong>{error_obj.field_name}</strong>")
                consistent_section += f"<strong style='color: #d32f2f;'>{idx}. {message}</strong><br>"
                
                # Add page and field location if available (make Page X, Field Y bold)
                if error_obj.field_location:
                    # Extract and bold Page X, Field Y pattern
                    import re
                    location_text = error_obj.field_location
                    # Bold "Page X, Field Y" part
                    location_text = re.sub(r'(Page \d+, Field \w+)', r'<strong>\1</strong>', location_text)
                    consistent_section += f"&nbsp;&nbsp;&nbsp;• {location_text}"
                    
                    # Add image if available (convert to absolute URL and make clickable)
                    if error_obj.image_path:
                        absolute_image_url = f"{BACKEND_URL}{error_obj.image_path}"
                        consistent_section += f'<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="{absolute_image_url}" target="_blank"><img src="{absolute_image_url}" alt="{error_obj.field_name} field" style="max-width: 500px; border: 1px solid #ddd; margin-top: 5px; border-radius: 4px; cursor: pointer;" title="Click to open full size"></a>'
                    
                    consistent_section += "<br>"
                
                # Add current value if available (bold)
                if error_obj.current_value:
                    consistent_section += f"&nbsp;&nbsp;&nbsp;• <strong>Current Value:</strong> {error_obj.current_value}<br>"
                
                # Add How to Fix with AI guidance (no bullet, no gap after label)
                if error_obj.guidance:
                    consistent_section += f"<br>&nbsp;&nbsp;&nbsp;<strong style='color: #1976d2;'>How to Fix:</strong><br>"
                    # Split by bullet points and format each with hanging indent
                    bullets = error_obj.guidance.split("• ")
                    for bullet in bullets:
                        if bullet.strip():  # Skip empty strings
                            # Remove <br> tags as we'll handle spacing
                            bullet_text = bullet.replace("<br>", "").strip()
                            # Use div with margin-left for bullet position and padding for hanging indent
                            consistent_section += f"<div style='margin-left: 20px; padding-left: 1.2em; text-indent: -1.2em; margin-bottom: 3px;'>• {bullet_text}</div>"
                    consistent_section += "<br>"
                
                consistent_section += "<br>"
        else:
            consistent_section = "<strong>Here is a summary:</strong><br><br>"
            consistent_section += "✅ <strong>Ready for submission to Grants.gov</strong><br><br>"
            
            # Show verified fields dynamically - same logic as failure case
            all_fields = [
                ('Organization Name', 'organization_name'),
                ('UEI', 'samuei'),
                ('EIN', 'employer_taxpayer_identification_number'),
                ('Application Type', 'application_type'),
                ('Funding Opportunity Number', 'funding_opportunity_number'),
                ('Project Title', 'project_title'),
                ('Contact Email', 'email'),
                ('Contact Phone', 'phone_number'),
            ]
            
            passed_fields = []
            for field_name, form_key in all_fields:
                # Check if field has value (no errors since validation passed)
                if form_data.get(form_key):
                    passed_fields.append(field_name)
            
            if passed_fields:
                consistent_section += "<strong>Fields validated successfully:</strong><br>"
                for field in passed_fields:
                    consistent_section += f"&nbsp;&nbsp;&nbsp;✅ {field}<br>"
                consistent_section += "<br>"
            
            consistent_section += "<strong>All validation checks passed:</strong><br>"
            consistent_section += f"✅ <strong>UEI:</strong> {form_data.get('samuei', 'Not provided')}<br>"
            if fon:
                consistent_section += f"✅ <strong>Funding Opportunity:</strong> {fon}<br>"
            consistent_section += f"✅ <strong>Application Type:</strong> {app_type}<br>"
            
            # Show Grant Number only if NOT "New only" funding opportunity
            if (grant_number and 
                app_type_normalized in ['2', '3'] and
                funding_opportunity and 
                funding_opportunity.type_of_app_by_fo != 1):
                consistent_section += f"✅ <strong>Grant Number:</strong> {grant_number}<br>"
        
        # No AI-generated guidance needed anymore
        # When validation fails: guidance is already embedded in each error
        # When validation passes: no additional guidance needed
        ai_response = consistent_section
        
        session_manager.save_session(file_id, {
            'file_name': data.get('file_name', 'unknown.pdf'),
            'uploaded_at': datetime.utcnow().isoformat() + 'Z',
            'form_data': form_data,
            'validation_errors': validation_errors,  # User messages for display
            'validation_errors_ai': validation_errors_ai,  # AI context for model
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
        
        # import asyncio
        response = asyncio.run(ai_service.chat_completion(
            message=message,
            chat_history=chat_history,
            form_context={
                'form_data': session_data.get('form_data'),
                'validation_errors': session_data.get('validation_errors_ai', session_data.get('validation_errors'))
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
