"""
File Lifecycle Management Service
Handles automatic cleanup of uploaded files based on expiration timestamp
"""

import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading


class FileLifecycleManager:
    def __init__(self, uploads_dir='uploads', sessions_file='data/sessions.json', ttl_hours=24):
        """
        Initialize the file lifecycle manager
        
        Args:
            uploads_dir: Directory where uploaded files are stored
            sessions_file: Path to sessions.json
            ttl_hours: Time to live for uploaded files in hours (default: 24)
        """
        self.uploads_dir = Path(uploads_dir)
        self.sessions_file = Path(sessions_file)
        self.ttl_hours = ttl_hours
        self.cleanup_interval = 3600  # Run cleanup every hour
        
    def set_file_expiration(self, file_id):
        """
        Set expiration timestamp for a file
        
        Args:
            file_id: The file identifier
            
        Returns:
            ISO formatted expiration datetime
        """
        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)
        return expires_at.isoformat()
    
    def is_expired(self, expires_at_str):
        """
        Check if a file has expired
        
        Args:
            expires_at_str: ISO formatted expiration datetime string
            
        Returns:
            True if expired, False otherwise
        """
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.now() > expires_at
        except (ValueError, TypeError):
            # If no valid expiration date, consider it expired
            return True
    
    def cleanup_expired_files(self):
        """
        Remove expired files from both filesystem and sessions.json
        """
        try:
            if not self.sessions_file.exists():
                return
            
            with open(self.sessions_file, 'r') as f:
                sessions = json.load(f)
            
            sessions_to_keep = {}
            files_removed = 0
            
            for file_id, session_data in sessions.items():
                expires_at = session_data.get('expires_at')
                
                if expires_at and self.is_expired(expires_at):
                    # Remove file directory
                    file_dir = self.uploads_dir / file_id
                    if file_dir.exists():
                        try:
                            import shutil
                            shutil.rmtree(file_dir)
                            files_removed += 1
                            print(f"[CLEANUP] Removed expired file: {file_id}")
                        except Exception as e:
                            print(f"[CLEANUP] Error removing {file_id}: {e}")
                else:
                    # Keep non-expired sessions
                    sessions_to_keep[file_id] = session_data
            
            # Update sessions.json
            if files_removed > 0:
                with open(self.sessions_file, 'w') as f:
                    json.dump(sessions_to_keep, f, indent=2)
                print(f"[CLEANUP] Removed {files_removed} expired files")
            
        except Exception as e:
            print(f"[CLEANUP] Error during cleanup: {e}")
    
    def start_cleanup_scheduler(self):
        """
        Start background thread to periodically cleanup expired files
        """
        def cleanup_loop():
            while True:
                time.sleep(self.cleanup_interval)
                self.cleanup_expired_files()
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        print(f"[LIFECYCLE] File cleanup scheduler started (TTL: {self.ttl_hours} hours)")
    
    def force_cleanup_file(self, file_id):
        """
        Immediately remove a specific file
        
        Args:
            file_id: The file identifier to remove
        """
        try:
            # Remove from filesystem
            file_dir = self.uploads_dir / file_id
            if file_dir.exists():
                import shutil
                shutil.rmtree(file_dir)
                print(f"[LIFECYCLE] Force removed file: {file_id}")
            
            # Remove from sessions
            if self.sessions_file.exists():
                with open(self.sessions_file, 'r') as f:
                    sessions = json.load(f)
                
                if file_id in sessions:
                    del sessions[file_id]
                    with open(self.sessions_file, 'w') as f:
                        json.dump(sessions, f, indent=2)
                        
        except Exception as e:
            print(f"[LIFECYCLE] Error force removing {file_id}: {e}")
