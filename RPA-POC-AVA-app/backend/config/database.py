import json
import os
from datetime import datetime
from typing import List, Dict, Optional

class JSONDatabase:
    def __init__(self, db_path: str = 'database/data.json'):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            self._write_data({'documents': []})
    
    def _read_data(self) -> Dict:
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {'documents': []}
    
    def _write_data(self, data: Dict):
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_all_documents(self) -> List[Dict]:
        data = self._read_data()
        return data.get('documents', [])
    
    def get_document_by_id(self, doc_id: str) -> Optional[Dict]:
        documents = self.get_all_documents()
        for doc in documents:
            if doc.get('id') == doc_id:
                return doc
        return None
    
    def insert_document(self, document: Dict) -> Dict:
        data = self._read_data()
        documents = data.get('documents', [])
        
        if 'id' not in document:
            document['id'] = str(len(documents) + 1)
        
        if 'upload_date' not in document:
            document['upload_date'] = datetime.utcnow().isoformat()
        
        documents.append(document)
        data['documents'] = documents
        self._write_data(data)
        
        return document
    
    def update_document(self, doc_id: str, updates: Dict) -> Optional[Dict]:
        data = self._read_data()
        documents = data.get('documents', [])
        
        for i, doc in enumerate(documents):
            if doc.get('id') == doc_id:
                documents[i].update(updates)
                documents[i]['updated_date'] = datetime.utcnow().isoformat()
                data['documents'] = documents
                self._write_data(data)
                return documents[i]
        
        return None
    
    def delete_document(self, doc_id: str) -> bool:
        data = self._read_data()
        documents = data.get('documents', [])
        
        initial_length = len(documents)
        documents = [doc for doc in documents if doc.get('id') != doc_id]
        
        if len(documents) < initial_length:
            data['documents'] = documents
            self._write_data(data)
            return True
        
        return False
