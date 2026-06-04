"""
Input Sanitization Service
Prevents prompt injection, malicious input attacks, and detects PII
"""
import re
from typing import Optional, List, Dict


class InputSanitizer:
    """Sanitize user input to prevent prompt injection and other attacks"""
    
    # Maximum message length
    MAX_MESSAGE_LENGTH = 2000
    
    # Prompt injection patterns (case-insensitive)
    INJECTION_PATTERNS = [
        r'ignore\s+(all\s+)?previous\s+instructions',
        r'forget\s+(you\'?re|your|you\s+are)',
        r'you\s+are\s+now',
        r'disregard\s+(all\s+)?(previous|prior)',
        r'system\s+prompt',
        r'repeat\s+your\s+(instructions|prompt|system)',
        r'what\s+(are|is)\s+your\s+(instructions|prompt|system)',
        r'show\s+me\s+your\s+(instructions|prompt)',
        r'reveal\s+your\s+(instructions|prompt)',
        r'act\s+as\s+if',
        r'pretend\s+(you\'?re|to\s+be)',
        r'roleplay\s+as',
        r'simulate\s+(a|being)',
        r'bypass\s+(your\s+)?(instructions|rules|restrictions)',
        r'override\s+(your\s+)?(instructions|rules|restrictions)',
        r'jailbreak',
        r'dan\s+mode',
        r'developer\s+mode',
    ]
    
    # Suspicious patterns that might indicate injection
    SUSPICIOUS_PATTERNS = [
        r'<\s*script',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers (onclick, onerror, etc.)
        r'<\s*iframe',  # Iframes
    ]
    
    # PII detection patterns
    PII_PATTERNS = {
        'ssn': {
            'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
            'description': 'Social Security Number'
        },
        'ssn_no_dash': {
            'pattern': r'\b\d{9}\b',
            'description': 'Social Security Number (no dashes)'
        },
        'credit_card': {
            'pattern': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'description': 'Credit Card Number'
        },
        'email': {
            'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'description': 'Email Address'
        },
        'phone': {
            'pattern': r'\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            'description': 'Phone Number'
        },
        'date_of_birth': {
            'pattern': r'\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/(19|20)\d{2}\b',
            'description': 'Date of Birth'
        }
    }
    
    def sanitize_message(self, message: str) -> str:
        """
        Sanitize user message to prevent prompt injection
        
        Args:
            message: Raw user input
            
        Returns:
            Sanitized message
            
        Raises:
            ValueError: If message contains injection attempts
        """
        if not message:
            raise ValueError("Message cannot be empty")
        
        # Remove control characters (except newlines and tabs)
        message = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', message)
        
        # Limit message length
        if len(message) > self.MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message exceeds maximum length of {self.MAX_MESSAGE_LENGTH} characters")
        
        # Check for prompt injection patterns
        message_lower = message.lower()
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, message_lower):
                raise ValueError("Message contains suspicious content that may be attempting prompt injection")
        
        # Check for suspicious patterns (XSS, code injection)
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                raise ValueError("Message contains potentially malicious content")
        
        # Strip leading/trailing whitespace
        message = message.strip()
        
        return message
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent injection via file metadata
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        if not filename:
            return "unnamed"
        
        # Remove control characters including newlines
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # Remove path separators
        filename = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Remove leading dots
        filename = filename.lstrip('.')
        
        # Limit length
        if len(filename) > 255:
            filename = filename[:255]
        
        return filename or "unnamed"
    
    def validate_ai_response(self, response: str) -> bool:
        """
        Validate AI response doesn't contain leaked system info
        
        Args:
            response: AI-generated response
            
        Returns:
            True if response is safe, False otherwise
        """
        if not response:
            return True
        
        response_lower = response.lower()
        
        # Check for leaked system prompt indicators
        forbidden_phrases = [
            "ignore previous",
            "i am now",
            "system prompt:",
            "my instructions are",
            "i was instructed to",
            "my system prompt",
            "fake uei",
            "fake ein",
            "generate fake",
            "bypass validation"
        ]
        
        for phrase in forbidden_phrases:
            if phrase in response_lower:
                return False
        
        return True
    
    def detect_pii(self, text: str) -> List[Dict[str, str]]:
        """
        Detect PII (Personally Identifiable Information) in text
        
        Args:
            text: Text to scan for PII
            
        Returns:
            List of detected PII with type and description
            Example: [{'type': 'ssn', 'description': 'Social Security Number', 'value': '***-**-1234'}]
        """
        detected_pii = []
        
        if not text:
            return detected_pii
        
        for pii_type, pii_info in self.PII_PATTERNS.items():
            pattern = pii_info['pattern']
            matches = re.findall(pattern, text)
            
            for match in matches:
                # Mask the value for logging (show last 4 digits only)
                if pii_type in ['ssn', 'ssn_no_dash']:
                    masked = f"***-**-{match[-4:]}" if len(match) >= 4 else "***"
                elif pii_type == 'credit_card':
                    masked = f"****-****-****-{match[-4:]}" if len(match) >= 4 else "****"
                elif pii_type == 'email':
                    parts = match.split('@')
                    masked = f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 else "***"
                elif pii_type == 'phone':
                    masked = f"***-***-{match[-4:]}" if len(match) >= 4 else "***"
                else:
                    masked = "***"
                
                detected_pii.append({
                    'type': pii_type,
                    'description': pii_info['description'],
                    'masked_value': masked
                })
        
        return detected_pii


# Global sanitizer instance
_sanitizer_instance = None

def get_sanitizer():
    """Get global sanitizer instance"""
    global _sanitizer_instance
    if _sanitizer_instance is None:
        _sanitizer_instance = InputSanitizer()
    return _sanitizer_instance
