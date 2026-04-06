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
│   ├── document_controller.py       # Document CRUD operations
│   └── pdf_validation_controller.py # PDF validation & AI endpoints
├── services/
│   ├── xfa_pdf_extractor.py        # XFA form field extraction
│   ├── form_mapper.py               # Map XFA to SF-424 structure
│   ├── sf424_validator.py           # SF-424 validation rules
│   ├── ai_service.py                # Azure OpenAI integration
│   ├── session_manager.py           # Session management
│   └── pdf_validator.py             # PDF validation service
├── models/
│   ├── application.py               # Application data model
│   └── document.py                  # Document data model
├── utils/
│   └── pdf_reader.py                # PDF reading utilities
├── config/
│   └── database.py                  # JSON database handler
└── data/
    ├── sessions.json                # Session storage
    ├── documents.json               # Document metadata
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
4. Backend saves file with UUID
   ↓
5. Validate PDF structure
   ↓
6. Return file_id to frontend
   ↓
7. POST /api/pdf/analyze with file_id
   ↓
8. Extract XFA form fields
   ↓
9. Map to SF-424 structure
   ↓
10. Validate form data
   ↓
11. Send to Azure OpenAI for analysis
   ↓
12. Create session with results
   ↓
13. Return analysis to frontend
   ↓
14. Display results and enable chat
```

### Chat Interaction Flow

```
1. User sends message
   ↓
2. POST /api/chat/message
   ↓
3. Retrieve session data (form context)
   ↓
4. Build prompt with context + history
   ↓
5. Call Azure OpenAI API
   ↓
6. Update session chat history
   ↓
7. Return AI response
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
- `POST /api/pdf/upload` - Upload PDF file
- `POST /api/pdf/analyze` - Analyze and validate PDF
- `POST /api/chat/message` - Chat with AI about form
- `DELETE /api/session/clear` - Clear session data
- `GET /api/health` - Health check

**Document Management Endpoints:**
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
  "message": "Please analyze this form."
}
```

**Analysis Response:**
```json
{
  "file_id": "uuid-string",
  "form_data": { /* extracted fields */ },
  "validation_errors": [ /* errors */ ],
  "validation_status": "PASSED|FAILED",
  "ai_response": "Analysis text...",
  "metadata": { /* PDF metadata */ }
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
