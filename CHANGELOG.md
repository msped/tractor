# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Auto-accept review mode**: admin toggle (Settings → Review Workflow) that automatically accepts all NER redaction suggestions when a document is processed. Reviewers must scroll through the full document before marking it complete, and auto-accepted redactions are excluded from SpanCat training
- **Data subject information propagation**: accepting a DS_INFO redaction automatically finds and accepts matching text (including plural/singular variations) across all other reviewable documents in the case; newly uploaded documents inherit the case's accepted DS_INFO terms on processing
- **Retention management**: Settings page for global automatic case deletion, lists of cases past or approaching their retention review date, and bulk case deletion
- **Disclosure style option** on document export settings: redactions in disclosure PDFs rendered as black bars or removed entirely (adjacent removals merge into a single `[...]` marker; fully redacted rows, cells, and lines are suppressed)
- Case list search and filtering
- Drag-and-drop document upload
- `Document.start_processing()` method to transition a document into processing state and dispatch the async task
- Paste Text tab (alpha) on the Add Document dialog — allows creating a document by pasting plain text directly, without uploading a file. The pasted content is stored as a `.txt` file and processed through the same NER pipeline as uploaded documents. Table formatting is not preserved.
- Makefile with backend and frontend targets for run, test, lint, format, and migrations

### Security

- Media files are now served through an authenticated backend view instead of directly by the web server; the view returns 404 for directory paths and files missing from storage
- Case API endpoints hardened: bulk redaction update payloads are validated (400 on missing/invalid fields), export requests return 409 while an export is already processing, and `case_reference` length limits are enforced in forms
- Blank entries filtered from `ALLOWED_HOSTS`

### Fixed

- Custom recognizer changes now take effect on the next processed document in all processes — including qcluster workers — without a restart. Presidio analyzers are served from an immutable per-document snapshot whose freshness is a content fingerprint of the recognizer tables, replacing the signal-based cache invalidation that only worked in the web process and missed bulk/queryset edits. Engine builds are also now thread-safe and load half as many spaCy instances.
- Case-decision propagation no longer leaks machine-accepted redactions into SpanCat training data — propagated decisions were previously indistinguishable from human accepts and contaminated every training run since auto-accept shipped
- A human re-confirming an auto-accepted redaction is now recorded as a human decision and included in SpanCat training (previously it stayed excluded)
- Admin-only UI elements (Retention Review nav item, API Keys, LLM Prompt Settings, and Retention Settings cards) not appearing until a hard page refresh after logging in. Root causes: (1) the `customSession` plugin renamed `isAdmin` → `is_admin`, causing a mismatch with the raw field name stored in better-auth's JWE cookie cache; (2) better-auth's `atomListeners` does not include the custom `/sign-in/username` endpoint, so `useSession()` was never notified to re-fetch after login. Fixed by keeping the field as `isAdmin` throughout and explicitly calling `authClient.$store.notify("$sessionSignal")` after a successful login.
- SpanCat training now extracts highlighted text from table cells in training documents, not just body paragraphs. Previously, any annotations in occurrence report tables (e.g. Link/No columns, involved-officer blocks) were silently ignored.
- Data subject name filter now handles inverted name formats (e.g. "COOPER, ALEX" in a document matching the stored name "Alex Cooper") using word-set subset comparison.
- Cancel document processing now actually removes the queued task — `OrmQ.key` holds the cluster name, not the task id, so the old lookup never matched
- Retention cleanup now deletes original files from storage rather than only clearing the database reference
- Export package generation no longer silently overwrites documents with identical sanitised filenames
- File downloads use absolute storage URLs natively (cloud storage backends) and defer blob URL revocation until after the download starts
- Per-thread database connections closed after parallel pipeline extractor stages, preventing connection exhaustion in the worker
- better-auth endpoints routed to the frontend in the nginx production config
- Training document upload returns 400 when no file is provided
- Explicitly provided case retention dates are preserved instead of being overwritten by the DOB-derived default; model creation detected via `_state.adding` for UUID-pk models
- `Document.save()` derives `file_type` in the same format as the serializer (leading dot) and no longer overwrites caller-set fields
- `OLLAMA_ENABLED` environment variable boolean conversion
- Training Documents now use media settings overide to stop test data being uploaded to the directroy.

### Changed

- **Redaction decision provenance**: the `auto_accepted` boolean is replaced by a `decided_by` column recording who made each decision (human reviewer, auto-accept mode, case-decision propagation, or DS_INFO propagation). All accept/reject operations must state their provenance — enforced at the API, ORM, and database-constraint level — and SpanCat training selection is now owned by a single canonical `trainable()` queryset. The `auto_accepted` API field is preserved read-only, so the frontend contract is unchanged
- Custom Presidio recognizers now run as the highest-priority extraction stage, so admin-configured patterns can no longer be overridden by learned SpanCat predictions
- DS_INFO propagation consolidated into a plan/apply module (`cases/ds_info_propagation.py`) with a read-only planning phase and a single writer of propagation acceptance state
- `training/services.py` split into `training/extraction.py` (document structure extraction and `DocumentStructure` dataclass) and `training/pipeline.py` (`ExtractionPipeline` and `build_default_pipeline`)
- `GLiNERModelManager` and `SpanCatModelManager` now inherit from `_ModelManagerBase`, giving each subclass independent singleton state and eliminating shared class-level `_instance`/`_lock`
- Task routing for the `cases` app centralised in `cases/tasks.py`; unhandled exceptions during document processing now log the traceback and mark the document `ERROR` rather than propagating silently
- Frontend services now use a shared `throwApiError` utility for consistent API error handling
- `RedactionComponent` state logic extracted into `useRedactionState` hook; mark-all-in-case logic extracted into `useMarkAllInCase` hook
- SpanCat superset extension rule: when SpanCat predicts a span that strictly contains a same-label custom Presidio span (e.g. it captures "OIC / HUGHES, R. #0723222" while Presidio only matched "HUGHES, R. #0723222"), SpanCat's wider span replaces the narrower one instead of being dropped. This is intentionally limited to the SpanCat stage.
- SpanCat training task timeout increased from the cluster-wide 1800 s to 7200 s; ngram candidate sizes capped at 1–20 (was 1–50) to reduce memory pressure on large document sets; case document input capped at 500 most-recent documents per training run

---

## [0.5.1] - 2026-05-09

### Changed

- Bumped Python dependencies: Django 5.2.12 → 5.2.14, lxml 5.4.0 → 6.1.0, Pillow 12.1.1 → 12.2.0, pypdf 6.9.2 → 6.10.2, python-dotenv 1.1.0 → 1.2.2
- Bumped JS dependencies: fast-uri 3.1.0 → 3.1.2, postcss 8.4.31 → 8.5.14 (also added as a direct override to resolve transitive version conflict)

---

## [0.5.0] - 2026-05-09

### Security

- XSS prevention: table HTML in DocumentViewer now sanitised with DOMPurify before rendering
- JWT session callback no longer exposes `refresh_token` to client-side React components — only `access_token`, `user`, and `error` are returned
- ExemptionTemplate create/update/delete now restricted to admin users (`IsAdminUser`)
- `.docx` upload validation now checks magic bytes with `zipfile.is_zipfile()` in addition to file extension
- `SECRET_KEY` and `JWT_SIGNING_KEY` now raise a `ValueError` at startup if not set, preventing Django from starting with `None` signing keys

### Changed

- Licence changed from AGPL v3 to Mozilla Public License 2.0
- Authentication migrated from NextAuth to better-auth for improved session management
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
