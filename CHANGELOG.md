# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Added

- Initial open-source release preparation
- CONTRIBUTING.md with development guidelines
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- SECURITY.md with vulnerability reporting process
- GitHub issue and PR templates

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
