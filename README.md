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
│   ├── services/          # Business logic layer
│   │   ├── github_service.py      # Service layer for GitHub operations
│   │   └── github_api_client.py   # GitHub API communication
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

## API Access

After starting the server (using either Docker or Manual Setup), the API will be available at:

- **API Base URL**: http://localhost:8000/
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

### Authentication in Swagger UI / ReDoc

To use the interactive documentation (Swagger UI or ReDoc) with authentication:

#### In Swagger UI (http://localhost:8000/api/docs/):

1. Open the documentation in your browser
2. Look for the **"Authorize"** button (🔒) in the top right corner of the page
3. Click on the **"Authorize"** button
4. In the **"Value"** field, enter your GitHub token (only the token, without the word "Bearer")
5. Click **"Authorize"** and then **"Close"**
6. Now all requests you make from Swagger UI will automatically include the token in the `Authorization: Bearer <your_token>` header
7. The token will be saved during the session thanks to the `persistAuthorization` configuration

**Note**: Do not include the word "Bearer" when entering the token in Swagger UI, only the token itself. The system will automatically add the "Bearer" prefix.

#### In ReDoc (http://localhost:8000/api/redoc/):

ReDoc displays the API documentation but does not have an interactive authorization button. To use ReDoc, you need to make requests manually using tools like `curl` or Postman with the authorization header.

#### Example with curl:

```bash
curl -X GET "http://localhost:8000/api/v1/github/user-info/" \
     -H "Authorization: Bearer YOUR_GITHUB_TOKEN"
```

## Testing

```bash
python manage.py test
```
