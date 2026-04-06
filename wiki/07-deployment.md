# Deployment Guide

## Deployment Overview

This guide covers deploying the HRSA RPA POC application to various environments.

## Deployment Environments

### Development
- **Purpose**: Local development and testing
- **Setup**: Docker Compose or local installation
- **URL**: http://localhost:3000

### Staging
- **Purpose**: Pre-production testing
- **Setup**: Docker Compose on staging server
- **URL**: https://staging.example.com

### Production
- **Purpose**: Live application
- **Setup**: Docker Compose or Kubernetes
- **URL**: https://app.example.com

## Prerequisites

### Server Requirements

**Minimum Specifications:**
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 20 GB
- **OS**: Ubuntu 20.04+ / Windows Server 2019+ / RHEL 8+

**Recommended Specifications:**
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **OS**: Ubuntu 22.04 LTS

### Software Requirements

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- SSL certificates (for production)

### Network Requirements

- **Inbound Ports**:
  - 80 (HTTP)
  - 443 (HTTPS)
  - 22 (SSH for management)

- **Outbound Access**:
  - Azure OpenAI API endpoints
  - Package repositories (npm, PyPI)
  - Docker Hub

## Docker Deployment

### Basic Docker Compose Deployment

**1. Clone Repository**

```bash
git clone <repository-url>
cd HRSA-RPA-POC/RPA-POC-AVA-app
```

**2. Configure Environment**

Create `backend/.env`:

```env
FLASK_ENV=production
FLASK_DEBUG=0

AZURE_OPENAI_API_KEY=your-production-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment
AZURE_OPENAI_API_VERSION=2024-02-15-preview

MAX_FILE_SIZE=10485760
SESSION_TIMEOUT_HOURS=24
```

**3. Update Frontend Configuration**

Edit `frontend/public/config.json`:

```json
{
  "apiUrl": "https://api.yourdomain.com"
}
```

**4. Build and Start**

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

**5. Verify Deployment**

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs -f

# Test health endpoint
curl http://localhost:5000/health
```

### Production Docker Compose Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: rpa-poc-backend-prod
    restart: always
    ports:
      - "5000:5000"
    volumes:
      - backend-uploads:/app/uploads
      - backend-data:/app/data
    environment:
      - FLASK_ENV=production
      - FLASK_DEBUG=0
    env_file:
      - ./backend/.env
    networks:
      - rpa-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    container_name: rpa-poc-frontend-prod
    restart: always
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=https://api.yourdomain.com
    depends_on:
      - backend
    networks:
      - rpa-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: rpa-poc-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    networks:
      - rpa-network

networks:
  rpa-network:
    driver: bridge

volumes:
  backend-uploads:
  backend-data:
```

### Production Dockerfile

**Backend Dockerfile.prod:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
```

**Frontend Dockerfile.prod:**

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM node:18-alpine

WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001
USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
```

## Nginx Configuration

### Reverse Proxy Setup

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:5000;
    }

    upstream frontend {
        server frontend:3000;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # Frontend
    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        client_max_body_size 10M;

        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # Backend API
    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        client_max_body_size 10M;

        location / {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
        }
    }
}
```

## SSL/TLS Configuration

### Using Let's Encrypt

**1. Install Certbot**

```bash
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx
```

**2. Obtain Certificate**

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com -d api.yourdomain.com
```

**3. Auto-Renewal**

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot automatically sets up cron job
```

**4. Copy Certificates to Docker**

```bash
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
```

## Environment Variables

### Production Environment Variables

**Backend (.env):**

```env
# Flask
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=your-secret-key-here

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-production-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Application
MAX_FILE_SIZE=10485760
SESSION_TIMEOUT_HOURS=24
UPLOAD_FOLDER=/app/uploads
DATA_FOLDER=/app/data

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log

# Security
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Frontend:**

```env
NODE_ENV=production
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## Database Migration (PostgreSQL)

### Setting Up PostgreSQL

**1. Add PostgreSQL to Docker Compose**

```yaml
services:
  postgres:
    image: postgres:14-alpine
    container_name: rpa-poc-postgres
    restart: always
    environment:
      POSTGRES_DB: rpa_poc
      POSTGRES_USER: rpa_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - rpa-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rpa_user"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
```

**2. Update Backend Configuration**

```env
DATABASE_URL=postgresql://rpa_user:password@postgres:5432/rpa_poc
```

**3. Run Migrations**

```bash
docker-compose exec backend alembic upgrade head
```

## Monitoring and Logging

### Application Logging

**Backend Logging Configuration:**

```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10240000,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')
```

### Docker Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f backend

# View last 100 lines
docker-compose logs --tail=100 backend

# Save logs to file
docker-compose logs > deployment.log
```

### Log Aggregation (Optional)

**Using ELK Stack:**

1. Add Elasticsearch, Logstash, Kibana to docker-compose
2. Configure log shipping
3. Create dashboards in Kibana

## Backup and Recovery

### Backup Strategy

**1. Database Backup (PostgreSQL)**

```bash
# Create backup
docker-compose exec postgres pg_dump -U rpa_user rpa_poc > backup_$(date +%Y%m%d).sql

# Automated daily backup
0 2 * * * /path/to/backup-script.sh
```

**2. File Storage Backup**

```bash
# Backup uploads
docker run --rm -v rpa-poc-backend-uploads:/data -v $(pwd):/backup \
  alpine tar czf /backup/uploads_$(date +%Y%m%d).tar.gz /data

# Backup data
docker run --rm -v rpa-poc-backend-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/data_$(date +%Y%m%d).tar.gz /data
```

**3. Configuration Backup**

```bash
# Backup configs
tar czf config_backup_$(date +%Y%m%d).tar.gz \
  docker-compose.prod.yml \
  nginx/ \
  backend/.env
```

### Recovery Procedure

**1. Restore Database**

```bash
docker-compose exec -T postgres psql -U rpa_user rpa_poc < backup_20240115.sql
```

**2. Restore Files**

```bash
docker run --rm -v rpa-poc-backend-uploads:/data -v $(pwd):/backup \
  alpine tar xzf /backup/uploads_20240115.tar.gz -C /
```

## Scaling

### Horizontal Scaling

**1. Multiple Backend Instances**

```yaml
services:
  backend:
    deploy:
      replicas: 3
```

**2. Load Balancer Configuration**

Update nginx upstream:

```nginx
upstream backend {
    least_conn;
    server backend-1:5000;
    server backend-2:5000;
    server backend-3:5000;
}
```

### Vertical Scaling

**Increase Container Resources:**

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Security Hardening

### Production Security Checklist

- [ ] Use HTTPS/TLS for all connections
- [ ] Set secure environment variables
- [ ] Enable firewall (UFW/iptables)
- [ ] Disable debug mode
- [ ] Use non-root users in containers
- [ ] Keep dependencies updated
- [ ] Implement rate limiting
- [ ] Set up fail2ban for SSH
- [ ] Regular security audits
- [ ] Backup encryption
- [ ] API key rotation policy
- [ ] Monitor for vulnerabilities

### Firewall Configuration

```bash
# UFW setup
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Health Checks and Monitoring

### Health Check Endpoints

```bash
# Backend health
curl https://api.yourdomain.com/health

# Frontend health
curl https://yourdomain.com/

# Expected response
{"status":"healthy","active_sessions":5}
```

### Monitoring Script

```bash
#!/bin/bash
# monitor.sh

BACKEND_URL="https://api.yourdomain.com/health"
FRONTEND_URL="https://yourdomain.com"

# Check backend
if curl -f -s $BACKEND_URL > /dev/null; then
    echo "Backend: OK"
else
    echo "Backend: FAILED"
    # Send alert
fi

# Check frontend
if curl -f -s $FRONTEND_URL > /dev/null; then
    echo "Frontend: OK"
else
    echo "Frontend: FAILED"
    # Send alert
fi
```

## Deployment Checklist

### Pre-Deployment

- [ ] Code reviewed and approved
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Environment variables configured
- [ ] SSL certificates obtained
- [ ] Backup created
- [ ] Rollback plan prepared

### Deployment

- [ ] Pull latest code
- [ ] Build Docker images
- [ ] Run database migrations
- [ ] Start containers
- [ ] Verify health checks
- [ ] Test critical functionality
- [ ] Monitor logs for errors

### Post-Deployment

- [ ] Verify all services running
- [ ] Test user workflows
- [ ] Check performance metrics
- [ ] Monitor error rates
- [ ] Update status page
- [ ] Notify stakeholders

## Troubleshooting Deployment Issues

### Container Won't Start

```bash
# Check logs
docker-compose logs backend

# Check container status
docker-compose ps

# Inspect container
docker inspect rpa-poc-backend-prod
```

### Database Connection Issues

```bash
# Test database connectivity
docker-compose exec backend python -c "from config.database import test_connection; test_connection()"

# Check PostgreSQL logs
docker-compose logs postgres
```

### SSL Certificate Issues

```bash
# Test SSL
openssl s_client -connect yourdomain.com:443

# Check certificate expiry
echo | openssl s_client -servername yourdomain.com -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates
```

## Rollback Procedure

**1. Stop Current Deployment**

```bash
docker-compose down
```

**2. Checkout Previous Version**

```bash
git checkout v1.0.0  # Previous stable version
```

**3. Restore Database (if needed)**

```bash
docker-compose exec -T postgres psql -U rpa_user rpa_poc < backup_previous.sql
```

**4. Start Previous Version**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**5. Verify**

```bash
curl https://api.yourdomain.com/health
```

## Maintenance

### Regular Maintenance Tasks

**Daily:**
- Monitor logs for errors
- Check disk space
- Verify backups completed

**Weekly:**
- Review performance metrics
- Check for security updates
- Clean up old logs

**Monthly:**
- Update dependencies
- Review and rotate logs
- Test backup restoration
- Security audit

### Updating the Application

```bash
# 1. Backup current state
./backup.sh

# 2. Pull latest changes
git pull origin main

# 3. Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# 4. Run migrations
docker-compose exec backend alembic upgrade head

# 5. Verify deployment
curl https://api.yourdomain.com/health
```

## Support and Escalation

### Incident Response

**Severity Levels:**

- **P1 (Critical)**: Service down, data loss
- **P2 (High)**: Major feature broken
- **P3 (Medium)**: Minor feature issue
- **P4 (Low)**: Cosmetic issue

**Response Times:**

- P1: Immediate
- P2: 2 hours
- P3: 1 business day
- P4: Next sprint

### Contact Information

- **DevOps Team**: devops@example.com
- **On-Call**: +1-XXX-XXX-XXXX
- **Slack Channel**: #rpa-poc-alerts
