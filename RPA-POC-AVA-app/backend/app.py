from dotenv import load_dotenv
import os
import sys

# Load environment variables FIRST before importing any services
load_dotenv()

def validate_environment():
    """Validate required environment variables are set"""
    required_vars = {
        'FLASK_ENV': 'development',
        'FLASK_DEBUG': '0'
    }
    
    missing_vars = []
    for var, default in required_vars.items():
        if not os.getenv(var):
            os.environ[var] = default
            print(f"INFO: {var} not set, using default: {default}")
    
    # Optional but recommended variables
    if not os.getenv('AZURE_OPENAI_API_KEY') or not os.getenv('AZURE_OPENAI_ENDPOINT'):
        print("WARNING: Azure OpenAI credentials not configured. AI features will be limited.")
        print("Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env file for full functionality.")

validate_environment()

from flask import Flask, jsonify
from flask_cors import CORS
from controllers.document_controller import document_bp
from controllers.pdf_validation_controller import pdf_bp
from services.session_manager import SessionManager
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://frontend:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type"]
    }
})

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

session_manager = SessionManager('data/sessions.json')

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=session_manager.cleanup_expired_sessions,
    trigger='interval',
    hours=1
)
scheduler.start()

app.register_blueprint(document_bp)
app.register_blueprint(pdf_bp)

@app.route('/')
def index():
    return jsonify({
        'message': 'Application Validation Assistant (AVA) API',
        'version': '1.0.0',
        'description': 'AI-powered SF-424 form validation assistant',
        'endpoints': {
            'pdf_upload': '/api/pdf/upload',
            'pdf_analyze': '/api/pdf/analyze',
            'chat': '/api/chat/message',
            'session_clear': '/api/session/clear',
            'health': '/api/health',
            'documents': '/api/documents'
        }
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'active_sessions': session_manager.get_session_count()
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File size exceeds maximum limit of 10MB'}), 413

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('data/uploads', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
