# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tractor is a document redaction application with ML-powered Named Entity Recognition. Users upload documents, the system identifies sensitive information using spaCy NER, and users can accept/reject redactions before exporting redacted versions. Supports model training from user-accepted redactions.

## Commands

### Backend (Django)

```bash
python manage.py runserver          # Start dev server
python manage.py qcluster           # Start django-q task queue (required for async tasks)
python manage.py test               # Run all tests
python manage.py test cases.tests.test_views  # Run specific test module
coverage run manage.py test && coverage report --fail-under=90  # Tests with coverage (90% threshold)
python manage.py makemigrations     # Create migrations
python manage.py migrate            # Apply migrations
```

### Frontend (Next.js)

```bash
cd frontend
npm run dev                         # Dev server with Turbopack
npm run build                       # Production build
npm run lint                        # ESLint
npm run cy:open                     # Cypress interactive mode
npm run cy:run                      # Cypress headless
npm run cy:test                     # Cypress + coverage report (80% threshold)
```

### WeasyPrint (macOS)

If PDF export fails with library errors:

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
```

## Architecture

### Tech Stack

- **Frontend**: Next.js 15 (React 19), Material-UI v7, NextAuth v5 for auth
- **Backend**: Django 5.2, Django REST Framework, django-q2 for async tasks
- **Database**: PostgreSQL 15
- **NLP**: spaCy 3.8 with PyTorch backend, custom trained models stored in `nlp_models/`

### Project Structure

```bash
tractor/
├── frontend/src/
│   ├── app/                    # Next.js App Router pages
│   │   └── (dashboard)/        # Grouped route with shared layout
│   ├── components/             # React components (tests as *.cy.js alongside)
│   ├── services/               # API client wrappers (caseService, documentService, etc.)
│   └── api/apiClient.js        # Axios instance with auth interceptor
├── backend/                    # Django project settings
├── cases/                      # Django app: Case, Document, Redaction models
├── authentication/             # Django app: JWT + Microsoft Entra ID auth
└── training/                   # Django app: Model training, TrainingRun, spaCy integration
```

### API Communication

- Frontend services in `frontend/src/services/` call backend via `apiClient.js`
- API base: `${NEXT_PUBLIC_API_HOST}/api`
- Auth: JWT tokens passed in Authorization header, managed by NextAuth
- 401 responses auto-redirect to login

### Key Endpoints

- `/api/auth/` - Authentication (login, logout, token refresh, Microsoft callback)
- `/api/cases/` - Case CRUD, export triggering
- `/api/cases/{id}/documents/` - Document upload and management
- `/api/training/` - Model management, training runs

### Data Flow

1. Document uploaded → docling extracts text → spaCy NER identifies entities
2. Redaction suggestions shown to user → user accepts/rejects
3. Completed documents feed into training pipeline
4. Async tasks (export, training) handled by django-q2

### Model Status

- Documents have status: `PROCESSING`, `IN_REVIEW`, `COMPLETED`, `FAILED`
- Cases have status: `OPEN`, `IN_PROGRESS`, `COMPLETED`, `CLOSED`, `WITHDRAWN`, `UNDER_REVIEW`, `ERROR`
- Redactions have status: `ACCEPTED`, `REJECTED`, `PENDING`

## Testing Conventions

### Backend

- Tests in `{app}/tests/` with `test_models.py`, `test_views.py`, `test_services.py`, `test_serializers.py`
- Use freezegun for time mocking
- Coverage threshold: 90%

### Frontend

- Components live in their own directory with an `index.js` re-export:
  ```
  components/
  └── ComponentName/
      ├── ComponentName.js      # Component implementation
      ├── ComponentName.cy.js   # Cypress component test
      └── index.js              # Re-exports: export * from './ComponentName';
  ```
- Import components via the directory: `import { ComponentName } from "@/components/ComponentName"`
- Uses Cypress component testing (not E2E)
- Coverage threshold: 80%

## Path Aliases

Frontend uses `@/*` mapping to `./src/*` (configured in jsconfig.json)

## Environment Variables

See `.env.example`. Key variables:

- `SECRET_KEY`, `JWT_SIGNING_KEY` - Django secrets
- `POSTGRES_*` - Database connection
- `NEXT_PUBLIC_API_HOST` - Backend URL for frontend
- `AUTH_MICROSOFT_ENTRA_ID_*` - Microsoft SSO config
