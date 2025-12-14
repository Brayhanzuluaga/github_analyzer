# GitHub Analyzer API

REST API service built with Django to extract authenticated GitHub user information.

## What it does

This API provides a single endpoint to extract comprehensive GitHub user information:

- Public and private repositories
- Organizations membership
- Pull requests

## Technology Stack

- **Python**: >= 3.12
- **Django**: 5.0
- **Django REST Framework**: 3.14+
- **httpx**: HTTP client for GitHub API
- **drf-spectacular**: OpenAPI/Swagger documentation

## Project Structure

```
github_analyzer/
├── github_analyzer/        # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── github_api/             # Main Django app
│   ├── views.py           # API views/endpoints
│   ├── serializers.py     # DRF serializers for validation
│   ├── services.py        # Business logic layer
│   ├── api_client.py      # GitHub API communication
│   ├── models.py          # Database models (empty - stateless API)
│   ├── tests.py           # Test cases
│   └── urls.py            # URL routing
│
├── manage.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Quick Start

### Option 1: Docker (Recommended)

```bash
docker-compose up --build
```

The API will be available at: http://localhost:8000/

### Option 2: Manual Setup

1. **Create and activate virtual environment:**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python -m venv venv
source venv/bin/activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Run migrations:**

```bash
python manage.py migrate
```

4. **Start server:**

```bash
python manage.py runserver
```

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/

## Usage

### Endpoint

```
GET /api/v1/github/user-info/
```

### Authentication

Provide a GitHub Personal Access Token in the Authorization header:

```bash
curl -X GET "http://localhost:8000/api/v1/github/user-info/" \
     -H "Authorization: Bearer YOUR_GITHUB_TOKEN"
```

### GitHub Token Setup

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`, `read:user`
4. Generate and copy your token

## Testing

```bash
python manage.py test
```
