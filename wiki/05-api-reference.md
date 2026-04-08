# API Reference

## Base URL

- **Local Development**: `http://localhost:5000`
- **Docker**: `http://backend:5000`

## Authentication

Currently, the API does not require authentication (POC phase). Future versions will implement OAuth 2.0 or JWT-based authentication.

## Common Headers

```
Content-Type: application/json
Accept: application/json
```

For file uploads:
```
Content-Type: multipart/form-data
```

## Response Format

All API responses follow a consistent JSON format:

**Success Response:**
```json
{
  "data": { /* response data */ },
  "status": "success"
}
```

**Error Response:**
```json
{
  "error": "Error message",
  "details": "Additional error details (optional)",
  "status": "error"
}
```

## HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 413 | Payload Too Large | File size exceeds limit |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | External service (AI) unavailable |

---

## PDF Validation Endpoints

### Upload PDF

Upload a PDF file for validation.

**Endpoint:** `POST /api/pdf/upload`

**Content-Type:** `multipart/form-data`

**Request:**

```
file: [PDF binary data]
```

**Response:** `200 OK`

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "SF424_Application.pdf",
  "file_size": 1234567,
  "status": "valid",
  "message": "File uploaded successfully"
}
```

**Error Responses:**

`400 Bad Request` - Invalid file:
```json
{
  "error": "Invalid file type. Only PDF files are allowed."
}
```

`413 Payload Too Large`:
```json
{
  "error": "File size exceeds 10MB limit"
}
```

**Example (cURL):**

```bash
curl -X POST http://localhost:5000/api/pdf/upload \
  -F "file=@/path/to/application.pdf"
```

**Example (JavaScript):**

```javascript
const formData = new FormData();
formData.append('file', pdfFile);

const response = await fetch('http://localhost:5000/api/pdf/upload', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log(data.file_id);
```

---

### Analyze PDF

Extract form fields, validate data, and get AI analysis.

**Endpoint:** `POST /api/pdf/analyze`

**Content-Type:** `application/json`

**Request:**

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Please analyze this form."
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_id | string | Yes | UUID from upload endpoint |
| message | string | No | Initial message to AI (default: "Please analyze this form.") |

**Response:** `200 OK`

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "form_data": {
    "applicant_name": "Example Organization",
    "ein": "12-3456789",
    "duns": "123456789",
    "address": {
      "street": "123 Main St",
      "city": "Washington",
      "state": "DC",
      "zip": "20001"
    },
    "project_title": "Health Services Grant",
    "federal_funding_requested": "500000"
  },
  "validation_errors": [
    {
      "field": "ein",
      "message": "EIN format should be XX-XXXXXXX",
      "severity": "error"
    }
  ],
  "validation_status": "FAILED",
  "ai_response": "I've analyzed your SF-424 form. I found 1 validation error that needs attention...",
  "metadata": {
    "page_count": 15,
    "form_version": "SF-424 V2.1",
    "created_date": "2024-01-15"
  }
}
```

**Error Responses:**

`400 Bad Request`:
```json
{
  "error": "file_id is required"
}
```

`404 Not Found`:
```json
{
  "error": "File not found"
}
```

`500 Internal Server Error`:
```json
{
  "error": "Analysis failed: [error details]"
}
```

**Example (cURL):**

```bash
curl -X POST http://localhost:5000/api/pdf/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Please analyze this form."
  }'
```

---

### Chat Message

Send a chat message and get AI response with form context.

**Endpoint:** `POST /api/chat/message`

**Content-Type:** `application/json`

**Request:**

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What is the applicant's EIN?",
  "chat_history": [
    {
      "role": "user",
      "content": "Please analyze this form."
    },
    {
      "role": "assistant",
      "content": "I've analyzed your form..."
    }
  ]
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file_id | string | Yes | UUID from upload endpoint |
| message | string | Yes | User's chat message |
| chat_history | array | No | Previous conversation history |

**Response:** `200 OK`

```json
{
  "response": "The applicant's EIN is 12-3456789. However, I noticed this format may be incorrect..."
}
```

**Error Responses:**

`400 Bad Request`:
```json
{
  "error": "file_id and message are required"
}
```

`404 Not Found`:
```json
{
  "error": "Session not found or expired"
}
```

`503 Service Unavailable`:
```json
{
  "error": "AI service unavailable",
  "details": "Connection timeout"
}
```

**Example (JavaScript):**

```javascript
const response = await fetch('http://localhost:5000/api/chat/message', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    file_id: fileId,
    message: userMessage,
    chat_history: chatHistory
  })
});

const data = await response.json();
console.log(data.response);
```

---

### Clear Session

Clear session data and delete temporary files.

**Endpoint:** `DELETE /api/session/clear`

**Content-Type:** `application/json`

**Request:**

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:** `200 OK`

```json
{
  "status": "success",
  "message": "Session cleared successfully"
}
```

**Error Responses:**

`400 Bad Request`:
```json
{
  "error": "file_id is required"
}
```

---

## Document Management Endpoints

### List Documents

Get all uploaded documents.

**Endpoint:** `GET /api/documents`

**Response:** `200 OK`

```json
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "SF424_Application.pdf",
      "upload_date": "2024-01-15T10:30:00Z",
      "status": "validated",
      "file_size": 1234567,
      "validation_status": "PASSED"
    }
  ],
  "total": 1
}
```

---

### Get Document

Get details of a specific document.

**Endpoint:** `GET /api/documents/<id>`

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "SF424_Application.pdf",
  "upload_date": "2024-01-15T10:30:00Z",
  "status": "validated",
  "file_size": 1234567,
  "validation_status": "PASSED",
  "validation_results": {
    "errors": [],
    "warnings": []
  },
  "file_path": "uploads/550e8400-e29b-41d4-a716-446655440000.pdf"
}
```

**Error Responses:**

`404 Not Found`:
```json
{
  "error": "Document not found"
}
```

---

### Upload Document

Upload a document (alternative to PDF upload endpoint).

**Endpoint:** `POST /api/documents/upload`

**Content-Type:** `multipart/form-data`

**Request:**

```
file: [PDF binary data]
```

**Response:** `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "SF424_Application.pdf",
  "upload_date": "2024-01-15T10:30:00Z",
  "status": "uploaded",
  "file_size": 1234567,
  "message": "Document uploaded successfully"
}
```

---

### Update Document

Update document metadata.

**Endpoint:** `PUT /api/documents/<id>`

**Content-Type:** `application/json`

**Request:**

```json
{
  "filename": "Updated_Application.pdf",
  "status": "reviewed"
}
```

**Response:** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "Updated_Application.pdf",
  "status": "reviewed",
  "message": "Document updated successfully"
}
```

---

### Delete Document

Delete a document and its associated files.

**Endpoint:** `DELETE /api/documents/<id>`

**Response:** `200 OK`

```json
{
  "status": "success",
  "message": "Document deleted successfully"
}
```

**Error Responses:**

`404 Not Found`:
```json
{
  "error": "Document not found"
}
```

---

## Health Check Endpoints

### API Health

Check API health status.

**Endpoint:** `GET /health`

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "active_sessions": 5
}
```

---

### Detailed Health

Check detailed health status of all services.

**Endpoint:** `GET /api/health`

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "ai_service": "connected",
    "storage": "available"
  }
}
```

---

## Root Endpoint

### API Information

Get API information and available endpoints.

**Endpoint:** `GET /`

**Response:** `200 OK`

```json
{
  "message": "Application Validation Assistant (AVA) API",
  "version": "1.0.0",
  "description": "AI-powered SF-424 form validation assistant",
  "endpoints": {
    "pdf_upload": "/api/pdf/upload",
    "pdf_analyze": "/api/pdf/analyze",
    "chat": "/api/chat/message",
    "session_clear": "/api/session/clear",
    "health": "/api/health",
    "documents": "/api/documents"
  }
}
```

---

## Data Models

### Form Data Structure

```json
{
  "applicant_name": "string",
  "ein": "string",
  "duns": "string",
  "address": {
    "street": "string",
    "city": "string",
    "state": "string",
    "zip": "string"
  },
  "contact": {
    "name": "string",
    "title": "string",
    "phone": "string",
    "email": "string"
  },
  "project_title": "string",
  "project_description": "string",
  "federal_funding_requested": "string",
  "applicant_funding": "string",
  "state_funding": "string",
  "other_funding": "string",
  "program_income": "string",
  "total_funding": "string"
}
```

### Validation Error Structure

```json
{
  "field": "string",
  "message": "string",
  "severity": "error|warning|info",
  "suggestion": "string (optional)"
}
```

### Session Data Structure

```json
{
  "file_name": "string",
  "uploaded_at": "ISO 8601 timestamp",
  "form_data": { /* Form Data Structure */ },
  "validation_errors": [ /* Array of Validation Errors */ ],
  "chat_history": [
    {
      "role": "user|assistant",
      "content": "string",
      "timestamp": "ISO 8601 timestamp"
    }
  ],
  "expires_at": "ISO 8601 timestamp"
}
```

---

## Rate Limiting

Currently, no rate limiting is implemented (POC phase). Future versions will implement:

- **Rate Limit**: 100 requests per minute per IP
- **Burst Limit**: 20 requests per second
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "error": "Human-readable error message",
  "details": "Technical details (optional)",
  "code": "ERROR_CODE (optional)",
  "timestamp": "ISO 8601 timestamp (optional)"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_FILE_TYPE` | File is not a PDF |
| `FILE_TOO_LARGE` | File exceeds size limit |
| `FILE_NOT_FOUND` | Uploaded file not found |
| `SESSION_EXPIRED` | Session has expired |
| `VALIDATION_FAILED` | Form validation failed |
| `AI_SERVICE_ERROR` | Azure OpenAI service error |
| `INVALID_REQUEST` | Request parameters invalid |

---

## CORS Configuration

The API allows requests from:

- `http://localhost:3000`
- `http://frontend:3000`

**Allowed Methods:**
- GET
- POST
- PUT
- DELETE

**Allowed Headers:**
- Content-Type

---

## File Size Limits

- **Maximum Upload Size**: 10 MB
- **Recommended Size**: Under 5 MB for optimal performance

---

## Session Management

- **Session Duration**: 24 hours
- **Cleanup Interval**: Every 1 hour
- **Storage**: JSON file (`data/sessions.json`)
- **Session ID**: UUID v4 format

---

## Best Practices

### 1. File Upload Flow

```
1. Upload PDF → Get file_id
2. Analyze PDF → Get form_data and validation_errors
3. Chat with AI → Use file_id for context
4. Clear session → Clean up when done
```

### 2. Error Handling

Always check response status codes and handle errors appropriately:

```javascript
try {
  const response = await fetch(url, options);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error);
  }
  
  const data = await response.json();
  return data;
} catch (error) {
  console.error('API Error:', error.message);
  // Handle error appropriately
}
```

### 3. Chat History Management

Maintain chat history on the client side and send with each message:

```javascript
const chatHistory = [];

// After each exchange
chatHistory.push(
  { role: 'user', content: userMessage },
  { role: 'assistant', content: aiResponse }
);

// Send with next message
await sendChatMessage(fileId, newMessage, chatHistory);
```

### 4. Session Cleanup

Always clear sessions when done to free up resources:

```javascript
// When user closes dialog or navigates away
await fetch('/api/session/clear', {
  method: 'DELETE',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ file_id: fileId })
});
```

---

## Testing the API

### Using cURL

```bash
# Upload PDF
curl -X POST http://localhost:5000/api/pdf/upload \
  -F "file=@application.pdf"

# Analyze PDF
curl -X POST http://localhost:5000/api/pdf/analyze \
  -H "Content-Type: application/json" \
  -d '{"file_id":"YOUR_FILE_ID"}'

# Chat
curl -X POST http://localhost:5000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"file_id":"YOUR_FILE_ID","message":"What errors did you find?"}'

# Health check
curl http://localhost:5000/health
```

### Using Postman

1. Import the API collection (if available)
2. Set base URL to `http://localhost:5000`
3. Use form-data for file uploads
4. Use JSON for other requests

### Using Thunder Client (VS Code)

1. Install Thunder Client extension
2. Create new request
3. Set method and URL
4. Add headers and body as needed
5. Send request and view response

---

## Changelog

### Version 1.0.0 (Current)

- Initial API release
- PDF upload and validation
- AI-powered form analysis
- Chat interface
- Session management
- Document management endpoints

### Planned Features

- Authentication and authorization
- Rate limiting
- Webhook support
- Batch processing
- Advanced analytics endpoints
- Export functionality
