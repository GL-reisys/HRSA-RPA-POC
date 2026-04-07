# Setup Guide

## Prerequisites

Before setting up the HRSA RPA POC application, ensure you have the following installed:

### Required Software

- **Docker Desktop** (recommended)
  - Version: 20.10+
  - Download: https://www.docker.com/products/docker-desktop

- **Node.js** (for local development)
  - Version: 18.x or higher
  - Download: https://nodejs.org/

- **Python** (for local development)
  - Version: 3.11 or higher
  - Download: https://www.python.org/

- **Git**
  - Latest version
  - Download: https://git-scm.com/

### Azure OpenAI Access

- Azure OpenAI API Key
- Azure OpenAI Endpoint URL
- Deployed GPT-4 or GPT-3.5-turbo model

## Quick Start (Docker - Recommended)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd HRSA-RPA-POC/RPA-POC-AVA-app
```

### 2. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```bash
cd backend
```

Create `.env` file with the following content:

```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1

# Azure OpenAI Configuration (Required for AI features)
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4

# Application Configuration (Optional - defaults provided)
MAX_FILE_SIZE=10485760
SESSION_TIMEOUT_HOURS=24
```

### 3. Start the Application

From the `RPA-POC-AVA-app` directory:

```bash
docker-compose up --build
```

This will:
- Build both frontend and backend Docker images
- Start the containers
- Create necessary volumes
- Set up the network

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **Health Check**: http://localhost:5000/health

### 5. Verify Installation

Open your browser and navigate to http://localhost:3000. You should see the AVA landing page.

## Local Development Setup

For development without Docker, follow these steps:

### Backend Setup

#### 1. Navigate to Backend Directory

```bash
cd RPA-POC-AVA-app/backend
```

#### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Create Required Directories

```bash
mkdir data
mkdir data\uploads
mkdir uploads
```

**macOS/Linux:**
```bash
mkdir -p data/uploads
mkdir uploads
```

#### 5. Configure Environment Variables

Create `.env` file (see Docker setup section for content).

#### 6. Initialize Data Storage

Create `data/sessions.json`:

```json
{}
```

Create `data/documents.json` (optional - legacy):

```json
{
  "documents": []
}
```

Note: `data/mock_database.json` should already exist in the repository with sample UEI, Funding Opportunity, and Organization data.

#### 7. Run the Backend Server

```bash
python app.py
```

The backend will start on http://localhost:5000

### Frontend Setup

#### 1. Navigate to Frontend Directory

Open a new terminal:

```bash
cd RPA-POC-AVA-app/frontend
```

#### 2. Install Dependencies

```bash
npm install
```

#### 3. Configure API URL

Edit `public/config.json`:

```json
{
  "apiUrl": "http://localhost:5000"
}
```

#### 4. Run Development Server

```bash
npm run dev
```

The frontend will start on http://localhost:3000

## Configuration Details

### Backend Configuration

**File: `backend/.env`**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FLASK_ENV` | Flask environment | development | No |
| `FLASK_DEBUG` | Enable debug mode | 0 | No |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | - | Yes* |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | - | Yes* |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | gpt-4 | No |
| `MAX_FILE_SIZE` | Max upload size in bytes | 10485760 (10MB) | No |
| `SESSION_TIMEOUT_HOURS` | Session expiration | 24 | No |

*Required for AI-powered analysis and chat features. The application will run without these but with limited functionality.

### Frontend Configuration

**File: `frontend/public/config.json`**

```json
{
  "apiUrl": "http://localhost:5000"
}
```

For Docker deployment, use:
```json
{
  "apiUrl": "http://backend:5000"
}
```

### Docker Compose Configuration

**File: `docker-compose.yml`**

Key configurations:
- **Backend Port**: 5000
- **Frontend Port**: 3000
- **Network**: rpa-network (bridge)
- **Volumes**: 
  - backend-uploads (persistent file storage)
  - backend-database (persistent data storage)

## Troubleshooting

### Common Issues

#### Port Already in Use

**Problem**: Port 3000 or 5000 is already in use.

**Solution**:
1. Stop the conflicting service
2. Or modify `docker-compose.yml` to use different ports:

```yaml
services:
  backend:
    ports:
      - "5001:5000"  # Change host port
  frontend:
    ports:
      - "3001:3000"  # Change host port
```

#### Docker Build Fails

**Problem**: Docker build fails with dependency errors.

**Solution**:
1. Clear Docker cache:
```bash
docker-compose down
docker system prune -a
docker-compose up --build
```

2. Check Docker Desktop is running
3. Ensure sufficient disk space

#### Backend Cannot Connect to Azure OpenAI

**Problem**: AI service unavailable errors.

**Solution**:
1. Verify `.env` file exists in `backend/` directory
2. Check API key is correct
3. Verify endpoint URL format
4. Test API key with curl:

```bash
curl https://your-endpoint.openai.azure.com/openai/deployments/your-model/chat/completions?api-version=2024-02-15-preview \
  -H "Content-Type: application/json" \
  -H "api-key: YOUR_API_KEY" \
  -d '{"messages":[{"role":"user","content":"test"}]}'
```

#### Frontend Cannot Connect to Backend

**Problem**: Network errors when uploading files.

**Solution**:
1. Verify backend is running: http://localhost:5000/health
2. Check `public/config.json` has correct API URL
3. Check browser console for CORS errors
4. Verify CORS configuration in `backend/app.py`

#### PDF Upload Fails

**Problem**: File upload returns error.

**Solution**:
1. Check file size (must be under 10MB)
2. Verify file is a valid PDF
3. Check backend logs for detailed error
4. Ensure `uploads/` directory exists and is writable

#### Session Not Found

**Problem**: Chat returns "Session not found or expired".

**Solution**:
1. Session expired (24 hours) - re-upload PDF
2. Backend restarted - sessions are in-memory
3. Check `data/sessions.json` exists

### Development Tips

#### Viewing Logs

**Docker:**
```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

**Local Development:**
- Backend: Check terminal running `python app.py`
- Frontend: Check terminal running `npm run dev`

#### Restarting Services

**Docker:**
```bash
# Restart all
docker-compose restart

# Restart backend only
docker-compose restart backend

# Restart frontend only
docker-compose restart frontend
```

**Local Development:**
- Press `Ctrl+C` in terminal and restart command

#### Clearing Data

**Remove all sessions and uploads:**

```bash
# Docker
docker-compose down -v  # Removes volumes

# Local
rm -rf data/uploads/*
rm -rf uploads/*
echo "{}" > data/sessions.json
```

#### Hot Reload

- **Frontend**: Automatically reloads on file changes
- **Backend**: Automatically reloads in debug mode (FLASK_DEBUG=1)

## Testing the Installation

### 1. Health Check

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

### 2. Upload Test SF-424 PDF

1. Navigate to http://localhost:3000
2. Click "Go to Dashboard"
3. Drag and drop an SF-424 PDF file (use test files from `TestData/` directory)
4. Verify upload succeeds and returns file_id

### 3. Test Form Analysis

1. After uploading PDF, click "Analyze"
2. Wait for analysis to complete
3. Verify validation results are displayed:
   - Form status (Ready/Not Ready)
   - Validation errors (if any)
   - AI-generated troubleshooting guidance

### 4. Test Chat

1. Type a message in chat: "What is the UEI in this form?"
2. Verify AI responds with form-specific information
3. Try follow-up questions about form fields

## Next Steps

After successful setup:

1. **Review Documentation**
   - Read API Reference for endpoint details
   - Review Architecture documentation
   - Check Workflow Guide for development practices

2. **Explore Features**
   - Upload various SF-424 forms
   - Test validation with different scenarios
   - Experiment with chat interactions

3. **Development**
   - Set up your IDE (VS Code recommended)
   - Install recommended extensions
   - Review code structure

4. **Customize**
   - Modify validation rules
   - Adjust AI prompts
   - Customize UI theme

## IDE Setup (Optional)

### Visual Studio Code

**Recommended Extensions:**

- **Python**: ms-python.python
- **Pylance**: ms-python.vscode-pylance
- **ESLint**: dbaeumer.vscode-eslint
- **Prettier**: esbenp.prettier-vscode
- **Docker**: ms-azuretools.vscode-docker
- **Thunder Client**: rangav.vscode-thunder-client (API testing)

**Settings:**

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  }
}
```

### PyCharm

1. Open `backend` folder as project
2. Configure Python interpreter to use `.venv`
3. Enable Flask support
4. Set working directory to `backend/`

## Security Considerations

### Development Environment

- Never commit `.env` files
- Use `.env.example` as template
- Keep API keys secure
- Use different keys for dev/staging/prod

### Production Deployment

- Use environment variables (not .env files)
- Enable HTTPS/TLS
- Implement authentication
- Set up firewall rules
- Regular security updates

## Getting Help

If you encounter issues not covered here:

1. Check the logs for detailed error messages
2. Review the Troubleshooting section
3. Search existing issues in the repository
4. Create a new issue with:
   - Error message
   - Steps to reproduce
   - Environment details (OS, Docker version, etc.)
   - Relevant logs
