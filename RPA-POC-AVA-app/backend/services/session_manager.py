import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from threading import Lock

# UUIDv4 pattern used for filenames in the chat upload flow (<file_id>.pdf).
# Constrained so the orphan sweep never deletes anything but uploads it owns.
_UPLOAD_FILENAME_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$',
    re.IGNORECASE,
)


class SessionManager:
    """
    Manages session data in JSON file for POC.
    Thread-safe file operations.
    """

    # Default session lifetime if SESSION_TIMEOUT_HOURS env var is unset
    # or invalid. 0.5 = 30 minutes. Tightened from 4h to minimize PII
    # retention on disk.
    DEFAULT_SESSION_TIMEOUT_HOURS = 0.5

    def __init__(
        self,
        json_file: str = 'data/sessions.json',
        upload_folder: Optional[str] = None,
        session_timeout_hours: Optional[float] = None,
    ):
        """
        Initialize session manager.

        Args:
            json_file: Path to JSON storage file.
            upload_folder: Directory where uploaded PDFs are stored.
                When set, cleanup_expired_sessions also removes the
                matching <file_id>.pdf, and sweep_orphan_uploads can run.
            session_timeout_hours: Override session TTL in hours (fractions
                allowed, e.g. 0.5 = 30 min). If None, falls back to the
                SESSION_TIMEOUT_HOURS env var, then to DEFAULT_SESSION_TIMEOUT_HOURS.
        """
        self.json_file = json_file
        self.upload_folder = upload_folder
        self.lock = Lock()
        self.session_timeout_hours = self._resolve_timeout(session_timeout_hours)

        os.makedirs(os.path.dirname(json_file), exist_ok=True)

        if not os.path.exists(json_file):
            self._save_sessions({'sessions': {}})

    @classmethod
    def _resolve_timeout(cls, override: Optional[float]) -> float:
        if override is not None:
            return float(override)
        raw = os.getenv('SESSION_TIMEOUT_HOURS')
        if raw:
            try:
                value = float(raw)
                if value > 0:
                    return value
            except ValueError:
                pass
        return cls.DEFAULT_SESSION_TIMEOUT_HOURS
    
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
        Remove all expired sessions and delete their associated upload files
        (when an upload_folder is configured).

        Returns:
            Number of sessions cleaned up.
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

                deleted_files = 0
                for file_id in expired_ids:
                    del sessions['sessions'][file_id]
                    if self._delete_upload_file(file_id):
                        deleted_files += 1

                if expired_ids:
                    self._save_sessions(sessions)
                    print(
                        f"Cleaned up {len(expired_ids)} expired sessions "
                        f"({deleted_files} upload file(s) removed)"
                    )

                return len(expired_ids)

        except Exception as e:
            print(f"Error cleaning up sessions: {str(e)}")
            return 0

    def sweep_orphan_uploads(self) -> int:
        """
        Delete <uuid>.pdf files in the upload folder that have no matching
        active session record and are older than the session timeout.

        The mtime guard protects in-flight uploads: the chat flow saves the
        PDF in /api/pdf/upload but doesn't create a session record until
        /api/pdf/analyze finishes, so a brand-new file may legitimately
        have no session yet.

        Returns:
            Number of orphan files deleted.
        """
        if not self.upload_folder:
            return 0

        try:
            with self.lock:
                sessions = self._load_sessions()
                active_ids = set(sessions['sessions'].keys())

            if not os.path.isdir(self.upload_folder):
                return 0

            cutoff_ts = (
                datetime.utcnow() - timedelta(hours=self.session_timeout_hours)
            ).timestamp()

            removed = 0
            for entry in os.listdir(self.upload_folder):
                if not _UPLOAD_FILENAME_PATTERN.match(entry):
                    continue

                file_id = entry[:-4]  # strip .pdf
                if file_id in active_ids:
                    continue

                path = os.path.join(self.upload_folder, entry)
                try:
                    if os.path.getmtime(path) > cutoff_ts:
                        # Too recent to be a true orphan; could still be
                        # mid-upload/analyze before the session is saved.
                        continue
                    os.remove(path)
                    removed += 1
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"Error removing orphan upload {path}: {str(e)}")

            if removed:
                print(
                    f"Orphan sweep removed {removed} upload(s) from "
                    f"{self.upload_folder}"
                )
            return removed

        except Exception as e:
            print(f"Error during orphan sweep: {str(e)}")
            return 0

    def _delete_upload_file(self, file_id: str) -> bool:
        """Delete <upload_folder>/<file_id>.pdf if it exists. Best-effort."""
        if not self.upload_folder:
            return False

        pdf_path = os.path.join(self.upload_folder, f"{file_id}.pdf")
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                return True
        except Exception as e:
            print(f"Error deleting upload file {pdf_path}: {str(e)}")
        return False
    
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
