import json
import os

def initialize_database():
    db_path = os.path.join(os.path.dirname(__file__), 'data.json')
    
    initial_structure = {
        'documents': []
    }
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with open(db_path, 'w') as f:
        json.dump(initial_structure, f, indent=2)
    
    print(f"Database initialized at {db_path}")

if __name__ == '__main__':
    initialize_database()
