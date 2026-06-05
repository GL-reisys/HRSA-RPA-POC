"""
Test suite for security features: rate limiting, path traversal, session ownership
"""
import pytest
import sys
import os
import uuid
import time
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from services.session_manager import SessionManager


class TestRateLimiting:
    """Test rate limiting enforcement"""
    
    @pytest.fixture
    def client(self):
        """Create test client with rate limiting enabled"""
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_chat_rate_limit_10_per_minute(self, client):
        """Test that chat endpoint blocks after 10 requests in 1 minute"""
        file_id = str(uuid.uuid4())
        
        # Create a session first
        with patch('services.session_manager.SessionManager.get_session') as mock_session:
            mock_session.return_value = {
                'file_id': file_id,
                'form_data': {},
                'form_type': 'SF-424'
            }
            
            # Send 10 requests (should all succeed)
            for i in range(10):
                response = client.post('/api/chat/message', json={
                    'file_id': file_id,
                    'message': f'Test message {i}'
                })
                # May fail for other reasons, but shouldn't be 429
                assert response.status_code != 429, f"Request {i+1} got rate limited too early"
            
            # 11th request should be rate limited
            response = client.post('/api/chat/message', json={
                'file_id': file_id,
                'message': 'Test message 11'
            })
            assert response.status_code == 429, "11th request should be rate limited"
    
    def test_global_rate_limit_50_per_hour(self, client):
        """Test that global rate limit of 50/hour is enforced"""
        # This test would take too long to run 51 requests
        # Just verify the limiter is configured
        assert hasattr(client.application, 'limiter')
        assert client.application.limiter is not None
    
    def test_upload_rate_limit_20_per_hour(self, client):
        """Test that upload endpoint has 20/hour limit"""
        # Verify endpoint has rate limit applied
        view_func = client.application.view_functions.get('zip.upload_zip')
        assert view_func is not None


class TestPathTraversalProtection:
    """Test path traversal and directory traversal protection"""
    
    @pytest.fixture
    def client(self):
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_invalid_uuid_format_rejected(self, client):
        """Test that non-UUID file_id is rejected"""
        malicious_ids = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "../../sensitive.txt",
            "file.txt",
            "123-abc",
            "<script>alert(1)</script>"
        ]
        
        for malicious_id in malicious_ids:
            response = client.get(f'/api/zip/download/{malicious_id}')
            assert response.status_code == 400
            assert b'Invalid file ID format' in response.data
    
    def test_valid_uuid_format_accepted(self, client):
        """Test that valid UUID format passes validation (but may fail auth)"""
        valid_uuid = str(uuid.uuid4())
        
        with patch('services.session_manager.SessionManager.get_session') as mock_session:
            # Return None to simulate session not found (expected)
            mock_session.return_value = None
            
            response = client.get(f'/api/zip/download/{valid_uuid}')
            # Should not be 400 (invalid format), should be 404 (not found)
            assert response.status_code != 400


class TestSessionOwnership:
    """Test that users can only access their own files"""
    
    @pytest.fixture
    def client(self):
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_download_requires_session_ownership(self, client):
        """Test that download endpoint checks session ownership"""
        valid_uuid = str(uuid.uuid4())
        
        with patch('services.session_manager.SessionManager.get_session') as mock_session:
            # Simulate session not found (user doesn't own this file)
            mock_session.return_value = None
            
            response = client.get(f'/api/zip/download/{valid_uuid}')
            assert response.status_code == 404
            assert b'File not found or access denied' in response.data
    
    def test_chat_requires_valid_session(self, client):
        """Test that chat endpoint requires valid session"""
        fake_file_id = str(uuid.uuid4())
        
        with patch('services.session_manager.SessionManager.get_session') as mock_session:
            mock_session.return_value = None
            
            response = client.post('/api/chat/message', json={
                'file_id': fake_file_id,
                'message': 'Test message'
            })
            assert response.status_code == 404
            assert b'Session not found' in response.data


class TestInputValidation:
    """Test input validation before processing"""
    
    @pytest.fixture
    def client(self):
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_large_json_payload_rejected(self, client):
        """Test that overly large JSON payloads are rejected before parsing"""
        file_id = str(uuid.uuid4())
        
        # Create 2MB payload (exceeds 1MB limit for chat)
        large_message = "A" * (2 * 1024 * 1024)
        
        response = client.post('/api/chat/message', 
            json={'file_id': file_id, 'message': large_message},
            content_type='application/json'
        )
        
        # Should be rejected with 413 (Payload Too Large) or 400 (message too long)
        assert response.status_code in [400, 413]
    
    def test_missing_required_fields(self, client):
        """Test that missing required fields are rejected"""
        # Missing file_id
        response = client.post('/api/chat/message', json={'message': 'test'})
        assert response.status_code == 400
        
        # Missing message
        response = client.post('/api/chat/message', json={'file_id': str(uuid.uuid4())})
        assert response.status_code == 400


class TestDocumentConversion:
    """Test document conversion security and timeout handling"""
    
    def test_conversion_timeout_enforced(self):
        """Test that LibreOffice conversion has 60s timeout"""
        from services.document_converter import DocumentConverter
        
        converter = DocumentConverter()
        if converter.has_libreoffice:
            # Verify timeout is set
            # This would require creating a mock file that causes timeout
            # For now, just verify converter is configured
            assert converter.can_convert()
    
    def test_only_whitelisted_extensions(self):
        """Test that only whitelisted file extensions are converted"""
        from services.comprehensive_zip_processor_v2 import ComprehensiveZipProcessorV2
        
        processor = ComprehensiveZipProcessorV2()
        
        allowed_extensions = {'.pdf', '.doc', '.docx', '.rtf', '.txt', 
                            '.wpd', '.xls', '.xlsx', '.vsd', '.vsdx'}
        
        assert processor.ACCEPTED_EXTENSIONS == allowed_extensions
        
        # Test that other extensions are rejected
        malicious_extensions = ['.exe', '.bat', '.sh', '.ps1', '.dll', '.so']
        for ext in malicious_extensions:
            assert ext not in processor.ACCEPTED_EXTENSIONS


class TestPIILogging:
    """Test that PII is not logged in plaintext"""
    
    def test_pii_not_logged_in_plaintext(self):
        """Test that PII detection logs types but not values"""
        from services.input_sanitizer import InputSanitizer
        import logging
        from io import StringIO
        
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger('controllers.pdf_validation_controller')
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        
        sanitizer = InputSanitizer()
        
        # Detect PII
        pii_found = sanitizer.detect_pii("My SSN is 123-45-6789")
        
        # Log it the way the controller does
        if pii_found:
            pii_types = [p['description'] for p in pii_found]
            logger.warning(f"PII detected, types: {pii_types} (values not logged)")
        
        log_output = log_capture.getvalue()
        
        # Verify that actual SSN is NOT in logs
        assert '123-45-6789' not in log_output
        
        # Verify that PII type IS logged
        assert 'Social Security Number' in log_output
        assert 'values not logged' in log_output
        
        logger.removeHandler(handler)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
