# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Cancel document processing: users can cancel a document currently being processed, resetting it to a new `UNPROCESSED` status (#39)
- Hybrid NER pipeline: SpanCat model for operational data combined with `en_core_web_lg` for third-party PII detection (#38)
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

- CI pipeline now checks linting before running tests (#33)
- Removed lint.yml as linting now occurs before testing
- Refactored API calls to use service functions with access tokens instead of direct apiClient usage (#23)
- Updated theme colours to align with default MUI palette (#29)

### Fixed

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
