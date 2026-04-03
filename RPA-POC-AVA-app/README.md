# RPA POC AVA Application

A proof-of-concept application for automated PDF document validation with a Next.js frontend and Flask backend.

## 🏗️ Architecture

- **Frontend**: Next.js 14 with Material-UI
- **Backend**: Python Flask API with PDF validation
- **Data Storage**: JSON file (PostgreSQL-ready structure)
- **Containerization**: Docker & Docker Compose

## 📋 Features

- PDF document upload with drag-and-drop support
- Automated PDF validation (file type, size, content extraction)
- Document management (list, view, delete)
- RESTful API with CORS support
- Responsive Material-UI interface
- Docker containerization for easy deployment

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd RPA-POC-AVA-app
```

2. Start the application:
```bash
docker-compose up --build
```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000

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

4. Initialize database:
```bash
python database/init_db.py
```

5. (Optional) Seed sample data:
```bash
python database/seed_data.py
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

### Documents

- `POST /api/documents/upload` - Upload and validate a PDF document
- `GET /api/documents` - Get all documents
- `GET /api/documents/<id>` - Get a specific document
- `PUT /api/documents/<id>` - Update document metadata
- `DELETE /api/documents/<id>` - Delete a document

### Health Check

- `GET /health` - Check API health status

## 📁 Project Structure

```
RPA-POC-AVA-app/
├── backend/
│   ├── config/              # Database configuration
│   ├── database/            # DB initialization & data storage
│   ├── services/            # Business logic (PDF validation)
│   ├── controllers/         # API endpoints (DocumentController)
│   ├── utils/               # Utility functions (PDF reader)
│   ├── app.py              # Main Flask application
│   ├── Dockerfile          # Backend container
│   └── requirements.txt    # Python dependencies
│
├── frontend/
│   ├── app/
│   │   ├── components/     # React components
│   │   ├── dashboard/      # Dashboard page
│   │   ├── styles/         # CSS styles
│   │   ├── layout.js       # Root layout
│   │   └── page.js         # Landing page
│   ├── public/
│   │   └── config.json     # Environment configuration
│   ├── Dockerfile          # Frontend container
│   └── package.json        # Node dependencies
│
├── .github/workflows/      # CI/CD pipelines
├── docker-compose.yml      # Docker orchestration
└── README.md              # This file
```

## 🔧 Configuration

### Backend Configuration

The backend uses a JSON file for data storage that mimics PostgreSQL structure:

- Database file: `backend/database/data.json`
- Upload directory: `backend/uploads/`
- Max file size: 50MB

### Frontend Configuration

Update `frontend/public/config.json` to change the API URL:

```json
{
  "apiUrl": "http://localhost:5000"
}
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
python -m pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 🔄 Migration to PostgreSQL

The JSON database structure is designed for easy migration to PostgreSQL:

1. Install PostgreSQL and SQLAlchemy:
```bash
pip install psycopg2-binary sqlalchemy
```

2. Update `config/database.py` to use SQLAlchemy ORM
3. Create PostgreSQL tables matching the JSON structure
4. Update connection strings in environment variables

## 📝 Environment Variables

### Backend

- `FLASK_ENV`: Development/Production mode
- `FLASK_DEBUG`: Enable debug mode (1/0)

### Frontend

- `NEXT_PUBLIC_API_URL`: Backend API URL

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
- **PDF validation fails**: Ensure the PDF is not corrupted and is under 50MB

### Frontend Issues

- **Cannot connect to backend**: Check that backend is running and `config.json` has correct API URL
- **Build fails**: Delete `node_modules` and `.next` folders, then run `npm install` again

### Docker Issues

- **Container won't start**: Check logs with `docker-compose logs`
- **Volume permission issues**: Ensure Docker has proper permissions to mount volumes

## 📞 Support

For issues and questions, please open an issue in the repository.
