# Production Deployment

This guide covers deploying Tractor using Docker Compose.

---

## Prerequisites

- Docker and Docker Compose installed on the host
- A domain name (for production)
- PostgreSQL credentials

---

## Environment Variables

Tractor uses two env files:

| File            | Used by             | Contains                                 |
|-----------------|---------------------|------------------------------------------|
| `.env`          | backend, worker, db | Django secrets, database, storage config |
| `frontend/.env` | frontend            | NextAuth, Microsoft SSO, API host        |

Copy the examples and fill in the values:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

### Backend (`.env`)

| Variable                 | Description                                   | Example                    |
|--------------------------|-----------------------------------------------|----------------------------|
| `SECRET_KEY`             | Django secret key                             | Long random string         |
| `JWT_SIGNING_KEY`        | JWT token signing key                         | Long random string         |
| `DJANGO_SETTINGS_MODULE` | Settings module path                          | `backend.settings.production` |
| `DEBUG`                  | Enable debug mode (optional — defaults to `False` in production) | `False` |
| `ALLOWED_HOSTS`          | Comma-separated allowed hostnames — must include `backend` when running in Docker, as the frontend container calls the backend directly | `localhost,backend,yourdomain.com` |
| `CORS_ALLOWED_ORIGINS`   | Comma-separated list of allowed CORS origins. In production, set this to the frontend URL only. In development, CORS is open (`CORS_ORIGIN_ALLOW_ALL = True`). | `https://yourdomain.com` |
| `DATABASE_URL`           | Database URL for connection (optional)        |                            |
| `POSTGRES_DB`            | Database name (optional)                      | `tractor`                  |
| `POSTGRES_USER`          | Database user (optional)                      | `tractor`                  |
| `POSTGRES_PASSWORD`      | Database password (optional)                  |                            |
| `POSTGRES_HOST`          | Database host (use `db` in Docker) (optional) | `db`                       |
| `POSTGRES_PORT`          | Database port (optional)                      | `5432`                     |
| `MEDIA_STORAGE`          | Storage backend (`local`, `s3`, `azure`)      | `local`                    |
| `OLLAMA_ENABLED`         | Enable Gemma contextual AI stage (`True`/`False`) | `True`               |
| `OLLAMA_HOST`            | Ollama API URL — use `http://ollama:11434` in Docker | `http://ollama:11434` |
| `OLLAMA_MODEL`           | Ollama model name                             | `gemma3:1b`                |
| `OLLAMA_CHUNK_SIZE`      | Characters per chunk sent to Ollama (optional) | `4000`                   |
| `OLLAMA_CHUNK_OVERLAP`   | Overlap between chunks in characters (optional) | `200`                   |

### Frontend (`frontend/.env`)

| Variable                         | Description                                                   | Example                  |
|----------------------------------|---------------------------------------------------------------|--------------------------|
| `NEXT_PUBLIC_API_HOST`           | Public-facing backend URL (used by the browser to reach the API) | `https://yourdomain.com` |
| `AUTH_SECRET`                    | NextAuth secret                                               | Long random string       |
| `AUTH_URL`                       | Full public URL of the frontend                               | `https://yourdomain.com` |
| `AUTH_TRUST_HOST`                | Trust the forwarded host header (required behind a proxy)     | `true`                   |
| `AUTH_MICROSOFT_ENTRA_ID_ID`     | Microsoft Entra application (client) ID (optional — see below)|                          |
| `AUTH_MICROSOFT_ENTRA_ID_SECRET` | Microsoft Entra client secret (optional — see below)          |                          |
| `AUTH_MICROSOFT_ENTRA_ID_ISSUER` | Microsoft Entra issuer URL (optional — see below)             |                          |

Username/password login is always available. Microsoft SSO is only enabled when **all three** `AUTH_MICROSOFT_ENTRA_ID_*` variables are set — omit them entirely if you don't need SSO.

---

## Docker Compose (Production)

The production stack (`docker-compose-prod.yml`) runs the following services:

| Service    | Description                                                                         |
|------------|-------------------------------------------------------------------------------------|
| `backend`  | Django app served by Gunicorn on port 8000                                          |
| `worker`   | Django-Q task queue for async jobs (export, training)                               |
| `frontend` | Next.js app served on port 3000                                                     |
| `nginx`    | Reverse proxy on port 80, serves static files directly; proxies `/media/` to Django |
| `ollama`   | Locally-hosted LLM inference server (contextual AI) — see below                    |
| `db`       | PostgreSQL 15 database (optional — see below)                                       |

### Ollama (Contextual AI)

The `ollama` service runs the locally-hosted LLM used for contextual document analysis. It is included in the production Compose file but is **optional** — set `OLLAMA_ENABLED=False` in `.env` to disable the Gemma stage entirely, and the other three NLP models will continue to operate normally.

On first startup, pull the model inside the container:

```bash
docker compose -f docker-compose-prod.yml exec ollama ollama pull gemma3:1b
```

This application is not tide to Gemma, you can run any model through Ollama depending on your system.

The model is persisted in the `ollama_volume` Docker volume, so it only needs to be downloaded once.

The `backend` and `worker` containers reach Ollama at `http://ollama:11434` (the Docker service hostname). Set `OLLAMA_HOST=http://ollama:11434` in `.env`.

### Task Queue (worker)

The `worker` service runs `python manage.py qcluster`, which is required for all asynchronous tasks — document export (PDF generation) and model training. Without it, these operations will queue but never execute. It shares the same Docker image as the backend and reads the same `.env` file.

### Database

The `db` service is optional and uses the Docker Compose `db` profile. Use it if you don't have an external PostgreSQL instance.

**With the bundled database:**

```bash
docker compose -f docker-compose-prod.yml --profile db up --build -d
```

**With an external database** (e.g. RDS, Azure Database, managed PostgreSQL):

Set either `DATABASE_URL` or the individual `POSTGRES_*` variables in `.env` pointing at your external host, then run without the `db` profile:

```bash
docker compose -f docker-compose-prod.yml up --build -d
```

### Verify

```bash
# Check all services are running
docker compose -f docker-compose-prod.yml ps

# Backend API
curl http://localhost/api/

# Frontend
curl http://localhost/

# Worker logs (confirm qcluster is running)
docker compose -f docker-compose-prod.yml logs worker
```

---

## Media File Storage

By default, uploaded documents are stored on the local filesystem inside a Docker volume (`media_volume`). For production deployments with multiple replicas or external backups, cloud storage is recommended.

Set `MEDIA_STORAGE` in `.env` to switch backends. **No changes to Docker files are needed** — nginx always proxies `/media/` requests to Django, which then either serves the file from the local volume or issues a redirect to the cloud storage URL depending on the configured backend.

> **Note:** nginx does not mount `media_volume` and does not serve media files directly. All `/media/` requests go through Django, which is what makes local and cloud storage work identically from nginx's perspective.

### Local (default)

No additional configuration required. Files are stored in the `media_volume` Docker volume, accessible by both `backend` and `worker`.

```bash
MEDIA_STORAGE=local
```

### Amazon S3

`django-storages[s3]` must be installed in the backend image. Add it to `pyproject.toml` and run `uv lock` so it is picked up when the image is built:

```bash
uv add "django-storages[s3]"
```

Then set env vars in `.env`:

```bash
MEDIA_STORAGE=s3
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

Rebuild so the package is installed into the image:

```bash
docker compose -f docker-compose-prod.yml up --build -d
```

The `media_volume` remains mounted but is unused when S3 is active.

### Azure Blob Storage

`django-storages[azure]` must be installed in the backend image. Add it to `pyproject.toml` and run `uv lock` so it is picked up when the image is built:

```bash
uv add "django-storages[azure]"
```

Then set env vars in `.env`:

```bash
MEDIA_STORAGE=azure
AZURE_ACCOUNT_NAME=your-storage-account
AZURE_ACCOUNT_KEY=your-account-key
AZURE_CONTAINER=your-container-name
```

Rebuild so the package is installed into the image:

```bash
docker compose -f docker-compose-prod.yml up --build -d
```

The `media_volume` remains mounted but is unused when Azure is active.

---

## Static Files

Static files are collected into the `static_volume` Docker volume during container startup (via `collectstatic`) and served directly by nginx at `/static/`. No additional configuration is required.

---

## NLP Models

### GLiNER

The GLiNER model (`urchade/gliner_medium-v2.1`) is downloaded from HuggingFace on first startup and saved to `nlp_models/` inside the container. This is handled automatically by the entrypoint — no manual steps are required.

The `nlp_models_volume` Docker volume persists the model across container rebuilds so it is only downloaded once. The download is skipped on subsequent starts if the model directory already exists.

The backend container requires internet access on first startup to reach HuggingFace. Subsequent starts are fully offline.

### SpanCat

The SpanCat model is trained from user-accepted redactions via the training pipeline. It is also stored in `nlp_models_volume` and is optional — document processing works without it, falling back to GLiNER, Presidio, and Gemma.

### Gemma (Ollama)

The Gemma model is pulled and stored inside the `ollama_volume` volume (see the [Ollama section](#ollama-contextual-ai) above). No backend container configuration is needed beyond the env vars.

---

## Original File Auto-Deletion

Tractor can automatically clear original uploaded files after a case reaches a terminal state (Completed, Closed, Withdrawn, Under Review, or Error) and has not been updated for a configurable number of days. This reduces storage usage over time while leaving redaction review and exports fully functional — all extracted text is stored in the database.

This feature is **disabled by default**. To enable it, set the following in `backend/settings/base.py` (or override in your environment-specific settings file):

```python
DELETE_ORIGINAL_FILES = True
DELETE_ORIGINAL_FILES_AFTER_DAYS = 30  # adjust as needed
```

A scheduled task (`delete_original_files_daily`) runs once per day via the `worker` service. It finds all documents where:

- the parent case status is terminal, **and**
- the case's `updated_at` timestamp is older than the configured threshold.

`django-cleanup` handles physical file deletion from storage (local or cloud) when the field is cleared.

> **Note:** Once an original file is deleted it cannot be recovered. Exported redacted PDFs and disclosure packages are unaffected.

---

## WeasyPrint (PDF Export)

WeasyPrint dependencies (Cairo, Pango, GDK-Pixbuf) are installed in the backend Docker image. No additional host configuration is needed.
