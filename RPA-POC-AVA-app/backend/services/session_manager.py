import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from threading import Lock

class SessionManager:
    """
    Manages session data in JSON file for POC.
    Thread-safe file operations.
    """
    
    def __init__(self, json_file: str = 'data/sessions.json'):
        """
        Initialize session manager.
        
        Args:
            json_file: Path to JSON storage file
        """
        self.json_file = json_file
        self.lock = Lock()
        self.session_timeout_hours = 4
        
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        
        if not os.path.exists(json_file):
            self._save_sessions({'sessions': {}})
    
    def save_session(self, file_id: str, data: Dict[str, Any]) -> bool:
        """
        Save or update session data.
        
        Args:
            file_id: Unique file identifier (UUID)
            data: Session data dictionary
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                sessions = self._load_sessions()
                
                expires_at = datetime.utcnow() + timedelta(hours=self.session_timeout_hours)
                
                session_data = {
                    'file_id': file_id,
                    'file_name': data.get('file_name', 'unknown.pdf'),
                    'uploaded_at': data.get('uploaded_at', datetime.utcnow().isoformat() + 'Z'),
                    'expires_at': expires_at.isoformat() + 'Z',
                    'form_data': data.get('form_data', {}),
                    'validation_errors': data.get('validation_errors', []),
                    'chat_history': data.get('chat_history', [])
                }
                
                sessions['sessions'][file_id] = session_data
                
                self._save_sessions(sessions)
                
                print(f"Session saved: {file_id}, expires at {expires_at}")
                return True
                
        except Exception as e:
            print(f"Error saving session: {str(e)}")
            return False
    
    def get_session(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data by file_id.
        
        Args:
            file_id: Unique file identifier
        
        Returns:
            Session data dictionary or None if not found/expired
        """
        try:
            with self.lock:
                sessions = self._load_sessions()
                session = sessions['sessions'].get(file_id)
                
                if not session:
                    print(f"Session not found: {file_id}")
                    return None
                
                expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', ''))
                if datetime.utcnow() > expires_at:
                    print(f"Session expired: {file_id}")
                    self.clear_session(file_id)
                    return None
                
                return session
                
        except Exception as e:
            print(f"Error retrieving session: {str(e)}")
            return None
    
    def update_chat_history(self, file_id: str, user_message: str, ai_response: str) -> bool:
        """
        Append messages to chat history.
        
        Args:
            file_id: Unique file identifier
            user_message: User's message
            ai_response: AI's response
        
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.get_session(file_id)
            
            if not session:
                print(f"Cannot update chat history: session not found {file_id}")
                return False
            
            timestamp = datetime.utcnow().isoformat() + 'Z'
            
            if 'chat_history' not in session:
                session['chat_history'] = []
            
            session['chat_history'].append({
                'role': 'user',
                'content': user_message,
                'timestamp': timestamp
            })
            
            session['chat_history'].append({
                'role': 'assistant',
                'content': ai_response,
                'timestamp': timestamp
            })
            
            return self.save_session(file_id, session)
            
        except Exception as e:
            print(f"Error updating chat history: {str(e)}")
            return False
    
    def clear_session(self, file_id: str) -> bool:
        """
        Delete session data.
        
        Args:
            file_id: Unique file identifier
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                sessions = self._load_sessions()
                
                if file_id in sessions['sessions']:
                    del sessions['sessions'][file_id]
                    self._save_sessions(sessions)
                    print(f"Session cleared: {file_id}")
                    return True
                else:
                    print(f"Session not found for clearing: {file_id}")
                    return False
                    
        except Exception as e:
            print(f"Error clearing session: {str(e)}")
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove all expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            with self.lock:
                sessions = self._load_sessions()
                now = datetime.utcnow()
                
                expired_ids = []
                
                for file_id, session in sessions['sessions'].items():
                    expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', ''))
                    if now > expires_at:
                        expired_ids.append(file_id)
                
                for file_id in expired_ids:
                    del sessions['sessions'][file_id]
                
                if expired_ids:
                    self._save_sessions(sessions)
                    print(f"Cleaned up {len(expired_ids)} expired sessions")
                
                return len(expired_ids)
                
        except Exception as e:
            print(f"Error cleaning up sessions: {str(e)}")
            return 0
    
    def get_session_count(self) -> int:
        """
        Get count of active sessions.
        
        Returns:
            Number of active sessions
        """
        try:
            sessions = self._load_sessions()
            return len(sessions['sessions'])
        except Exception as e:
            print(f"Error getting session count: {str(e)}")
            return 0
    
    def _load_sessions(self) -> Dict[str, Any]:
        """Load sessions from JSON file."""
        try:
            if not os.path.exists(self.json_file):
                return {'sessions': {}}
            
            with open(self.json_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {self.json_file}, resetting")
            return {'sessions': {}}
        except Exception as e:
            print(f"Error loading sessions: {str(e)}")
            return {'sessions': {}}
    
    def _save_sessions(self, sessions: Dict[str, Any]):
        """Save sessions to JSON file."""
        try:
            with open(self.json_file, 'w') as f:
                json.dump(sessions, f, indent=2)
        except Exception as e:
            print(f"Error saving sessions: {str(e)}")
            raise
