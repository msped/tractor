# Architecture

This document describes the technical architecture of Tractor.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 15 (React 19), Material-UI v7 |
| Backend | Django 5.2, Django REST Framework |
| Database | PostgreSQL 15 |  
| Task Queue | django-q2 |
| NLP | spaCy 3.8 with PyTorch |
| Authentication | NextAuth v5, JWT |

## Project Structure

```bash
tractor/
├── frontend/src/
│   ├── app/                    # Next.js App Router pages
│   │   └── (dashboard)/        # Grouped route with shared layout
│   ├── components/             # React components
│   ├── services/               # API client wrappers
│   └── api/apiClient.js        # Axios instance with auth interceptor
├── backend/                    # Django project settings
├── cases/                      # Django app: Case, Document, Redaction models
├── authentication/             # Django app: JWT + Microsoft Entra ID auth
└── training/                   # Django app: Model training, spaCy integration
```

## Data Flow

1. **Document Upload**: User uploads document → stored in media/originals
2. **Text Extraction**: docling extracts text and structure from document
3. **NER Processing**: spaCy NER identifies entities → creates Redaction suggestions
4. **User Review**: User accepts/rejects redactions in the UI
5. **Export**: WeasyPrint generates PDF exports with redactions applied
6. **Training**: Accepted redactions feed into model training pipeline

## API Endpoints

All endpoints are prefixed with `/api/`.

### Authentication (`/api/auth/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Login with username/password |
| POST | `/logout` | Logout current user |
| GET | `/user` | Get current user details |
| POST | `/token/verify` | Verify JWT token |
| POST | `/token/refresh` | Refresh JWT token |
| POST | `/microsoft` | Microsoft Entra ID callback |

### Cases (`/api/cases`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases` | List all cases |
| POST | `/cases` | Create a new case |
| GET | `/cases/<case_id>` | Get case details |
| PATCH | `/cases/<case_id>` | Update case |
| DELETE | `/cases/<case_id>` | Delete case |
| POST | `/cases/<case_id>/export` | Generate disclosure package |

### Documents (`/api/cases/...`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases/<case_id>/documents` | List documents in case |
| POST | `/cases/<case_id>/documents` | Upload document(s) |
| GET | `/cases/documents/<document_id>` | Get document details |
| PATCH | `/cases/documents/<document_id>` | Update document |
| DELETE | `/cases/documents/<document_id>` | Delete document |
| POST | `/cases/documents/<document_id>/resubmit` | Resubmit for processing |
| GET | `/cases/<case_id>/document/<document_id>/review` | Get document for review |

### Redactions (`/api/cases/document/...`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases/document/<document_id>/redaction` | List redactions |
| POST | `/cases/document/<document_id>/redaction` | Create redaction |
| GET | `/cases/document/redaction/<id>` | Get redaction details |
| PATCH | `/cases/document/redaction/<id>` | Update redaction (accept/reject) |
| DELETE | `/cases/document/redaction/<id>` | Delete redaction |
| POST | `/cases/document/redaction/<id>/context` | Add/update context |

### Models & Training (`/api/...`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/models` | List trained models |
| GET | `/models/<id>` | Get model details |
| POST | `/models/<id>/set-active` | Activate a model |
| POST | `/training/run-now` | Trigger manual training |
| GET | `/training-docs` | List training documents |
| POST | `/training-docs` | Upload training document |
| GET | `/schedules` | List training schedules |
| POST | `/schedules` | Create training schedule |
| GET | `/training-runs` | List training run history |

## Authentication Flow

!!! note "TODO"
    Document JWT flow and Microsoft Entra ID integration

## Model Training

!!! note "TODO"
    Document the training pipeline and model versioning
