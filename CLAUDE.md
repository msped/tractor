# CLAUDE.md

Tractor is a document redaction app: users upload documents, an NER pipeline suggests redactions, users accept or reject them, then export. Accepted redactions train the SpanCat model.

Django 5.2 + DRF backend (`cases/`, `training/`, `authentication/`, settings in `backend/`); Next.js 15 + MUI v7 frontend in `frontend/`.

## Commands

Run backend and frontend commands through the Makefile (`make help` lists every target). The `be-*` targets wrap the venv and the macOS `DYLD_FALLBACK_LIBRARY_PATH` that WeasyPrint and psycopg2 need. For ad-hoc Python (`manage.py shell`, scripts), copy the `VENV` and `DYLD_LIBS` values from the top of `Makefile`.

## Where things are documented

- **Architecture** (NER pipeline and its priority order, deduplication, span merging, API endpoints, auth flow): `docs/dev/architecture.md`
- **Local setup and env vars**: `docs/dev/setup.md`, `.env.example`
- **Production deployment**: `docs/dev/deployment.md`
- **Writing or debugging tests**: `docs/dev/testing.md`

## Frontend conventions

- Each component lives in its own directory with an `index.js` re-export:
  ```
  components/ComponentName/
  ├── ComponentName.js
  ├── ComponentName.cy.js   # Cypress component test (component testing, not E2E)
  └── index.js              # export * from './ComponentName';
  ```
- Import through the directory with the `@/` alias (`@/*` → `src/*`): `import { ComponentName } from "@/components/ComponentName"`
