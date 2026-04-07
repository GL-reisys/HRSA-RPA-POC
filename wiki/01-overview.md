# Project Overview

## HRSA RPA POC - Application Validation Assistant (AVA)

### Purpose

The HRSA RPA POC project is an AI-powered Application Validation Assistant (AVA) designed to automate and streamline the validation of SF-424 grant application forms. The system leverages Azure OpenAI to provide intelligent form validation, data extraction, and interactive assistance for grant application processing.

### Key Objectives

- **Automated PDF Processing**: Extract and validate data from SF-424 PDF forms
- **AI-Powered Validation**: Use Azure OpenAI to intelligently validate form fields and identify errors
- **Interactive Chat Interface**: Provide real-time assistance and guidance through conversational AI
- **Document Management**: Track and manage uploaded documents with validation history
- **Session Management**: Maintain user context across multiple interactions

### Target Users

- Grant application reviewers
- HRSA administrative staff
- Grant applicants seeking validation assistance

### Business Value

- **Efficiency**: Reduce manual review time by automating initial validation
- **Accuracy**: Minimize human error through consistent AI-powered validation
- **User Experience**: Provide immediate feedback and guidance to users
- **Scalability**: Handle multiple concurrent validation sessions
- **Audit Trail**: Maintain comprehensive logs of validation activities

### Project Status

**Current Phase**: Proof of Concept (POC)

The application is in active development with core features implemented:
- ✅ XFA PDF field extraction
- ✅ SF-424 form field mapping
- ✅ Database-driven validation (UEI, Funding Opportunity, Grant Number)
- ✅ Azure OpenAI integration for AI-powered analysis
- ✅ Interactive chat interface with form context
- ✅ Session management with automatic cleanup
- ✅ Document upload and storage
- ✅ Validation error messaging (user-friendly + AI context)
- 🔄 Frontend UI enhancements (in progress)
- 🔄 Comprehensive testing suite (in progress)

### Key Features

1. **XFA PDF Processing**
   - Drag-and-drop file upload with validation
   - XFA form field extraction from SF-424 PDFs
   - Automatic field mapping to SF-424 data structure
   - PDF structure validation (XFA/AcroForm detection)

2. **Database-Driven Validation**
   - UEI (Unique Entity Identifier) verification against mock database
   - Funding Opportunity Number validation
   - Application Type validation (New/Continuation/Revision)
   - Grant Number validation for continuation/revision applications
   - Business rule enforcement based on funding opportunity constraints

3. **AI-Powered Analysis**
   - Azure OpenAI integration for intelligent form analysis
   - Context-aware troubleshooting guidance
   - Validation error explanations with actionable steps
   - HTML-formatted responses for rich UI display

4. **Interactive Chat Interface**
   - Real-time Q&A about uploaded SF-424 forms
   - Contextual assistance based on form data and validation results
   - Session-based conversation history
   - Form field extraction for relevant context

5. **Session Management**
   - UUID-based session tracking per uploaded file
   - Automatic session expiration (24 hours)
   - Background cleanup scheduler (hourly)
   - Chat history persistence within sessions

### Technology Approach

The project uses a modern full-stack architecture:
- **Frontend**: Next.js 14 with Material-UI for responsive, modern UI
- **Backend**: Flask API with Python for robust server-side processing
- **AI Integration**: Azure OpenAI for intelligent validation and chat
- **Data Storage**: JSON-based storage (PostgreSQL-ready for production)
- **Containerization**: Docker for consistent deployment environments

### Future Roadmap

- **Phase 2**: PostgreSQL database integration
- **Phase 3**: Advanced analytics and reporting
- **Phase 4**: Multi-form support beyond SF-424
- **Phase 5**: Production deployment with authentication
