# Subject Access Manager (SAM)

Locally ran application to redact documents for subject access requests.

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
| **AI / NLP** | spaCy v3 |
| **Hosting** | This will be upto your organisation |

#### Hosting

The simplist hosting solution is to use [Docker](https://www.docker.com/) to host all of the services. This project is setup to use this solution.

### Security Measures

* **Dependency Management:** All dependencies are actively managed and scanned for vulnerabilities using `npm audit` (frontend) and `pip-audit` (backend).
* **Framework Protections:** The service leverages Django's built-in security features, including its ORM to prevent SQL Injection, template auto-escaping to prevent XSS, and CSRF middleware.
* **Secrets Management:** All secrets (e.g., Django `SECRET_KEY`, database credentials) are managed via environment variables and are not stored in the codebase.

### AI / NLP Component Justification

The service uses the **spaCy** library to perform Named Entity Recognition (NER) on user-submitted text. This is essential for automatically identifying key information (like people, places, and dates) to improve service efficiency. The spaCy library requires the torch framework as its machine learning backend.

As part of the package, during setup departments can train the model on information based off previous Subject Access Requests. This ensures that the information it identifies will speed up your organisations workflow.

---

## Getting Started

### Prerequisites

* Node.js (v18 or later)
* Python (v3.10 or later)
* Docker

### Installation & Setup (Development)

1. **Clone the repository:**

    ```bash
    git clone https://github.com/msped/subject-access-manager
    ```

2. **Setup the Backend (Django):**

    ```bash
    # Navigate to the backend directory
    cd backend

    # Create and activate a virtual environment
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`

    # Install Python dependencies
    pip install -r requirements.txt

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

    # Create a .env.local file for environment variables
    cp .env.local.example .env.local
    ```

### Running the Application

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

The application should now be running locally at `http://localhost:3000`.

#### WeasyPrint Issue

If you get an error like cannot load library 'xxx': error xxx, it means that WeasyPrint can’t find this library. On macOS, you can set the DYLD_FALLBACK_LIBRARY_PATH environment variable:

`export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH`

---

## Model Training

The application supports training custom redaction models based on the redactions that users accept in completed cases as well as the uploading of completed material to train from.

### How it Works

1. **Data Collection**: The system gathers all documents marked as "Completed". For each document, it collects the text and the set of accepted redactions.
2. **Training Format**: This data is converted into the format required by spaCy for training Named Entity Recognition (NER) models.
3. **Training Process**: A new, blank spaCy model is trained from scratch using this data. The training process runs for a set number of iterations to improve the model's accuracy.
4. **Model Versioning**: After training, the new model is saved to the `nlp_models/` directory with a timestamped version name (e.g., `model_20240521_143000`). A record of this new model is created in the database.

### Running the Training

Training will run automatically on redactions where applicable and at the time specified below. In the admin page, you can upload your own Documents, with highlighted redactions, to use for training.

This process can be resource-intensive and may take some time depending on the amount of training data.

### Scheduled training

You can run scheduled training through the Django Admin. Under Django Q, you can add a new entry with the following:

* Name: Monthly Model Training (or whatever you prefer)
* Func: `training.tasks.train_model`
* Kwargs: `{"source": "redactions"}`
* Schedule Type: Select from the drop down menu
* Repeats: -1 (This means it will repeat forver)
* Next Run: Set the date and time for the first time you want the training to run.

### Managing Models

After training, new models are available but not active. An administrator must activate a model for it to be used for new document processing.

* **Default Model**: If no custom model is active, the system falls back to the default `en_core_web_lg` spaCy model.
* **Activating a Model**: Model activation can be handled via the admin page. Activating a new model will automatically deactivate any other active model.
