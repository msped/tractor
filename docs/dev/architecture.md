# Architecture

This document describes the technical architecture of Tractor.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 15 (React 19), Material-UI v7 |
| Backend | Django 5.2, Django REST Framework |
| Database | PostgreSQL 15 |  
| Task Queue | django-q2 |
| NLP | SpanCat (spaCy 3.8), GLiNER (HuggingFace), Microsoft Presidio |
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
2. **Text Extraction**: python-docx (DOCX) or pdfplumber (PDF) extracts text and structure
3. **Entity Recognition (Three-model pipeline)**:
    - **SpanCat** identifies OPERATIONAL and THIRD_PARTY spans from the trained custom model (optional — skipped gracefully if no model trained yet)
    - **GLiNER** identifies **THIRD_PARTY** spans (names, orgs, locations, DOB, addresses) using a zero-shot model from HuggingFace
    - **Presidio** identifies structured **THIRD_PARTY** PII (phone, email, NHS, postcode, NI) and structured **OPERATIONAL** refs (crime references, collar numbers) via pattern recognisers
    - Results are deduplicated with priority: **SpanCat > GLiNER > Presidio**
4. **Data Subject Filtering**: Entities matching the case's data subject name or DOB are excluded from suggestions
5. **User Review**: User accepts/rejects redactions in the UI. Adjacent same-type spans are automatically merged into compound display items for easier review. Merged items can be split and reviewed individually.
6. **Export**: WeasyPrint generates PDF exports with redactions applied
7. **Training**: Accepted redactions from completed documents feed into the SpanCat training pipeline

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
| PATCH | `/cases/document/<document_id>/redactions/bulk` | Bulk accept/reject/retype multiple redactions |

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

Tractor uses a three-model hybrid pipeline. All three models run on every document and their results are merged and deduplicated.

### SpanCat (Trained Model)

A custom SpanCat (Span Categorisation) model trained on your organisation's accepted redactions. It can identify both:

- **OPERATIONAL** — reference numbers, case IDs, and other domain-specific operational patterns
- **THIRD_PARTY** — domain-specific PII patterns learned from training data

SpanCat is loaded as a singleton (`SpanCatModelManager`) and takes the **highest priority** in deduplication. If no SpanCat model has been trained yet, this step is skipped and the system falls back to GLiNER + Presidio. Trained models are stored in `nlp_models/`.

### GLiNER (Third-Party PII — Zero-Shot)

[GLiNER](https://github.com/urchade/GLiNER) is a zero-shot generalist NER model downloaded from HuggingFace and registered in the database via the `download_model` management command. It identifies **THIRD_PARTY** entities:

- person names, organisations, locations, dates of birth, addresses

GLiNER is loaded as a singleton (`GLiNERModelManager`). The model ID stored in the database is the HuggingFace model identifier (e.g. `urchade/gliner_medium-v2.1`); HuggingFace handles local caching automatically. Long texts are chunked to stay within the model's ~1500 character token limit per chunk.

### Presidio (Pattern-Based)

[Microsoft Presidio](https://microsoft.github.io/presidio/) is a rule-based detection framework using custom pattern recognisers. It runs two separate analyzers:

**THIRD_PARTY analyzer:**

| Recogniser | Entities detected |
|------------|------------------|
| Built-in (spaCy `en_core_web_sm`) | PHONE_NUMBER, EMAIL_ADDRESS, UK_NHS |
| Custom pattern | UK postcodes |
| Custom pattern | National Insurance numbers |

**OPERATIONAL analyzer:**

| Recogniser | Entities detected |
|------------|------------------|
| Custom pattern | Crime reference numbers (e.g. `42/12345/24`) |
| Custom pattern | Police collar numbers (e.g. `PC 1234`) |

Both analyzers are instantiated lazily and cached as module-level singletons.

### Deduplication

After all three models run, overlapping spans are deduplicated with this priority order:

1. SpanCat results are kept in full
2. GLiNER results are added where they don't overlap SpanCat spans
3. Presidio results are added where they don't overlap either of the above

### Merged Display Items

Adjacent or near-adjacent spans of the **same type** (within a 2-character gap by default) are automatically merged into a single compound display item in the review sidebar. This reduces noise when, for example, a first name and surname are detected as separate spans.

Merged items show all underlying span IDs and can be split back into individual items by the user from the sidebar.

### Data Subject Filtering

Entities matching the case's `data_subject_name` or `data_subject_dob` are automatically excluded from redaction suggestions. This includes:

- Full name matches (case-insensitive)
- Individual name parts (e.g., "John" or "Doe" from "John Doe")
- DOB in common date formats (DD/MM/YYYY, YYYY-MM-DD, D Month YYYY, etc.)

The data subject's own information should remain visible in the document. Users can still manually mark text as DS_INFORMATION, which propagates across all documents in the case via `find_and_flag_matching_text_in_case()`.
