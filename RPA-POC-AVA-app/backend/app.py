from dotenv import load_dotenv
import os

# Load environment variables FIRST before importing any services
load_dotenv()

def validate_environment():
    """Validate required environment variables are set"""
    required_vars = {
        'FLASK_ENV': 'development',
        'FLASK_DEBUG': '0'
    }

    for var, default in required_vars.items():
        if not os.getenv(var):
            os.environ[var] = default
            print(f"INFO: {var} not set, using default: {default}")

    # Optional but recommended variables
    if not os.getenv('AZURE_OPENAI_API_KEY') or not os.getenv('AZURE_OPENAI_ENDPOINT'):
        print("WARNING: Azure OpenAI credentials not configured. AI features will be limited.")
        print("Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env file for full functionality.")

validate_environment()

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from controllers.document_controller import document_bp
from controllers.pdf_validation_controller import pdf_bp
from controllers.zip_upload_controller import zip_bp
from services.session_manager import SessionManager
from apscheduler.schedulers.background import BackgroundScheduler
from config.runtime import get_allowed_origins, get_port, is_debug_enabled, resolve_app_path


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    CORS(app, resources={
        r"/api/*": {
            "origins": get_allowed_origins(),
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type"],
        },
        r"/static/*": {
            "origins": get_allowed_origins(),
            "methods": ["GET"],
            "allow_headers": ["Content-Type"],
        }
    })

    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
    app.config['UPLOAD_FOLDER'] = resolve_app_path(os.getenv('UPLOAD_DIR'), 'uploads')
    app.config['DATA_DIR'] = resolve_app_path(os.getenv('DATA_DIR'), 'database')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # Chat-flow PDFs land here (UUID-named). Created before the SessionManager
    # so the scheduled cleanup can read it.
    data_uploads = resolve_app_path(os.getenv('TEMP_UPLOAD_PATH'), 'data/uploads')
    os.makedirs(data_uploads, exist_ok=True)

    session_path = resolve_app_path(os.getenv('SESSION_STORAGE_PATH'), 'data/sessions.json')
    session_manager = SessionManager(session_path, upload_folder=data_uploads)

    scheduler = BackgroundScheduler()
    # Expire sessions every 15 min — also deletes the matching <file_id>.pdf.
    # With the default 30-min TTL, worst-case session retention is ~45 min.
    scheduler.add_job(
        func=session_manager.cleanup_expired_sessions,
        trigger='interval',
        minutes=15,
    )
    # Catch PDFs whose session record was lost (process kill, JSON corruption,
    # missed save). Only removes files older than the session timeout, so
    # in-flight uploads (upload → analyze) are not affected.
    scheduler.add_job(
        func=session_manager.sweep_orphan_uploads,
        trigger='interval',
        hours=1,
    )
    scheduler.start()

    app.register_blueprint(document_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(zip_bp)

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

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=get_port(), debug=is_debug_enabled())
