# Tractor

Locally ran application to redact documents with a trained model.

## Key Features

* Allow the uploading of documents for Natural Language Processing (NLP).
* Provide redaction based on operational, Third Party Personally Identifiable Information (PII) from trained model.
* Export case with all documents redacted in folder structure showcasing original, editied, and redacted versions.

## Compliance & Accessibility

This service has been built to align with the standards set by the UK's Government Digital Service (GDS).

* **[➡️ View our full Accessibility Statement](./ACCESSIBILITY.md)**
* **[➡️ View our issue Remediation Log](./REMEDIATION-LOG.md)**

## Technical Overview

This section provides a technical overview for developers and IT administrators.

### Technology Stack

| Area | Technology |
| :--- | :--- |
| **Frontend** | Next.js (React) with Material UI (MUI) |
| **Backend** | Django (Python) |
| **Database** | Postgres |
| **AI / NLP** | GLiNER, SpanCat (spaCy), Microsoft Presidio |
| **Hosting** | This will be upto your organisation |

#### Hosting

The simplist hosting solution is to use [Docker](https://www.docker.com/) to host all of the services. This project is setup to use this solution.

### Security Measures

* **Dependency Management:** All dependencies are actively managed and scanned for vulnerabilities using `npm audit` (frontend) and `pip-audit` (backend via `uv`).
* **Framework Protections:** The service leverages Django's built-in security features, including its ORM to prevent SQL Injection, template auto-escaping to prevent XSS, and CSRF middleware.
* **Secrets Management:** All secrets (e.g., Django `SECRET_KEY`, database credentials) are managed via environment variables and are not stored in the codebase.

### AI / NLP Component Justification

The service uses a three-model hybrid pipeline to perform Named Entity Recognition (NER) on user-submitted text:

* **SpanCat (spaCy)** — a custom trained model that identifies both **Operational Data** and **Third-Party PII** based on your organisation's accepted redactions. This takes highest priority in the pipeline. If no model has been trained yet, the system falls back to the other two models.
* **GLiNER** — a zero-shot NER model downloaded from HuggingFace. It identifies **Third-Party PII** such as names, organisations, addresses, and dates of birth without requiring training data.
* **Microsoft Presidio** — a rule-based PII detection framework. It identifies structured **Third-Party PII** (phone numbers, email addresses, NHS numbers, postcodes, NI numbers) and structured **Operational Data** (crime reference numbers, collar numbers) using pattern recognisers.

The SpanCat model improves over time as more redactions are accepted and the model is retrained.

---

## Getting Started

### Prerequisites

* Node.js (v18 or later)
* Python (v3.13 or later)
* [uv](https://docs.astral.sh/uv/) (Python package manager)
* Docker

### Installation & Setup (Development)

1. **Clone the repository:**

    ```bash
    git clone https://github.com/msped/tractor
    ```

2. **Setup the Backend (Django):**

    ```bash
    # Navigate to the tractor directory
    cd tractor

    # Create and activate a virtual environment
    uv venv env
    source env/bin/activate  # On Windows use `env\Scripts\activate`

    # Install Python dependencies
    uv sync

    # Run database migrations
    python manage.py migrate

    # Create a .env file and add your environment variables
    cp .env.example .env
    ```

3. **Setup the Frontend (Next.js):**

    ```bash
    # Navigate to the frontend directory
    cd /frontend

    # Install Node.js dependencies
    npm install

    # Create a .env file for environment variables
    cp .env.example .env
    ```

### Running the Application in development

1. **Start the Django Backend Server:**

    ```bash
    # In the /backend directory
    python manage.py runserver
    ```

2. **Start the Next.js Frontend Server:**

    ```bash
    # In a new terminal, in the /frontend directory
    npm run dev
    ```

3. **Start django-q to listen for tasks**

    ```bash
    # In a new terminal, in the root directory
    python manage.py qcluster
    ```

The application should now be running locally at `http://localhost:3000`.

#### WeasyPrint Issue

If you get an error like cannot load library 'xxx': error xxx, it means that WeasyPrint can’t find this library. On macOS, you can set the DYLD_FALLBACK_LIBRARY_PATH environment variable [See more](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting):

`export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH`

---

## Model Management

### GLiNER (Third-Party PII)

The GLiNER model is downloaded from HuggingFace and registered in the database via a management command. On first setup, run:

```bash
python manage.py download_model
```

To download a specific model variant:

```bash
python manage.py download_model --name urchade/gliner_large-v2.1
```

### SpanCat (Trained Model)

The SpanCat model is trained on your organisation's accepted redactions. Training can be triggered manually from the Settings page or scheduled to run automatically. After training, the new model must be activated before it is used for processing.

Models are listed and activated via the **Settings → Models** page. Activating a new model will automatically deactivate the current active model.

### Training

Training will automatically collect accepted redactions from completed documents as training data. You can also upload pre-annotated Word documents from the Settings → Training section.

This process can be resource-intensive and may take some time depending on the amount of training data.
