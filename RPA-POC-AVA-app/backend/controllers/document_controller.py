from flask import Blueprint, request, jsonify
from config.database import JSONDatabase
from services.pdf_validator import PDFValidatorService
import os

document_bp = Blueprint('documents', __name__, url_prefix='/api/documents')

db = JSONDatabase()
pdf_service = PDFValidatorService()

@document_bp.route('/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    result = pdf_service.process_and_validate(file)
    
    if not result['success']:
        return jsonify({'error': result['error']}), 400
    
    document = {
        'filename': result['filename'],
        'file_path': result['file_path'],
        'status': 'validated' if result['validation']['is_valid'] else 'invalid',
        'validation_results': result['validation']
    }
    
    saved_document = db.insert_document(document)
    
    return jsonify({
        'message': 'Document uploaded and validated successfully',
        'document': saved_document
    }), 201

@document_bp.route('', methods=['GET'])
def get_all_documents():
    documents = db.get_all_documents()
    return jsonify({'documents': documents}), 200

@document_bp.route('/<doc_id>', methods=['GET'])
def get_document(doc_id):
    document = db.get_document_by_id(doc_id)
    
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify({'document': document}), 200

@document_bp.route('/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    document = db.get_document_by_id(doc_id)
    
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    
    file_path = document.get('file_path')
    if file_path:
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception as e:
                print(f"Error deleting file: {str(e)}")
    
    success = db.delete_document(doc_id)
    
    if success:
        return jsonify({'message': 'Document deleted successfully'}), 200
    else:
        return jsonify({'error': 'Failed to delete document'}), 500

@document_bp.route('/<doc_id>', methods=['PUT'])
def update_document(doc_id):
    document = db.get_document_by_id(doc_id)
    
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    
    updates = request.get_json()
    
    allowed_updates = ['status', 'validation_results']
    filtered_updates = {k: v for k, v in updates.items() if k in allowed_updates}
    
    updated_document = db.update_document(doc_id, filtered_updates)
    
    return jsonify({
        'message': 'Document updated successfully',
        'document': updated_document
    }), 200
