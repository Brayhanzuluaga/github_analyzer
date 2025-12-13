# GitHub Analyzer API

REST API service to extract authenticated GitHub user information in JSON format.

## Requirements

- Python >= 3.12
- pip

## Installation

1. **Create virtual environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python -m venv venv
source venv/bin/activate
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure environment**

Create a `.env` file (optional, it will use defaults):

```
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
```

4. **Run migrations**

```bash
python manage.py migrate
```

5. **Start server**

```bash
python manage.py runserver
```

The API will be available at: http://localhost:8000/

## API Documentation

- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

## Project Structure

```
github_analyzer/
├── config/              # Django project configuration
├── github_api/          # Main application
│   ├── controllers/     # HTTP handlers
│   ├── services/        # Business logic
│   ├── repositories/    # GitHub API integration
│   └── schemas/         # Request/Response validation
├── manage.py
└── requirements.txt
```

## Technology Stack

- Django 5.0
- Django REST Framework
- Python 3.12+
- httpx (HTTP client)
- Pydantic (validation)
