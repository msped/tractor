# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Loading state to confirmation dialog and document deletion process (#72)
- Isolated constituent management for merged redactions — split items can be individually accepted/rejected/type-changed without affecting the group (#71)
- Validation to reject legacy `.doc` files on upload with a clear error message (#72)
- API key management: creation, revocation, and display in settings (admin/superuser only) (#68)
- `IsAdminOrSuperuser` permission class for API key endpoints (#68)
- Manual redaction: users can highlight text in the document viewer to create new redactions
- Remove redaction: users can remove individual redaction highlights directly from the document viewer
- Undo/Redo functionality on document review
- Undo/Redo buttons moved into the redaction sidebar
- `SessionWatcher` component for session management with automatic redirect on expiry
- Training status banner showing when a training run is in progress
- Original file auto-deletion after a configurable retention threshold, with settings UI
- `DS_INFORMATION` redactions excluded from disclosure PDF export
- Docker multi-stage build setup for frontend and backend, including PostgreSQL configuration
- Production Django settings split into base, development, and production modules
- Three-model NLP pipeline: SpanCat (trained, highest priority) + GLiNER (zero-shot THIRD_PARTY) + Presidio (structured THIRD_PARTY PII and OPERATIONAL pattern refs); replaces previous SpanCat + `en_core_web_lg` approach
- GLiNER added for zero-shot third-party PII detection (names, orgs, locations, DOB, addresses) — works without training data
- Presidio added with custom UK pattern recognisers for postcodes, NI numbers, crime references, and collar numbers
- `download_model` management command to fetch a GLiNER model from HuggingFace and register it as the active model
- Merged redaction display: adjacent same-type spans within a 2-character gap are combined into a single sidebar item, with a split action to expand them individually
- Bulk accept/reject for grouped redactions (same text + type) via `PATCH /api/cases/document/<id>/redactions/bulk/`
- Bulk redaction type change on merged items
- Cancel document processing: users can cancel a document currently being processed, resetting it to a new `UNPROCESSED` status (#39)
- Resizable redaction sidebar with drag handle (#37)
- Font size changer in document review/view (#35)
- Table display with redactions in document viewer (#35)
- Resubmit documents in `READY_FOR_REVIEW` status, not just `ERROR` (#33)
- Cumulative model training using all previous training documents (#32)
- Automatic cleanup of model files from disk when a model entry is deleted (#32)
- Training run and training document views in Django admin (#31)
- Filtered training documents to only show unprocessed documents (#31)
- Navigation sidebar replacing the top header bar (#29)
- User profile button with logout in sidebar (#29)
- Application logo and favicon (#29)
- MkDocs documentation site with user guide and developer guide (#30)
- Ruff linter integration and CI linting workflow (#30)
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, and GitHub issue/PR templates (#29)

### Changed

- Migrated Python dependency management from `pip`/`requirements.txt` to `uv`/`pyproject.toml`
- Upgraded Python from 3.10 to 3.13
- CI pipeline updated to use `uv` for dependency installation and Python 3.13
- Dockerfile updated to use `python:3.13-slim` base image and `uv` for installs
- Removed unused `ocrmac` dependency (macOS-only, not used in codebase)
- Updated `smart-open` from 7.3.0 (yanked) to 7.5.1
- NLP stack updated: `en_core_web_lg` replaced by GLiNER + Presidio; SpanCat retained as the primary trained model
- GLiNER model paths store HuggingFace model IDs; HuggingFace handles local caching. SpanCat models continue to be stored in `nlp_models/`
- GLiNER model loading now falls back to a local path if available before fetching from HuggingFace
- CI pipeline now checks linting before running tests (#33)
- Removed lint.yml as linting now occurs before testing
- Refactored API calls to use service functions with access tokens instead of direct apiClient usage (#23)
- Updated theme colours to align with default MUI palette (#29)
- Updated dependencies to fix CVEs

### Fixed

- Training documents reset to unprocessed when their associated TrainingRun is deleted (#69)
- Merged cells in tables not displaying correctly as duplicated content (#72)
- Scroll behaviour when navigating merged redaction split/remove items (#71)
- Token refresh error handling and session expiry redirect
- Mismatched entity label types between SpanCat and NER models (#38)
- Unauthenticated users could access the training page (#34)
- Duplicate characters rendered due to inclusive/exclusive character offset mismatch (#31)
- Tables not displaying correctly alongside redactions (#35)
- Hydration warnings on dates/times from client-server mismatches (#32)
- Redaction context not saving due to function being overwritten (#22)

## [0.1.0] - 2025-01-07

Added

- Document upload and text extraction (PDF, Word, PowerPoint, Excel)
- Named Entity Recognition using spaCy for automatic redaction suggestions
- Accept/reject workflow for redactions
- Case management with status tracking
- Document export with original, edited, and redacted versions
- Custom model training from accepted redactions
- Manual training document upload
- Scheduled training via django-q2
- Model versioning and activation
- Microsoft Entra ID authentication support
- JWT-based API authentication
- Audit logging for compliance
- WCAG 2.2 AA accessibility compliance (partial)

### Security

- Django CSRF protection enabled
- XSS prevention via template auto-escaping
- SQL injection prevention via ORM
- Environment-based secrets management
