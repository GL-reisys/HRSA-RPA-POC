from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config.database import JSONDatabase

def seed_sample_data():
    db = JSONDatabase()
    
    sample_documents = [
        {
            'id': '1',
            'filename': 'sample_report_2024.pdf',
            'upload_date': (datetime.utcnow() - timedelta(days=5)).isoformat(),
            'status': 'validated',
            'validation_results': {
                'is_valid': True,
                'file_size': 245678,
                'page_count': 12,
                'has_text': True,
                'errors': []
            },
            'file_path': 'uploads/sample_report_2024.pdf'
        },
        {
            'id': '2',
            'filename': 'invoice_march.pdf',
            'upload_date': (datetime.utcnow() - timedelta(days=2)).isoformat(),
            'status': 'validated',
            'validation_results': {
                'is_valid': True,
                'file_size': 89234,
                'page_count': 3,
                'has_text': True,
                'errors': []
            },
            'file_path': 'uploads/invoice_march.pdf'
        }
    ]
    
    for doc in sample_documents:
        db.insert_document(doc)
    
    print(f"Seeded {len(sample_documents)} sample documents")

if __name__ == '__main__':
    seed_sample_data()
