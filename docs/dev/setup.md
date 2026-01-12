# Developer Setup

This guide covers setting up a development environment for Tractor.

## Prerequisites

- Python 3.10 or later
- Node.js 18 or later
- PostgreSQL 15
- Docker (optional, for database)

## Backend Setup

```bash
# Clone the repository
git clone https://github.com/msped/tractor
cd tractor

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

In a separate terminal, start the task queue:

```bash
python manage.py qcluster
```

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start the development server
npm run dev
```

The application will be available at `http://localhost:3000`.

## Running Tests

### Backend

```bash
python manage.py test                           # Run all tests
python manage.py test cases.tests.test_views    # Run specific module
coverage run manage.py test && coverage report  # With coverage (90% threshold)
```

### Frontend

```bash
cd frontend
npm run cy:run      # Headless
npm run cy:open     # Interactive
npm run cy:test     # With coverage (80% threshold)
```

## WeasyPrint (macOS)

If PDF export fails with library errors:

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
```

## Environment Variables

### Backend (.env)

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret key for cryptographic signing |
| `JWT_SIGNING_KEY` | Key for signing JWT tokens |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `DJANGO_SETTINGS_MODULE` | Django settings module path (e.g., `backend.settings`) |

### Frontend (frontend/.env)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_HOST` | Backend API URL (e.g., `http://localhost:8000`) |
| `AUTH_SECRET` | NextAuth secret for session encryption |
| `AUTH_MICROSOFT_ENTRA_ID_ID` | Microsoft Entra ID client ID (optional) |
| `AUTH_MICROSOFT_ENTRA_ID_SECRET` | Microsoft Entra ID client secret (optional) |
| `AUTH_MICROSOFT_ENTRA_ID_ISSUER` | Microsoft Entra ID issuer URL (optional) |

!!! note
    The Microsoft Entra ID variables are only required if SSO is being configured.
