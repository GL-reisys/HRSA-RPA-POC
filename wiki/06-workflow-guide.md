# Workflow Guide

## Development Workflows

This guide covers common development workflows and best practices for the HRSA RPA POC project.

## Git Workflow

### Branch Strategy

**Main Branches:**
- `main` - Production-ready code
- `develop` - Integration branch for features

**Supporting Branches:**
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Urgent production fixes
- `release/*` - Release preparation

### Feature Development Workflow

```bash
# 1. Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/add-validation-rule

# 2. Make changes and commit
git add .
git commit -m "Add new validation rule for EIN format"

# 3. Push to remote
git push origin feature/add-validation-rule

# 4. Create Pull Request
# - Target: develop
# - Add description and screenshots
# - Request review

# 5. After approval, merge and delete branch
git checkout develop
git pull origin develop
git branch -d feature/add-validation-rule
```

### Commit Message Convention

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```bash
feat(backend): add EIN validation rule

Implement validation for EIN format XX-XXXXXXX
with proper error messages and suggestions.

Closes #123

---

fix(frontend): resolve file upload timeout issue

Increase timeout for large file uploads and add
progress indicator for better UX.

Fixes #456

---

docs(wiki): update API reference with new endpoints

Add documentation for batch processing endpoints
and update examples.
```

## Development Environment Setup

### Daily Development Workflow

**1. Start Development Environment**

```bash
# Using Docker (recommended)
cd RPA-POC-AVA-app
docker-compose up

# Or local development
# Terminal 1 - Backend
cd backend
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
python app.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

**2. Make Changes**

- Edit code in your IDE
- Save files (hot reload enabled)
- Test changes in browser

**3. Test Changes**

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# Lint code
cd backend
flake8 .

cd frontend
npm run lint
```

**4. Commit Changes**

```bash
git add .
git commit -m "feat: your change description"
git push
```

## Backend Development Workflow

### Adding a New API Endpoint

**1. Create Controller Method**

`backend/controllers/your_controller.py`:

```python
from flask import Blueprint, request, jsonify

your_bp = Blueprint('your_feature', __name__)

@your_bp.route('/api/your-endpoint', methods=['POST'])
def your_endpoint():
    try:
        data = request.get_json()
        
        # Validate input
        if not data.get('required_field'):
            return jsonify({'error': 'required_field is missing'}), 400
        
        # Process request
        result = process_data(data)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

**2. Register Blueprint**

`backend/app.py`:

```python
from controllers.your_controller import your_bp

app.register_blueprint(your_bp)
```

**3. Add Service Logic**

`backend/services/your_service.py`:

```python
class YourService:
    def process_data(self, data):
        # Business logic here
        return result
```

**4. Write Tests**

`backend/tests/test_your_controller.py`:

```python
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_your_endpoint(client):
    response = client.post('/api/your-endpoint', 
                          json={'required_field': 'value'})
    assert response.status_code == 200
```

**5. Update Documentation**

- Add endpoint to `wiki/05-api-reference.md`
- Update README if needed

### Adding a New Validation Rule

**1. Update Validator**

`backend/services/sf424_validator.py`:

```python
def validate_form_data(self, form_data):
    errors = []
    
    # Add your validation rule
    if not self._validate_your_field(form_data.get('your_field')):
        errors.append({
            'field': 'your_field',
            'message': 'Validation error message',
            'severity': 'error'
        })
    
    return errors

def _validate_your_field(self, value):
    # Validation logic
    return is_valid
```

**2. Write Tests**

```python
def test_validate_your_field():
    validator = SF424Validator()
    assert validator._validate_your_field('valid_value') == True
    assert validator._validate_your_field('invalid_value') == False
```

**3. Update AI Prompt**

`backend/services/ai_service.py`:

Update the system prompt to include the new validation rule context.

## Frontend Development Workflow

### Adding a New Component

**1. Create Component File**

`frontend/app/components/YourComponent.js`:

```javascript
'use client';

import { useState } from 'react';
import { Box, Button, Typography } from '@mui/material';

export default function YourComponent({ prop1, prop2 }) {
  const [state, setState] = useState(null);
  
  const handleAction = async () => {
    // Component logic
  };
  
  return (
    <Box>
      <Typography variant="h6">Your Component</Typography>
      <Button onClick={handleAction}>Action</Button>
    </Box>
  );
}
```

**2. Import and Use**

```javascript
import YourComponent from './components/YourComponent';

export default function Page() {
  return (
    <YourComponent prop1="value" prop2="value" />
  );
}
```

**3. Add Styling**

Use Material-UI's `sx` prop or styled components:

```javascript
<Box sx={{
  padding: 2,
  backgroundColor: 'background.paper',
  borderRadius: 1
}}>
  {/* Content */}
</Box>
```

### Making API Calls

**1. Create API Service**

`frontend/app/services/api.js`:

```javascript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export async function yourApiCall(data) {
  const response = await fetch(`${API_URL}/api/your-endpoint`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error);
  }
  
  return response.json();
}
```

**2. Use in Component**

```javascript
import { yourApiCall } from '../services/api';

const handleSubmit = async () => {
  try {
    setLoading(true);
    const result = await yourApiCall(formData);
    setResult(result);
  } catch (error) {
    setError(error.message);
  } finally {
    setLoading(false);
  }
};
```

## Testing Workflow

### Backend Testing

**Run All Tests:**

```bash
cd backend
pytest
```

**Run Specific Test:**

```bash
pytest tests/test_your_controller.py::test_your_endpoint
```

**Run with Coverage:**

```bash
pytest --cov=. --cov-report=html
```

**Test Structure:**

```
backend/tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_controllers/
│   ├── test_document_controller.py
│   └── test_pdf_validation_controller.py
├── test_services/
│   ├── test_pdf_validator.py
│   └── test_sf424_validator.py
└── test_utils/
    └── test_pdf_reader.py
```

### Frontend Testing

**Run Tests:**

```bash
cd frontend
npm test
```

**Run with Coverage:**

```bash
npm test -- --coverage
```

**Test Example:**

```javascript
import { render, screen, fireEvent } from '@testing-library/react';
import YourComponent from './YourComponent';

describe('YourComponent', () => {
  it('renders correctly', () => {
    render(<YourComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
  
  it('handles click event', () => {
    const handleClick = jest.fn();
    render(<YourComponent onClick={handleClick} />);
    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalled();
  });
});
```

## Debugging Workflow

### Backend Debugging

**1. Enable Debug Mode**

`.env`:
```
FLASK_DEBUG=1
```

**2. Add Breakpoints**

```python
import pdb; pdb.set_trace()  # Python debugger
```

**3. View Logs**

```bash
# Docker
docker-compose logs -f backend

# Local
# Logs appear in terminal running app.py
```

**4. Test with cURL**

```bash
curl -X POST http://localhost:5000/api/your-endpoint \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}' \
  -v  # Verbose output
```

### Frontend Debugging

**1. Browser DevTools**

- Open DevTools (F12)
- Check Console for errors
- Use Network tab for API calls
- Use React DevTools extension

**2. Add Console Logs**

```javascript
console.log('Debug:', variable);
console.error('Error:', error);
console.table(arrayData);
```

**3. Use Debugger**

```javascript
debugger;  // Pauses execution in DevTools
```

**4. Check Next.js Logs**

Terminal running `npm run dev` shows:
- Compilation errors
- Runtime errors
- API route logs

## Code Review Workflow

### Creating a Pull Request

**1. Prepare PR**

```bash
# Ensure branch is up to date
git checkout develop
git pull origin develop
git checkout your-branch
git rebase develop

# Run tests
pytest  # Backend
npm test  # Frontend

# Lint code
flake8 .  # Backend
npm run lint  # Frontend
```

**2. Create PR**

- Go to GitHub repository
- Click "New Pull Request"
- Select base: `develop`, compare: `your-branch`
- Fill in template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added new tests
- [ ] Manual testing completed

## Screenshots (if applicable)
[Add screenshots]

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No console warnings
```

**3. Request Review**

- Assign reviewers
- Add labels
- Link related issues

### Reviewing a Pull Request

**1. Code Review Checklist**

- [ ] Code is readable and maintainable
- [ ] Follows project conventions
- [ ] No unnecessary complexity
- [ ] Error handling is appropriate
- [ ] Tests are comprehensive
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance is acceptable

**2. Testing the PR**

```bash
# Checkout PR branch
git fetch origin
git checkout pr-branch-name

# Test locally
docker-compose up --build

# Run tests
pytest
npm test
```

**3. Provide Feedback**

- Be constructive and specific
- Suggest improvements
- Ask questions for clarification
- Approve when ready

## Database Migration Workflow (Future)

When migrating to PostgreSQL:

**1. Create Migration**

```bash
cd backend
alembic revision -m "Add new table"
```

**2. Edit Migration File**

`alembic/versions/xxx_add_new_table.py`:

```python
def upgrade():
    op.create_table(
        'your_table',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False)
    )

def downgrade():
    op.drop_table('your_table')
```

**3. Run Migration**

```bash
alembic upgrade head
```

**4. Test Migration**

```bash
# Test downgrade
alembic downgrade -1

# Test upgrade
alembic upgrade head
```

## Deployment Workflow

### Staging Deployment

**1. Merge to Develop**

```bash
git checkout develop
git merge feature/your-feature
git push origin develop
```

**2. Deploy to Staging**

```bash
# Automated via CI/CD or manual:
docker-compose -f docker-compose.staging.yml up -d
```

**3. Verify Deployment**

- Check health endpoints
- Run smoke tests
- Verify logs

### Production Deployment

**1. Create Release Branch**

```bash
git checkout develop
git checkout -b release/v1.1.0
```

**2. Update Version**

Update version in:
- `backend/app.py`
- `frontend/package.json`
- `CHANGELOG.md`

**3. Test Release**

```bash
# Run full test suite
pytest
npm test

# Manual testing
```

**4. Merge to Main**

```bash
git checkout main
git merge release/v1.1.0
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin main --tags
```

**5. Deploy to Production**

```bash
# Via CI/CD or manual deployment
```

**6. Monitor**

- Check logs
- Monitor metrics
- Verify functionality

## Troubleshooting Workflow

### Issue Occurs

**1. Reproduce the Issue**

- Document steps to reproduce
- Note environment details
- Capture error messages

**2. Check Logs**

```bash
# Docker
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Local
# Check terminal output
```

**3. Debug**

- Add logging statements
- Use debugger
- Check API responses
- Verify environment variables

**4. Fix and Test**

- Implement fix
- Write test to prevent regression
- Verify fix works

**5. Document**

- Update troubleshooting guide
- Add to FAQ if common issue

## Performance Optimization Workflow

**1. Identify Bottleneck**

- Use profiling tools
- Check logs for slow operations
- Monitor resource usage

**2. Optimize**

- Backend: Optimize queries, add caching
- Frontend: Code splitting, lazy loading
- Database: Add indexes, optimize queries

**3. Measure**

- Compare before/after metrics
- Ensure optimization works
- Check for side effects

**4. Document**

- Note optimization in comments
- Update performance documentation

## Best Practices

### Code Quality

- Write self-documenting code
- Keep functions small and focused
- Follow DRY principle
- Use meaningful variable names
- Add comments for complex logic

### Testing

- Write tests before fixing bugs
- Aim for high test coverage
- Test edge cases
- Mock external dependencies

### Git

- Commit often with clear messages
- Keep commits atomic
- Pull before pushing
- Resolve conflicts carefully

### Documentation

- Update docs with code changes
- Include examples
- Keep README current
- Document breaking changes

### Security

- Never commit secrets
- Validate all inputs
- Use environment variables
- Keep dependencies updated
- Follow security best practices
