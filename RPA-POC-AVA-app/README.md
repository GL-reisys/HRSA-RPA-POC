# HRSA RPA POC - Application Validation Assistant (AVA)

An AI-powered proof-of-concept application for automated SF-424 grant application form validation. The system extracts XFA form data from PDFs, validates against business rules and mock database records, and provides intelligent troubleshooting guidance through Azure OpenAI integration.

## 🏗️ Architecture

- **Frontend**: Next.js 14 with Material-UI for responsive UI
- **Backend**: Python Flask API with XFA PDF extraction and validation
- **AI Integration**: Azure OpenAI (GPT-4) for intelligent form analysis and chat
- **Data Storage**: JSON-based mock database (PostgreSQL-ready structure)
- **Containerization**: Docker & Docker Compose for consistent deployment

## 📋 Key Features

### XFA PDF Processing
- Drag-and-drop SF-424 PDF upload with validation
- XFA form field extraction using pikepdf and lxml
- Automatic field mapping to SF-424 data structure
- PDF structure validation (XFA/AcroForm detection)

### Database-Driven Validation
- **UEI Verification**: Validates Unique Entity Identifier against mock database
- **Funding Opportunity Validation**: Checks funding opportunity number and constraints
- **Application Type Validation**: Validates New/Continuation/Revision applications
- **Grant Number Validation**: Verifies grant numbers for continuation/revision applications
- **Business Rule Enforcement**: Applies funding opportunity-specific constraints

### AI-Powered Analysis
- Azure OpenAI integration for intelligent form analysis
- Context-aware troubleshooting guidance generation
- Validation error explanations with actionable steps
- HTML-formatted responses for rich UI display

### Interactive Chat Interface
- Real-time Q&A about uploaded SF-424 forms
- Contextual assistance based on form data and validation results
- Session-based conversation history
- Automatic form field extraction for relevant context

### Session Management
- UUID-based session tracking per uploaded file
- Automatic session expiration (24 hours)
- Background cleanup scheduler (hourly via APScheduler)
- Chat history persistence within sessions

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd HRSA-RPA-POC/RPA-POC-AVA-app
```

2. Configure Azure OpenAI credentials in `backend/.env`:
```env
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

3. Start the application:
```bash
docker-compose up --build
```

4. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - Health Check: http://localhost:5000/health

### Local Development

#### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create required directories:
```bash
mkdir data\uploads
```

5. Initialize data storage:
```bash
echo {} > data\sessions.json
```

6. Run the Flask server:
```bash
python app.py
```

Backend will be available at http://localhost:5000

#### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run development server:
```bash
npm run dev
```

Frontend will be available at http://localhost:3000

## 📡 API Endpoints

### PDF Validation & Analysis

- `POST /api/pdf/upload` - Upload SF-424 PDF and validate structure
- `POST /api/pdf/analyze` - Extract form fields, validate data, and get AI analysis
- `POST /api/chat/message` - Chat with AI about the uploaded form
- `DELETE /api/session/clear` - Clear session data and delete files
- `GET /api/health` - Check API health status with active session count

### Document Management (Legacy)

- `GET /api/documents` - Get all documents
- `GET /api/documents/<id>` - Get a specific document
- `POST /api/documents/upload` - Upload document
- `PUT /api/documents/<id>` - Update document metadata
- `DELETE /api/documents/<id>` - Delete a document

## 📁 Project Structure

```
RPA-POC-AVA-app/
├── backend/
│   ├── controllers/
│   │   ├── document_controller.py       # Document CRUD (legacy)
│   │   └── pdf_validation_controller.py # PDF validation & AI endpoints
│   ├── services/
│   │   ├── xfa_pdf_extractor.py        # XFA form field extraction
│   │   ├── form_mapper.py               # Map XFA to SF-424 structure
│   │   ├── sf424_validator.py           # SF-424 validation rules
│   │   ├── database_service.py          # Database operations
│   │   ├── ai_service.py                # Azure OpenAI integration
│   │   ├── session_manager.py           # Session management
│   │   └── pdf_validator.py             # PDF structure validation
│   ├── models/
│   │   ├── validation_error.py          # ValidationError models
│   │   ├── funding_cycle.py             # FundingCycle model
│   │   └── organization.py              # Organization model
│   ├── config/
│   │   └── database.py                  # JSON database handler
│   ├── data/
│   │   ├── sessions.json                # Session storage
│   │   ├── mock_database.json           # Mock database
│   │   └── uploads/                     # PDF file storage
│   ├── app.py                           # Main Flask application
│   ├── Dockerfile                       # Backend container
│   └── requirements.txt                 # Python dependencies
│
├── frontend/
│   ├── app/
│   │   ├── components/                  # React components
│   │   ├── dashboard/                   # Dashboard page
│   │   ├── styles/                      # CSS styles
│   │   ├── layout.js                    # Root layout
│   │   └── page.js                      # Landing page
│   ├── public/
│   │   └── config.json                  # API URL configuration
│   ├── Dockerfile                       # Frontend container
│   └── package.json                     # Node dependencies
│
├── .github/workflows/                   # CI/CD pipelines
├── docker-compose.yml                   # Docker orchestration
└── README.md                            # This file
```

## 🔧 Configuration

### Backend Configuration

Create `backend/.env` file:

```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1

# Azure OpenAI Configuration (Required for AI features)
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4

# Application Configuration (Optional)
MAX_FILE_SIZE=10485760  # 10MB
SESSION_TIMEOUT_HOURS=24
```

**Data Storage:**
- Sessions: `backend/data/sessions.json`
- Mock Database: `backend/data/mock_database.json`
- Uploads: `backend/data/uploads/`
- Max file size: 10MB

### Frontend Configuration

Update `frontend/public/config.json` to change the API URL:

```json
{
  "apiUrl": "http://localhost:5000"
}
```

## 🧪 Testing

### Test with Sample SF-424 PDFs

Use the test files in the `TestData/` directory:
- `1-HappyPath-New.pdf` - Valid new application
- `3-HappyPath-Continuation.pdf` - Valid continuation application
- `11 - New - Invalid UEI.pdf` - Invalid UEI test case
- `12 - New - Invalid FON.pdf` - Invalid Funding Opportunity Number test case

### Manual Testing

1. Upload a test PDF via the dashboard
2. Click "Analyze" to trigger validation
3. Review validation results and AI guidance
4. Test chat functionality with questions like:
   - "What is the UEI in this form?"
   - "What validation errors were found?"
   - "What is the funding opportunity number?"

## 🔄 Future Enhancements

### Migration to PostgreSQL

The JSON database structure is designed for easy migration:

1. Install PostgreSQL and SQLAlchemy
2. Create tables: Organizations, FundingCycles, ValidationErrors
3. Update `database_service.py` to use SQLAlchemy ORM
4. Migrate data from `mock_database.json`

### Planned Features

- User authentication and authorization
- Multi-form support (beyond SF-424)
- Advanced analytics and reporting
- Batch PDF processing
- Email notifications for validation results
- Integration with Grants.gov API

## 📝 Environment Variables

### Backend

- `FLASK_ENV`: Development/Production mode (default: development)
- `FLASK_DEBUG`: Enable debug mode (default: 0)
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key (required for AI features)
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL (required for AI features)
- `AZURE_OPENAI_DEPLOYMENT`: Model deployment name (default: gpt-4)
- `MAX_FILE_SIZE`: Maximum upload size in bytes (default: 10485760)
- `SESSION_TIMEOUT_HOURS`: Session expiration time (default: 24)

### Frontend

- `NEXT_PUBLIC_API_URL`: Backend API URL (configured in `public/config.json`)

## 🐳 Docker Commands

Build and start services:
```bash
docker-compose up --build
```

Stop services:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f
```

Rebuild specific service:
```bash
docker-compose up --build backend
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

See LICENSE file for details.

## 🆘 Troubleshooting

### Backend Issues

- **Port 5000 already in use**: Change the port in `docker-compose.yml` or stop the conflicting service
- **PDF validation fails**: Ensure the PDF is a valid SF-424 XFA form and under 10MB
- **AI service unavailable**: Verify Azure OpenAI credentials in `.env` file
- **Session not found**: Sessions expire after 24 hours - re-upload the PDF

### Frontend Issues

- **Cannot connect to backend**: Check that backend is running at http://localhost:5000/health
- **CORS errors**: Verify CORS configuration in `backend/app.py` includes your frontend URL
- **Build fails**: Delete `node_modules` and `.next` folders, then run `npm install` again

### Docker Issues

- **Container won't start**: Check logs with `docker-compose logs -f`
- **Volume permission issues**: Ensure Docker has proper permissions to mount volumes
- **Build cache issues**: Run `docker-compose down` and `docker system prune -a` before rebuilding

### Validation Issues

- **UEI not found**: Check `data/mock_database.json` for valid test UEIs
- **Funding Opportunity invalid**: Verify the funding opportunity code matches entries in mock database
- **Grant Number validation fails**: Ensure application type is Continuation/Revision and grant number format is correct

## 📚 Documentation

For detailed documentation, see the `wiki/` directory:
- `01-overview.md` - Project overview and objectives
- `02-tech-stack.md` - Technology stack and dependencies
- `03-architecture.md` - System architecture and data flows
- `04-setup-guide.md` - Detailed setup instructions

## 📞 Support

For issues and questions, please open an issue in the repository.

## 📄 License

See LICENSE file for details.
