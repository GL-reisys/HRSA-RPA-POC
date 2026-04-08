# Application Validation Assistant (AVA) - Backend

AI-powered SF-424 grant application form validation assistant built with Flask and Python.

## Overview

AVA validates SF-424 (Application for Federal Assistance) forms by:
- Extracting XFA form data from PDF files using pikepdf + lxml
- Validating against business rules (88 fields across 10 sections)
- Providing AI-powered analysis via Azure OpenAI
- Supporting interactive Q&A chat with form context

## Technology Stack

- **Framework**: Flask 3.0.0
- **PDF Processing**: pikepdf 8.10.1 + lxml 5.1.0 (XFA extraction)
- **AI Service**: Azure OpenAI (Python SDK)
- **Data Validation**: Pydantic 2.6.1
- **Session Storage**: JSON file (POC) → PostgreSQL (Production)
- **Scheduler**: APScheduler 3.10.4 (session cleanup)

## Project Structure

```
backend/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── config/
│   ├── database.py                 # Database configuration
│   └── field_mapping.json          # XFA field name mappings
├── controllers/
│   ├── document_controller.py      # Document endpoints
│   └── pdf_validation_controller.py # AVA endpoints
├── services/
│   ├── xfa_pdf_extractor.py        # XFA PDF extraction
│   ├── form_mapper.py              # Field mapping to SF424
│   ├── sf424_validator.py          # Form validation
│   ├── ai_service.py               # Azure OpenAI integration
│   ├── session_manager.py          # Session management
│   └── pdf_validator.py            # Legacy PDF validator
├── models/
│   └── sf424_form_data.py          # SF-424 data model (88 fields)
└── data/
    ├── uploads/                    # Temporary PDF storage
    └── sessions.json               # Session data (POC)
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your Azure OpenAI credentials:

```env
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

### 3. Create Required Directories

```bash
mkdir -p data/uploads
mkdir -p uploads
```

## Running the Application

### Development Mode

```bash
python app.py
```

The API will be available at `http://localhost:5000`

### Production Mode

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## API Endpoints

### 1. Upload PDF
```http
POST /api/pdf/upload
Content-Type: multipart/form-data

Response:
{
  "file_id": "uuid",
  "file_name": "application.pdf",
  "status": "valid"
}
```

### 2. Analyze Form
```http
POST /api/pdf/analyze
Content-Type: application/json

{
  "file_id": "uuid",
  "message": "Please analyze this form"
}

Response:
{
  "file_id": "uuid",
  "form_data": { ... },
  "validation_errors": [ ... ],
  "validation_status": "PASSED|FAILED",
  "ai_response": "HTML formatted response"
}
```

### 3. Chat Message
```http
POST /api/chat/message
Content-Type: application/json

{
  "file_id": "uuid",
  "message": "What is the project title?",
  "chat_history": [ ... ]
}

Response:
{
  "response": "The project title is..."
}
```

### 4. Clear Session
```http
DELETE /api/session/clear
Content-Type: application/json

{
  "file_id": "uuid"
}
```

### 5. Health Check
```http
GET /api/health

Response:
{
  "status": "healthy",
  "active_sessions": 5
}
```

## Key Features

### XFA PDF Extraction
- Uses pikepdf to extract raw XFA XML from PDF
- Parses XML with lxml to get form field values
- Supports multiple field name variants
- Fallback to AcroForm if XFA not available

### Form Validation
- 18 required fields validation
- Format validation (EIN, UEI, email)
- Business logic validation (budget totals, date ranges)
- Comprehensive error messages

### AI Integration
- Azure OpenAI GPT-4 integration
- Context-aware responses with form data
- HTML-formatted responses for UI display
- Relevant field extraction based on user questions

### Session Management
- JSON file storage for POC
- 4-hour session timeout
- Automatic cleanup of expired sessions
- Thread-safe file operations

## Testing

### Test PDF Upload
```bash
curl -X POST http://localhost:5000/api/pdf/upload \
  -F "file=@test_sf424.pdf"
```

### Test Form Analysis
```bash
curl -X POST http://localhost:5000/api/pdf/analyze \
  -H "Content-Type: application/json" \
  -d '{"file_id": "your-file-id", "message": "Analyze this form"}'
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | Required |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Required |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name | gpt-4 |
| `SESSION_STORAGE_PATH` | Session JSON file path | data/sessions.json |
| `SESSION_TIMEOUT_HOURS` | Session expiration time | 4 |
| `MAX_FILE_SIZE` | Max PDF file size (bytes) | 10485760 (10MB) |

## Troubleshooting

### XFA Extraction Issues
- Verify PDF is actually XFA (not scanned/flat PDF)
- Check XFA XML structure with debug output
- Try different field name variants in mapping
- Consider C# microservice fallback if needed

### AI Service Errors
- Verify Azure OpenAI credentials in .env
- Check endpoint URL format
- Ensure deployment name is correct
- Monitor API rate limits

### Session Issues
- Check data/sessions.json file permissions
- Verify session timeout configuration
- Monitor disk space for session storage

## Migration to Production

### PostgreSQL Migration
When ready for production, migrate from JSON to PostgreSQL:

1. Create database schema (see documentation)
2. Update `session_manager.py` to use PostgreSQL
3. Configure database connection string
4. Test migration with existing sessions

### Scaling Considerations
- Use multiple Flask workers (gunicorn)
- Add Redis for caching
- Separate PDF processing workers
- Implement load balancing

## Documentation

Complete migration documentation available in:
- `MIGRATION_DOCS/` - Full migration guide from ASP.NET
- `MIGRATION_DOCS/02-backend/` - Backend implementation details
- `MIGRATION_DOCS/04-data/` - SF-424 data model and validation rules

## Support

For issues or questions:
1. Check migration documentation
2. Review API endpoint specifications
3. Test with sample SF-424 PDFs
4. Verify Azure OpenAI configuration

## License

Internal use only - HRSA RPA POC
