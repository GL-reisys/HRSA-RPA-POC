# Technology Stack

## Overview

The HRSA RPA POC uses a modern, containerized full-stack architecture with AI capabilities.

## Frontend Technologies

### Core Framework
- **Next.js 14.0.4**: React framework with server-side rendering and routing
- **React 18.2.0**: UI component library
- **React DOM 18.2.0**: React rendering for web

### UI Components & Styling
- **Material-UI (@mui/material) 5.15.0**: Comprehensive React component library
- **Material Icons (@mui/icons-material) 5.15.0**: Icon library
- **Emotion 11.11.x**: CSS-in-JS styling solution
  - @emotion/react
  - @emotion/styled

### Additional Libraries
- **Axios 1.6.2**: HTTP client for API communication
- **React Dropzone 14.2.3**: Drag-and-drop file upload component

### Development Tools
- **ESLint 8.55.0**: Code linting and quality
- **eslint-config-next**: Next.js-specific ESLint configuration

## Backend Technologies

### Core Framework
- **Flask 3.0.0**: Lightweight Python web framework
- **Flask-CORS 4.0.0**: Cross-Origin Resource Sharing support
- **Werkzeug 3.0.1**: WSGI utility library

### PDF Processing
- **pikepdf 9.4.2**: XFA form extraction and PDF manipulation
- **lxml 5.3.0**: XML parsing for XFA data structures
- **Pillow 10.4.0**: Image processing support

### AI Integration
- **OpenAI 1.58.1**: Azure OpenAI SDK for AI-powered validation and chat
- **Pydantic 2.10.6**: Data validation and settings management

### Utilities
- **python-dotenv 1.0.0**: Environment variable management
- **python-multipart 0.0.9**: Multipart form data parsing
- **APScheduler 3.10.4**: Background job scheduling for session cleanup

### Database (Future)
- **psycopg2-binary 2.9.9**: PostgreSQL adapter (ready for migration)

## Infrastructure

### Containerization
- **Docker**: Container platform for consistent environments
- **Docker Compose 3.8**: Multi-container orchestration

### Version Control
- **Git**: Source control management
- **GitHub**: Repository hosting and collaboration

## Development Environment

### Required Software
- **Node.js 18+**: JavaScript runtime for frontend
- **Python 3.11+**: Python runtime for backend
- **Docker Desktop**: Container management
- **Git**: Version control client

### Recommended IDEs
- **Visual Studio Code**: Lightweight, extensible editor
- **PyCharm**: Python-focused IDE
- **WebStorm**: JavaScript/React IDE

### Browser Support
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## External Services

### Azure OpenAI
- **Service**: Azure OpenAI Service
- **Model**: GPT-4 (configurable via AZURE_OPENAI_DEPLOYMENT)
- **API Version**: 2024-08-01-preview
- **Purpose**: 
  - SF-424 form analysis and troubleshooting guidance
  - Interactive chat with form context
  - Validation error explanations
- **Configuration**: Via environment variables (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT)

## Data Storage

### Current (POC)
- **Format**: JSON files
- **Location**: `backend/data/` directory
- **Files**:
  - `sessions.json`: Session data with chat history
  - `documents.json`: Document metadata (legacy)
  - `uploads/`: PDF file storage
  - `mock_database.json`: Mock database for UEI, Funding Opportunities, Organizations

### Future (Production)
- **Database**: PostgreSQL 14+
- **ORM**: SQLAlchemy (planned)
- **Migration**: Alembic (planned)
- **Tables**: Organizations, FundingCycles, ValidationErrors

## Networking

### Ports
- **Frontend**: 3000 (HTTP)
- **Backend**: 5000 (HTTP)

### Docker Network
- **Name**: rpa-network
- **Driver**: bridge
- **Purpose**: Inter-container communication

## Security Considerations

### Current Implementation
- CORS configuration for frontend-backend communication
- File size limits (10MB max)
- Environment variable protection
- Session-based isolation

### Future Enhancements
- Authentication and authorization
- HTTPS/TLS encryption
- API rate limiting
- Input sanitization and validation
- Secure file storage with encryption

## Performance Optimization

### Frontend
- Next.js automatic code splitting
- Image optimization
- Static asset caching

### Backend
- Background job scheduling
- Session cleanup automation
- Efficient PDF processing

## Monitoring & Logging

### Current
- Flask debug logging
- Console output for development

### Planned
- Application Performance Monitoring (APM)
- Centralized logging (ELK stack)
- Error tracking (Sentry)
- Health check endpoints

## CI/CD (Planned)

### GitHub Actions
- Automated testing
- Code quality checks
- Docker image building
- Deployment automation

## Technology Decisions

### Why Next.js?
- Server-side rendering for better SEO
- Built-in routing and API routes
- Excellent developer experience
- Strong community support

### Why Flask?
- Lightweight and flexible
- Easy to integrate with Python libraries
- Excellent for microservices
- Simple deployment

### Why Material-UI?
- Comprehensive component library
- Consistent design system
- Accessibility built-in
- Active development and support

### Why JSON Storage (POC)?
- Quick setup for proof of concept
- Easy to inspect and debug
- PostgreSQL-ready structure
- No database infrastructure needed initially

### Why Docker?
- Consistent development environments
- Easy deployment
- Isolation and security
- Scalability for production
