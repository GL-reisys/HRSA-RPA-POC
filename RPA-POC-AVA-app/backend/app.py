from flask import Flask, jsonify
from flask_cors import CORS
from controllers.document_controller import document_bp
import os
from config.runtime import get_allowed_origins, get_port, is_debug_enabled, resolve_app_path

def create_app():
    app = Flask(__name__)

    CORS(app, resources={
        r"/api/*": {
            "origins": get_allowed_origins(),
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type"],
        }
    })

    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
    app.config['UPLOAD_FOLDER'] = resolve_app_path(os.getenv('UPLOAD_DIR'), 'uploads')
    app.config['DATA_DIR'] = resolve_app_path(os.getenv('DATA_DIR'), 'database')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    app.register_blueprint(document_bp)

    @app.route('/')
    def index():
        return jsonify({
            'message': 'RPA POC AVA API',
            'version': '1.0.0',
            'endpoints': {
                'documents': '/api/documents',
                'upload': '/api/documents/upload'
            }
        })

    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'}), 200

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({'error': 'File size exceeds maximum limit of 50MB'}), 413

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=get_port(), debug=is_debug_enabled())
