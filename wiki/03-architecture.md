# System Architecture

## High-Level Architecture

The HRSA RPA POC follows a three-tier architecture pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                         Client Layer                         │
│                    (Web Browser - React)                     │
└─────────────────────────────────────────────────────────────┘
                              ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│                   (Next.js 14 + Material-UI)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Dashboard  │  │  Components  │  │   Services   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓ HTTP/REST API
┌─────────────────────────────────────────────────────────────┐
│                       Backend Layer                          │
│                      (Flask Python API)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Controllers  │  │   Services   │  │   Utilities  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ JSON Storage │  │ File Storage │  │ Azure OpenAI │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Frontend Architecture (Next.js)

```
frontend/
├── app/
│   ├── layout.js                    # Root layout with Material-UI theme
│   ├── page.js                      # Landing page
│   ├── dashboard/
│   │   └── page.js                  # Main dashboard
│   ├── components/
│   │   ├── Header.js                # App header with navigation
│   │   ├── Footer.js                # App footer
│   │   ├── DocumentUpload.js        # PDF upload component
│   │   ├── DocumentList.js          # Document listing
│   │   └── ChatInterface.js         # AI chat interface
│   └── styles/
│       └── globals.css              # Global styles
└── public/
    └── config.json                  # Environment configuration
```

**Key Frontend Components:**

1. **Layout System**
   - Root layout with Material-UI ThemeProvider
   - Responsive design with mobile support
   - Consistent header/footer across pages

2. **Dashboard**
   - Central hub for all operations
   - Document upload interface
   - Document list with actions
   - Chat interface for AI assistance

3. **Document Upload**
   - Drag-and-drop support via react-dropzone
   - File validation (type, size)
   - Progress indicators
   - Error handling

4. **Chat Interface**
   - Real-time messaging with AI
   - Context-aware responses
   - Message history
   - Session management

### Backend Architecture (Flask)

```
backend/
├── app.py                           # Main Flask application
├── controllers/
│   ├── document_controller.py       # Document CRUD operations (legacy)
│   └── pdf_validation_controller.py # PDF validation & AI endpoints
├── services/
│   ├── xfa_pdf_extractor.py        # XFA form field extraction from PDFs
│   ├── form_mapper.py               # Map XFA fields to SF-424 structure
│   ├── sf424_validator.py           # SF-424 validation rules & business logic
│   ├── database_service.py          # Database operations (UEI, Funding Opp, etc.)
│   ├── ai_service.py                # Azure OpenAI integration
│   ├── session_manager.py           # Session management with chat history
│   └── pdf_validator.py             # PDF structure validation
├── models/
│   ├── validation_error.py          # ValidationError and ValidationErrorFactory
│   ├── funding_cycle.py             # FundingCycle model
│   └── organization.py              # Organization model
├── config/
│   └── database.py                  # JSON database handler
└── data/
    ├── sessions.json                # Session storage with chat history
    ├── documents.json               # Document metadata (legacy)
    ├── mock_database.json           # Mock database (UEI, Funding Opp, Orgs)
    └── uploads/                     # PDF file storage
```

**Key Backend Components:**

1. **Controllers**
   - RESTful API endpoints
   - Request validation
   - Response formatting
   - Error handling

2. **Services**
   - Business logic layer
   - AI integration
   - PDF processing
   - Validation rules
   - Session management

3. **Models**
   - Data structures
   - Validation schemas
   - Type definitions

4. **Utilities**
   - Helper functions
   - PDF operations
   - File management

## Data Flow

### PDF Upload & Validation Flow

```
1. User uploads PDF
   ↓
2. Frontend validates file (type, size)
   ↓
3. POST /api/pdf/upload
   ↓
4. Backend saves file with UUID (file_id)
   ↓
5. SF424Validator.validate_pdf_structure()
   - Check for /AcroForm
   - Verify XFA or Fields exist
   ↓
6. Return file_id to frontend
   ↓
7. POST /api/pdf/analyze with file_id
   ↓
8. XFAPdfExtractor.extract_form_fields()
   - Parse XFA XML data
   - Extract all form fields
   - Return raw_fields and typed fields
   ↓
9. FormMapper.map_to_sf424()
   - Map XFA field names to SF-424 structure
   - Handle multiple field name prefixes
   - Type conversion (string, date, decimal)
   ↓
10. SF424Validator.validate_form_data()
   - Validate UEI against mock database
   - Validate Funding Opportunity Number
   - Validate Application Type constraints
   - Validate Grant Number (if continuation/revision)
   - Return ValidationError objects
   ↓
11. Build validation response
   - Extract user_message for UI display
   - Extract ai_context for AI model
   ↓
12. AIService.get_troubleshooting_guidance()
   - Send form data + validation errors to Azure OpenAI
   - Generate actionable troubleshooting steps
   - Return HTML-formatted guidance
   ↓
13. SessionManager.save_session()
   - Store form_data, validation_errors, chat_history
   - Set expiration (24 hours)
   ↓
14. Return analysis to frontend
   - form_data, validation_errors, validation_status, ai_response
   ↓
15. Display results and enable chat
```

### Chat Interaction Flow

```
1. User sends message
   ↓
2. POST /api/chat/message with file_id, message, chat_history
   ↓
3. SessionManager.get_session(file_id)
   - Retrieve form_data and validation_errors
   ↓
4. AIService.chat_completion()
   - Build system prompt (AVA role definition)
   - Add chat history to messages
   - Extract relevant form fields based on user question
   - Append form context to user message
   ↓
5. Call Azure OpenAI API
   - Model: GPT-4
   - Max tokens: 2000
   - Return HTML-formatted response
   ↓
6. SessionManager.update_chat_history()
   - Append user message and AI response
   - Update session timestamp
   ↓
7. Return AI response to frontend
   ↓
8. Display in chat interface
```

### Session Management Flow

```
1. Session created on PDF analysis
   ↓
2. Session stored in sessions.json
   ↓
3. Session includes:
   - file_id (UUID)
   - file_name
   - uploaded_at timestamp
   - form_data (extracted fields)
   - validation_errors
   - chat_history
   - expires_at (24 hours)
   ↓
4. Background scheduler runs hourly
   ↓
5. Cleanup expired sessions
   ↓
6. Delete associated files
```

## API Architecture

### RESTful Endpoints

**PDF Validation Endpoints:**
- `POST /api/pdf/upload` - Upload PDF file and validate structure
- `POST /api/pdf/analyze` - Extract, validate, and analyze SF-424 form
- `POST /api/chat/message` - Chat with AI about form with context
- `DELETE /api/session/clear` - Clear session data and delete files
- `GET /api/health` - Health check with active session count

**Document Management Endpoints (Legacy):**
- `GET /api/documents` - List all documents
- `GET /api/documents/<id>` - Get document details
- `POST /api/documents/upload` - Upload document
- `PUT /api/documents/<id>` - Update document
- `DELETE /api/documents/<id>` - Delete document

### API Request/Response Patterns

**Upload Request:**
```json
POST /api/pdf/upload
Content-Type: multipart/form-data

file: [PDF binary data]
```

**Upload Response:**
```json
{
  "file_id": "uuid-string",
  "file_name": "application.pdf",
  "file_size": 1234567,
  "status": "valid",
  "message": "File uploaded successfully"
}
```

**Analysis Request:**
```json
POST /api/pdf/analyze
Content-Type: application/json

{
  "file_id": "uuid-string",
  "file_name": "application.pdf",
  "message": "Please analyze this form."
}
```

**Analysis Response:**
```json
{
  "file_id": "uuid-string",
  "form_data": {
    "samuei": "E9358A5CI103",
    "organization_name": "Testing INC",
    "funding_opportunity_number": "HRSA-26-001",
    "application_type": "1",
    "federal_award_identifier": "1 H80CS12345-01-00",
    /* ... other SF-424 fields ... */
  },
  "validation_errors": [
    "UEI E9358A5CI103 not found in system",
    "Organization Testing INC does not match records"
  ],
  "validation_status": "PASSED" | "FAILED",
  "ai_response": "<strong>Form Status: Not Ready...</strong><br><br>...",
  "metadata": {
    "page_count": 2,
    "field_count": 45,
    "form_type": "SF-424"
  }
}
```

## Integration Architecture

### Azure OpenAI Integration

```
Backend Service
     ↓
AI Service Layer
     ↓
OpenAI Python SDK
     ↓
HTTPS/TLS
     ↓
Azure OpenAI API
     ↓
GPT-4 Model
```

**Configuration:**
- API Key: Environment variable `AZURE_OPENAI_API_KEY`
- Endpoint: Environment variable `AZURE_OPENAI_ENDPOINT`
- Model: GPT-4 or GPT-3.5-turbo
- Max Tokens: 4000
- Temperature: 0.7

**Prompt Engineering:**
- System prompt defines AI role as SF-424 validator
- Context includes form data and validation errors
- Chat history maintains conversation context
- Structured output for consistent responses

## Security Architecture

### Current Security Measures

1. **CORS Configuration**
   - Restricted origins (localhost:3000, frontend:3000)
   - Allowed methods: GET, POST, PUT, DELETE
   - Allowed headers: Content-Type

2. **File Upload Security**
   - File type validation (PDF only)
   - File size limits (10MB)
   - Secure filename handling
   - Isolated upload directory

3. **Session Security**
   - UUID-based session IDs
   - Automatic expiration (24 hours)
   - Session isolation per file

4. **Environment Variables**
   - API keys stored in .env files
   - Not committed to version control
   - Loaded at runtime

### Future Security Enhancements

- Authentication & Authorization (OAuth 2.0)
- HTTPS/TLS encryption
- API rate limiting
- Input sanitization
- SQL injection prevention (when migrating to PostgreSQL)
- File encryption at rest
- Audit logging
- RBAC (Role-Based Access Control)

## Deployment Architecture

### Docker Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Host                          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │         Docker Network (rpa-network)            │  │
│  │                                                 │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  │  │
│  │  │  Frontend        │  │  Backend         │  │  │
│  │  │  Container       │  │  Container       │  │  │
│  │  │  (Next.js)       │  │  (Flask)         │  │  │
│  │  │  Port: 3000      │  │  Port: 5000      │  │  │
│  │  └──────────────────┘  └──────────────────┘  │  │
│  │          ↓                      ↓             │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  │  │
│  │  │  Volume:         │  │  Volumes:        │  │  │
│  │  │  node_modules    │  │  - uploads       │  │  │
│  │  │  .next           │  │  - database      │  │  │
│  │  └──────────────────┘  └──────────────────┘  │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Container Configuration:**

1. **Frontend Container**
   - Base: Node.js 18
   - Port: 3000
   - Volumes: node_modules, .next
   - Environment: NEXT_PUBLIC_API_URL

2. **Backend Container**
   - Base: Python 3.11
   - Port: 5000
   - Volumes: uploads, database
   - Environment: FLASK_ENV, FLASK_DEBUG, Azure OpenAI credentials

3. **Network**
   - Bridge network for inter-container communication
   - Isolated from host network
   - DNS resolution between containers

## Scalability Considerations

### Current Limitations (POC)

- Single instance deployment
- JSON file storage (not concurrent-safe)
- No load balancing
- No caching layer
- No database connection pooling

### Future Scalability Path

1. **Horizontal Scaling**
   - Multiple backend instances
   - Load balancer (nginx/HAProxy)
   - Shared PostgreSQL database
   - Redis for session storage

2. **Vertical Scaling**
   - Increased container resources
   - Optimized PDF processing
   - Caching strategies

3. **Microservices Evolution**
   - Separate PDF processing service
   - Dedicated AI service
   - Message queue (RabbitMQ/Kafka)
   - Event-driven architecture

## Monitoring & Observability

### Current Monitoring

- Console logging
- Flask debug mode
- Docker logs

### Planned Monitoring

- Application Performance Monitoring (APM)
- Error tracking (Sentry)
- Log aggregation (ELK stack)
- Metrics collection (Prometheus)
- Dashboards (Grafana)
- Health check endpoints
- Uptime monitoring

## Technology Decisions & Rationale

### Why Microservices-Ready Architecture?

- **Modularity**: Easy to extract services later
- **Testability**: Independent component testing
- **Maintainability**: Clear separation of concerns
- **Scalability**: Can scale components independently

### Why JSON Storage for POC?

- **Speed**: Quick setup without database infrastructure
- **Simplicity**: Easy to inspect and debug
- **Flexibility**: Schema changes don't require migrations
- **Migration Path**: Structure designed for PostgreSQL

### Why Docker?

- **Consistency**: Same environment across dev/staging/prod
- **Isolation**: Dependencies contained
- **Portability**: Deploy anywhere Docker runs
- **Scalability**: Easy to orchestrate with Kubernetes

### Why Flask over Django?

- **Lightweight**: Minimal overhead for API
- **Flexibility**: Choose components as needed
- **Simplicity**: Less boilerplate
- **Performance**: Fast for API workloads
