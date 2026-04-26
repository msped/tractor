# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- XSS prevention: table HTML in DocumentViewer now sanitised with DOMPurify before rendering
- JWT session callback no longer exposes `refresh_token` to client-side React components — only `access_token`, `user`, and `error` are returned
- ExemptionTemplate create/update/delete now restricted to admin users (`IsAdminUser`)
- `.docx` upload validation now checks magic bytes with `zipfile.is_zipfile()` in addition to file extension
- `SECRET_KEY` and `JWT_SIGNING_KEY` now raise a `ValueError` at startup if not set, preventing Django from starting with `None` signing keys

### Changed
- Minimum training data threshold raised from 25 to 75 examples before a SpanCat training run will proceed
- `OLLAMA_CHUNK_SIZE` and `OLLAMA_CHUNK_OVERLAP` are now loaded from environment variables (previously only worked as Django settings overrides)

### Documentation
- CONTRIBUTING.md setup commands updated to use `uv` instead of `pip`/`venv`
- `docs/dev/setup.md` now includes the `python manage.py download_model` step required for first-time bare-metal setup
- `docs/dev/deployment.md` worker warning made more prominent; optional env var defaults clarified; Gemma model guidance updated
- `docs/dev/architecture.md` now documents the custom Presidio recognizer integration
- `docs/index.md` updated to correctly describe a four-model pipeline
- `docs/user-guide/training.md` added — covers scheduled training, manual training, uploading training documents, monitoring runs, and activating models
- `docs/user-guide/getting-started.md` typo fixes
- `frontend/.env.example` now includes `INTERNAL_API_HOST`
- `SECURITY.md` expanded with production security requirements
- `README.md` now includes a production deployment section
- `mkdocs.yml` updated to include the new training user guide

---

## [0.4.0] - 2026-04-19

### Added
- **Four-model NLP pipeline**: Gemma (via Ollama) added as a fourth extraction stage, performing contextual document analysis using a locally-hosted LLM. Results labelled `source=LLM` and shown with an **AI (Contextual)** badge in the review sidebar. Controlled by `OLLAMA_ENABLED` — fully optional
- **GPU acceleration**: GLiNER and SpanCat models now automatically use CUDA (NVIDIA) or MPS (Apple Silicon) via `_get_device()` in `training/loader.py`. NVIDIA GPU passthrough for the Ollama container supported via `docker-compose.gpu.yml`
- **Document chunking for Ollama**: Large documents automatically split into overlapping chunks before Gemma processing, with character offset correction before results are merged (`OLLAMA_CHUNK_SIZE` / `OLLAMA_CHUNK_OVERLAP`)
- **Custom Presidio recognizers**: Administrators can define organisation-specific entity patterns (regex with confidence scores, or deny lists) from Settings. Changes take effect immediately via signal-based singleton invalidation
- **LLM system prompt configuration**: The prompt sent to Gemma is configurable from Settings → Contextual AI Prompt and stored in a singleton model
- **Parallel NLP processing**: GLiNER, Presidio, and Gemma extractors now run concurrently to reduce document processing time
- Accessibility improvements: skip navigation link, `aria-current` on active sidebar item, autocomplete on login fields, `dvh` viewport units, reduced-motion CSS
- Dark/light mode toggle stored in context

### Changed
- Training section renamed to **Model Management** in the UI and API (`/api/model-management/`)
- Training documents are removed from the list when their associated training run is deleted

### Fixed
- Gemma extraction character offsets corrected for chunked documents (#102, #103)

---

## [0.3.0] - 2026-04-10

### Added
- **Three-model hybrid NER pipeline**: SpanCat (trained, highest priority) + GLiNER (zero-shot THIRD_PARTY) + Presidio (pattern-based THIRD_PARTY PII and OPERATIONAL refs). Replaces previous SpanCat + `en_core_web_lg` approach. Results deduplicated with priority SpanCat > GLiNER > Presidio
- GLiNER zero-shot model for THIRD_PARTY PII detection (names, orgs, locations, DOB, addresses) — works without training data
- Presidio with custom UK pattern recognisers: postcodes, NI numbers, NHS numbers, crime references, collar numbers
- `download_model` management command to fetch a GLiNER model from HuggingFace and register it as the active model
- Merged redaction display: adjacent same-type spans within a 2-character gap combined into a single sidebar item with a split action
- Bulk accept/reject for grouped redactions (same text + type) via `PATCH /api/cases/document/<id>/redactions/bulk/`
- Bulk redaction type change on merged items
- Isolated constituent management for merged redactions — split items can be individually accepted/rejected/type-changed
- Undo/redo support for redaction accept/reject actions; buttons moved into the redaction sidebar
- **Exemption templates**: predefined rejection reasons selectable when rejecting redactions, managed via Settings
- **Table extraction**: tables in DOCX and PDF documents extracted and rendered in the document viewer and exports
- **Export font selection**: configurable typeface for generated PDF exports
- **Header/footer/watermark**: customisable document header, footer, and watermark applied to exported PDFs
- **Production Docker Compose** (`docker-compose-prod.yml`): Gunicorn, nginx, django-q worker, optional managed database and Ollama services
- **Cloud media storage**: Amazon S3 and Azure Blob Storage backends alongside local filesystem, configured via `MEDIA_STORAGE`
- **MySQL support** as an alternative database backend
- **API key authentication**: external services authenticate with `Authorization: Api-Key <key>`. Keys stored as SHA-256 hashes, managed by admin users only
- `SessionWatcher` component for automatic redirect on session expiry
- Training status banner showing when a training run is in progress
- Original file auto-deletion after a configurable retention threshold
- `DS_INFORMATION` redactions excluded from disclosure PDF export
- Cancel document processing: in-progress documents can be cancelled, resetting to unprocessed status
- Training run and training document views in Django admin
- Resizable redaction sidebar with drag handle
- Font size control in document review and view
- Cumulative model training using all previous training data
- Automatic cleanup of model files from disk when a model entry is deleted
- JWT refresh token blacklisting: rotated tokens are blacklisted, preventing reuse
- MkDocs documentation site with user guide and developer guide
- Ruff linter integration

### Changed
- Migrated Python dependency management from `pip`/`requirements.txt` to `uv`/`pyproject.toml`
- Upgraded Python from 3.10 to 3.13
- Dockerfile and CI updated for `uv` and Python 3.13
- Settings page introduced to consolidate model management, training, and export configuration
- Navigation sidebar replacing the top header bar; user profile/logout button in sidebar
- Updated dependencies to address CVEs
- Removed unused `ocrmac` dependency

### Fixed
- Training documents reset to unprocessed when their associated training run is deleted
- Merged table cells no longer rendered as duplicated content
- Scroll behaviour when navigating merged redaction split/remove items
- Token refresh error handling and session expiry redirect
- Mismatched entity label types between SpanCat and NER models
- Unauthenticated users could access the training page
- Duplicate characters from inclusive/exclusive character offset mismatch
- Tables not displaying correctly alongside redactions
- Hydration warnings from client/server date mismatches
- Redaction context not saving due to function being overwritten

---

## [0.1.0] - 2025-01-07

### Added
- Document upload and text extraction (PDF, Word)
- Named Entity Recognition using spaCy for automatic redaction suggestions
- Accept/reject workflow for redactions
- Case management with status tracking
- Document export with original, edited, and redacted versions
- Custom SpanCat model training from accepted redactions
- Manual training document upload
- Scheduled training via django-q2
- Model versioning and activation
- Microsoft Entra ID SSO authentication
- JWT-based API authentication
- Audit logging for compliance
- WCAG 2.2 AA accessibility compliance (partial)

### Security
- Django CSRF protection enabled
- XSS prevention via template auto-escaping
- SQL injection prevention via ORM
- Environment-based secrets management
