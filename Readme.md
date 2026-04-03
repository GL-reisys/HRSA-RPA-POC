# RPA POC AVA Application Setup Plan

Set up a full-stack application with Next.js frontend (Material-UI), Flask backend with JSON-based data storage (PostgreSQL-ready), Docker containerization, and PDF validation functionality.

## Project Overview

Create a proof-of-concept application with:
- **Frontend**: Next.js with Material-UI
- **Backend**: Python Flask API with PDF processing capabilities
- **Data Storage**: JSON file (mimicking PostgreSQL structure for easy migration)
- **Containerization**: Docker + Docker Compose
- **CI/CD**: GitHub Actions workflows

## Folder Structure

```
RPA-POC-AVA-app/
├── backend/
│   ├── config/
│   │   └── database.py          # JSON file handler (PostgreSQL-ready)
│   ├── database/
│   │   ├── init_db.py           # Database initialization
│   │   ├── seed_data.py         # Sample data seeding
│   │   └── data.json            # JSON storage file
│   ├── services/
│   │   └── pdf_validator.py    # PDF validation business logic
│   ├── controllers/
│   │   └── document_controller.py  # PDF processing endpoints
│   ├── utils/
│   │   └── pdf_reader.py        # PDF reading utilities
│   ├── app.py                   # Main Flask application
│   ├── Dockerfile               # Backend container
│   └── requirements.txt         # Python dependencies
│
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── Header.js
│   │   │   ├── Footer.js
│   │   │   └── DocumentUpload.js  # PDF upload component
│   │   ├── dashboard/
│   │   │   └── page.js          # Main dashboard (no login)
│   │   ├── styles/
│   │   │   └── globals.css
│   │   ├── layout.js            # Root layout with Material-UI
│   │   └── page.js              # Welcome/landing page
│   ├── public/
│   │   └── config.json          # Environment configuration
│   ├── Dockerfile               # Frontend container
│   ├── package.json             # Node dependencies
│   └── next.config.js           # Next.js configuration
│
├── docker-compose.yml           # Orchestration for both services
├── .github/
│   └── workflows/
│       ├── backend-ci.yml       # Backend tests & build
│       └── frontend-ci.yml      # Frontend tests & build
├── .gitignore
└── README.md
```

## Implementation Steps

### 1. Backend Setup (Flask API)

**Files to create:**

- **`backend/requirements.txt`**: Include Flask, Flask-CORS, PyPDF2/pdfplumber, python-dotenv
- **`backend/app.py`**: Main Flask app with CORS, error handling, and route registration
- **`backend/config/database.py`**: JSON file handler with methods mimicking database operations (get, insert, update, delete)
- **`backend/database/init_db.py`**: Initialize JSON structure
- **`backend/database/seed_data.py`**: Sample document records
- **`backend/database/data.json`**: JSON storage with structure ready for PostgreSQL migration
- **`backend/services/pdf_validator.py`**: Business logic for PDF validation (file type, size, content extraction)
- **`backend/controllers/document_controller.py`**: REST endpoints:
  - `POST /api/documents/upload` - Upload and validate PDF
  - `GET /api/documents` - List all documents
  - `GET /api/documents/<id>` - Get document details
  - `DELETE /api/documents/<id>` - Delete document
- **`backend/utils/pdf_reader.py`**: PDF text extraction and metadata reading
- **`backend/Dockerfile`**: Multi-stage build for Python Flask app

### 2. Frontend Setup (Next.js + Material-UI)

**Files to create:**

- **`frontend/package.json`**: Next.js, React, Material-UI (@mui/material, @emotion), axios
- **`frontend/next.config.js`**: API proxy configuration
- **`frontend/app/layout.js`**: Root layout with Material-UI ThemeProvider
- **`frontend/app/page.js`**: Landing/welcome page with navigation to dashboard
- **`frontend/app/dashboard/page.js`**: Main dashboard with document upload and list
- **`frontend/app/components/Header.js`**: App header with Material-UI AppBar
- **`frontend/app/components/Footer.js`**: Simple footer
- **`frontend/app/components/DocumentUpload.js`**: PDF upload component with drag-and-drop
- **`frontend/app/styles/globals.css`**: Global styles
- **`frontend/public/config.json`**: Backend API URL configuration
- **`frontend/Dockerfile`**: Multi-stage build for Next.js

### 3. Docker Configuration

**Files to create:**

- **`docker-compose.yml`**: 
  - Backend service (port 5000)
  - Frontend service (port 3000)
  - Volume mounts for development
  - Network configuration

### 4. CI/CD Setup

**Files to create:**

- **`.github/workflows/backend-ci.yml`**: 
  - Run Python tests
  - Lint with flake8
  - Build Docker image
- **`.github/workflows/frontend-ci.yml`**:
  - Run npm tests
  - Lint with ESLint
  - Build Docker image

### 5. Documentation & Configuration

**Files to create:**

- **`README.md`**: Project overview, setup instructions, API documentation
- **`.gitignore`**: Node modules, Python cache, environment files, data.json

## Key Technical Decisions

1. **JSON Storage Structure**: Design JSON schema to match PostgreSQL tables (documents table with id, filename, upload_date, status, validation_results, file_path)
2. **PDF Library**: Use `pdfplumber` for robust text extraction and validation
3. **Material-UI Theme**: Use default theme with custom primary color
4. **API Communication**: Axios for HTTP requests from frontend
5. **File Upload**: Store uploaded PDFs in `backend/uploads/` directory (gitignored)
6. **Controller Name**: `DocumentController` - handles all document/PDF operations

## Migration Path to PostgreSQL

The JSON structure will be designed to easily migrate to PostgreSQL:
- JSON objects → PostgreSQL rows
- Nested structures → Relational tables with foreign keys
- `config/database.py` will have methods that can be swapped with SQLAlchemy ORM

## Next Steps After Setup

1. Test PDF upload and validation flow
2. Add more validation rules as needed
3. Implement error handling and logging
4. Add unit tests for backend services
5. Add frontend tests with Jest/React Testing Library
6. Configure environment variables for production
