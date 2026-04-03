from flask import Flask, jsonify
from flask_cors import CORS
from controllers.document_controller import document_bp
import os

app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://frontend:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type"]
    }
})

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

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

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
