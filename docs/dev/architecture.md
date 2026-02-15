# Architecture

This document describes the technical architecture of Tractor.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 15 (React 19), Material-UI v7 |
| Backend | Django 5.2, Django REST Framework |
| Database | PostgreSQL 15 |  
| Task Queue | django-q2 |
| NLP | spaCy 3.8 with PyTorch, `en_core_web_lg` + custom SpanCat |
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
2. **Text Extraction**: python-docx (DOCX) or spaCyLayout (PDF) extracts text and structure
3. **Entity Recognition (Hybrid)**:
    - Custom **SpanCat** model identifies OPERATIONAL and THIRD_PARTY spans via `doc.spans["sc"]`
    - **`en_core_web_lg`** built-in NER identifies standard entities (PERSON, ORG, GPE, DATE, etc.) mapped to THIRD_PARTY
    - Results are deduplicated — SpanCat takes priority where spans overlap
4. **Data Subject Filtering**: Entities matching the case's data subject name or DOB are excluded from suggestions
5. **User Review**: User accepts/rejects redactions in the UI
6. **Export**: WeasyPrint generates PDF exports with redactions applied
7. **Training**: Accepted redactions feed into SpanCat model training pipeline

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

## Entity Recognition

Tractor uses a hybrid two-model approach for entity recognition:

### `en_core_web_lg` (Built-in NER)

The pre-trained spaCy model provides out-of-the-box recognition for standard entity types. The following NER labels are mapped to **THIRD_PARTY** redactions:

| NER Label | Example |
|-----------|---------|
| PERSON | "John Smith", "Dr. Jones" |
| ORG | "NHS", "Acme Ltd" |
| GPE | "London", "United Kingdom" |
| DATE | "1 January 1990", "last Tuesday" |
| FAC | "Heathrow Airport" |
| LOC | "the Thames" |
| NORP | "British", "Muslim" |

This model requires no training and works immediately.

### Custom SpanCat Model

A SpanCat (Span Categorisation) model trained on domain-specific data. Results are stored in `doc.spans["sc"]` with labels:

- **OPERATIONAL** → Operational Data (reference numbers, case IDs, internal codes)
- **THIRD_PARTY** → Third-Party PII (domain-specific patterns)

Training is performed via the training pipeline using accepted redactions from completed documents. Models are versioned and stored in `nlp_models/`.

### Deduplication

When both models identify overlapping spans, the SpanCat result takes priority since it was trained on domain-specific data.

### Data Subject Filtering

Entities matching the case's `data_subject_name` or `data_subject_dob` are automatically excluded from redaction suggestions. This includes:

- Full name matches (case-insensitive)
- Individual name parts (e.g., "John" or "Doe" from "John Doe")
- DOB in common date formats (DD/MM/YYYY, YYYY-MM-DD, D Month YYYY, etc.)

The data subject's own information should remain visible in the document. Users can still manually mark text as DS_INFORMATION, which propagates across all documents in the case via `find_and_flag_matching_text_in_case()`.
