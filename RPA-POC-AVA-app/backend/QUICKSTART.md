# AVA Backend - Quick Start Guide

Get the Application Validation Assistant backend running in 5 minutes.

## Prerequisites

- Python 3.9 or higher
- Azure OpenAI access (endpoint + API key)
- SF-424 PDF form for testing

## Setup Steps

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Azure OpenAI credentials
# Required variables:
# - AZURE_OPENAI_ENDPOINT
# - AZURE_OPENAI_API_KEY
# - AZURE_OPENAI_DEPLOYMENT
```

### 3. Create Data Directories

```bash
mkdir -p data/uploads
mkdir -p data
```

### 4. Run the Application

```bash
python app.py
```

Server will start at `http://localhost:5000`

## Test the API

### 1. Check Health

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "active_sessions": 0
}
```

### 2. Upload a PDF

```bash
curl -X POST http://localhost:5000/api/pdf/upload \
  -F "file=@path/to/sf424.pdf"
```

Expected response:
```json
{
  "file_id": "abc-123-def-456",
  "file_name": "sf424.pdf",
  "status": "valid"
}
```

### 3. Analyze the Form

```bash
curl -X POST http://localhost:5000/api/pdf/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "abc-123-def-456",
    "message": "Please analyze this form"
  }'
```

Expected response:
```json
{
  "file_id": "abc-123-def-456",
  "form_data": { ... },
  "validation_errors": [ ... ],
  "validation_status": "PASSED",
  "ai_response": "<strong>Form Status: Ready for Submission</strong>..."
}
```

### 4. Chat with AVA

```bash
curl -X POST http://localhost:5000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "abc-123-def-456",
    "message": "What is the organization name?",
    "chat_history": []
  }'
```

## API Workflow

```
1. Upload PDF → Get file_id
   POST /api/pdf/upload

2. Analyze Form → Get validation results + AI analysis
   POST /api/pdf/analyze

3. Ask Questions → Interactive chat with form context
   POST /api/chat/message

4. Clear Session → Clean up when done
   DELETE /api/session/clear
```

## Key Components

### XFA PDF Extractor
- **File**: `services/xfa_pdf_extractor.py`
- **Purpose**: Extract form fields from XFA PDFs using pikepdf + lxml
- **Output**: Dictionary of field names and values

### Form Mapper
- **File**: `services/form_mapper.py`
- **Purpose**: Map XFA fields to SF424FormData model
- **Config**: `config/field_mapping.json`

### SF-424 Validator
- **File**: `services/sf424_validator.py`
- **Purpose**: Validate form data against business rules
- **Rules**: 18 required fields, format validation, business logic

### AI Service
- **File**: `services/ai_service.py`
- **Purpose**: Azure OpenAI integration for analysis and chat
- **Model**: GPT-4 (configurable)

### Session Manager
- **File**: `services/session_manager.py`
- **Purpose**: Store session data in JSON file
- **Timeout**: 4 hours (configurable)

## Common Issues

### Issue: "PDF does not contain a form"
**Solution**: Ensure PDF is an XFA or AcroForm PDF, not a scanned/flat PDF

### Issue: "AI service unavailable"
**Solution**: 
- Check Azure OpenAI credentials in `.env`
- Verify endpoint URL format
- Ensure deployment name matches your Azure resource

### Issue: "Session not found or expired"
**Solution**: 
- Sessions expire after 4 hours
- Re-upload and analyze the PDF
- Check `data/sessions.json` file permissions

### Issue: "No fields extracted from PDF"
**Solution**:
- Verify PDF is SF-424 form (not other form types)
- Check XFA structure with debug output
- Try different field name variants in mapping

## Development Tips

### Enable Debug Logging
```python
# In services/xfa_pdf_extractor.py
print(f"XFA extraction successful: {len(result['raw_fields'])} fields")
```

### Test with Sample Data
```python
# Create test session
from services.session_manager import SessionManager
sm = SessionManager()
sm.save_session('test-123', {
    'file_name': 'test.pdf',
    'form_data': {...},
    'validation_errors': []
})
```

### View Session Data
```bash
cat data/sessions.json | python -m json.tool
```

## Next Steps

1. **Test with real SF-424 PDFs** - Verify extraction works with your forms
2. **Customize validation rules** - Update `sf424_validator.py` for your requirements
3. **Tune AI prompts** - Modify system prompts in `ai_service.py`
4. **Add frontend** - Connect Next.js frontend to these APIs
5. **Monitor performance** - Track extraction time and accuracy

## Production Checklist

- [ ] Configure production Azure OpenAI endpoint
- [ ] Set up PostgreSQL database (replace JSON storage)
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS for production domain
- [ ] Set up logging and monitoring
- [ ] Implement rate limiting
- [ ] Add authentication/authorization
- [ ] Configure backup strategy
- [ ] Set up CI/CD pipeline
- [ ] Load test with multiple concurrent users

## Resources

- **Full Documentation**: `README.md`
- **Migration Docs**: `../MIGRATION_DOCS/`
- **API Specification**: `../MIGRATION_DOCS/02-backend/flask-api-specification.md`
- **Data Model**: `models/sf424_form_data.py`

## Support

For detailed implementation guidance, refer to the migration documentation in `MIGRATION_DOCS/`.
