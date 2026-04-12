# Developer Setup

This guide covers setting up a development environment for Tractor.

## Prerequisites

- Python 3.13 or later
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18 or later
- PostgreSQL 15 **or** MySQL 8.0+ (see [Database Configuration](#database-configuration))
- Docker (optional, for database)
- [Ollama](https://ollama.com/) (optional, for contextual AI redaction)

## Backend Setup

```bash
# Clone the repository
git clone https://github.com/msped/tractor
cd tractor

# Create and activate virtual environment
uv venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
uv sync

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

## Linting

### Backend linting

```bash
ruff check .          # Run linter
ruff format --check . # Check formatting
ruff format .         # Auto-format code
```

### Frontend linting

```bash
cd frontend
npm run lint          # Run ESLint
```

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

!!! note
    The pages directory is required by Cypress to stop the following error: ```Error:   x   Using `export * from '...'` in a page is disallowed. Please use `export { default } from '...'` instead.```

## Ollama (Contextual AI)

Tractor can use a locally-hosted LLM via [Ollama](https://ollama.com/) to perform contextual analysis of documents. This is optional — the other three NLP models work without it.

### Install and start Ollama

Download and install Ollama from [ollama.com](https://ollama.com/), then pull the model:

```bash
ollama pull gemma3:1b
```

Ollama must be running before starting the Django server. On macOS it starts automatically as a background service after installation. To verify it is running:

```bash
curl http://localhost:11434/api/tags
```

### Enable in Django

Set the following in your `.env`:

```bash
OLLAMA_ENABLED=True
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:1b
```

If `OLLAMA_ENABLED` is not set or is `False`, the Gemma extraction stage is skipped entirely and document processing continues with the other three models.

### Customise chunking (optional)

Large documents are split into overlapping chunks before being sent to Ollama. The defaults work for most cases:

```bash
OLLAMA_CHUNK_SIZE=4000    # characters per chunk (default: 4000)
OLLAMA_CHUNK_OVERLAP=200  # overlap between chunks (default: 200)
```

---

## WeasyPrint (macOS)

If PDF export fails with library errors:

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
```

## Database Configuration

Tractor supports PostgreSQL and MySQL. Configure the connection using **one** of the two methods below — `DATABASE_URL` takes priority if both are set.

### Option A: Connection URL (recommended)

Set a single `DATABASE_URL` variable in `.env`. The URL scheme selects the database engine automatically:

| Scheme             | Engine     | Example                                            |
|--------------------|------------|----------------------------------------------------|
| `postgresql://`    | PostgreSQL | `postgresql://user:pass@localhost:5432/tractor`    |
| `mysql://`         | MySQL      | `mysql://user:pass@localhost:3306/tractor`         |

```bash
# .env
DATABASE_URL="postgresql://tractor:secret@localhost:5432/tractor"
```

### Option B: Individual variables (legacy / Docker Compose default)

If `DATABASE_URL` is not set, the app falls back to the individual `POSTGRES_*` variables. This is the existing behaviour and requires no changes for current deployments.

```bash
# .env
POSTGRES_DB=tractor
POSTGRES_USER=tractor
POSTGRES_PASSWORD=secret
POSTGRES_HOST=localhost   # default: localhost
POSTGRES_PORT=5432        # default: 5432
```

### MySQL driver

MySQL requires `mysqlclient`, which is **not** in `pyproject.toml` because it needs system-level MySQL client libraries. Install it separately after activating the virtual environment:

```bash
# Debian/Ubuntu
sudo apt-get install python3-dev default-libmysqlclient-dev build-essential
uv pip install mysqlclient

# macOS (Homebrew)
brew install mysql-client
uv pip install mysqlclient
```

MySQL 8.0 or later is required. Tractor does not use any PostgreSQL-only field types, so migrations apply cleanly to MySQL without modification.

---

## Environment Variables

### Django settings

The project uses split settings under `backend/settings/`:

| Module                          | Used when                          |
|---------------------------------|------------------------------------|
| `backend.settings.development`  | Local development (default)        |
| `backend.settings.production`   | Production / Docker                |

`manage.py` defaults to `backend.settings.development`, so `DJANGO_SETTINGS_MODULE` does not need to be set locally. The development settings hardcode `DEBUG=True` and `ALLOWED_HOSTS=["*"]` so those do not need to be in your local `.env` either.

### Backend (.env)

| Variable                 | Purpose                                                                 |
|--------------------------|-------------------------------------------------------------------------|
| `SECRET_KEY`             | Django secret key for cryptographic signing                             |
| `JWT_SIGNING_KEY`        | Key for signing JWT tokens                                              |
| `DATABASE_URL`           | Full connection URL — takes priority over individual vars               |
| `POSTGRES_DB`            | PostgreSQL database name (used when `DATABASE_URL` is not set)          |
| `POSTGRES_USER`          | PostgreSQL username (used when `DATABASE_URL` is not set)               |
| `POSTGRES_PASSWORD`      | PostgreSQL password (used when `DATABASE_URL` is not set)               |
| `POSTGRES_HOST`          | PostgreSQL host (default: `localhost`)                                  |
| `POSTGRES_PORT`          | PostgreSQL port (default: `5432`)                                       |
| `OLLAMA_ENABLED`         | Enable the Gemma contextual AI stage (`True`/`False`, default: `False`) |
| `OLLAMA_HOST`            | Ollama API base URL (default: `http://localhost:11434`)                 |
| `OLLAMA_MODEL`           | Ollama model name to use (e.g. `gemma3:1b`)                             |
| `OLLAMA_CHUNK_SIZE`      | Characters per document chunk sent to Ollama (default: `4000`)          |
| `OLLAMA_CHUNK_OVERLAP`   | Overlap between chunks in characters (default: `200`)                   |

### Frontend (frontend/.env)

| Variable                         | Purpose                                                     |
|----------------------------------|-------------------------------------------------------------|
| `NEXT_PUBLIC_API_HOST`           | Backend API URL — for local dev use `http://localhost:8000` |
| `AUTH_SECRET`                    | NextAuth secret for session encryption                      |
| `AUTH_MICROSOFT_ENTRA_ID_ID`     | Microsoft Entra ID client ID (optional)                     |
| `AUTH_MICROSOFT_ENTRA_ID_SECRET` | Microsoft Entra ID client secret (optional)                 |
| `AUTH_MICROSOFT_ENTRA_ID_ISSUER` | Microsoft Entra ID issuer URL (optional)                    |

!!! note
    The Microsoft Entra ID variables are only required if SSO is being configured.
