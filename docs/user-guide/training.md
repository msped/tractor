# Model Training

Tractor can train a custom SpanCat model from the redactions your team has accepted. The more accepted redactions you accumulate, the more accurate the model becomes for your organisation's specific documents.

!!! note
    Training requires the `worker` service (`python manage.py qcluster`) to be running. The training task runs asynchronously in the background.

## How Training Works

When a document is marked as completed, its accepted **Operational Data** redactions are stored as training examples. Tractor uses these to fine-tune a SpanCat (Span Categorisation) model that learns to recognise **OPERATIONAL** patterns — reference numbers, case IDs, and domain-specific identifiers.

!!! note
    PII (Third-Party) redactions accepted during review are **not** used to train SpanCat, because they originate from GLiNER suggestions which may contain errors. Training on them could cause SpanCat to reinforce those mistakes. Third-Party signal comes exclusively from manually annotated training documents (see [Uploading Training Documents](#uploading-training-documents)).

Once trained, the new model must be **activated** before it is used for processing. The trained model takes the second-highest priority in the four-model pipeline — ahead of built-in Presidio, GLiNER, and Gemma — with only admin-configured custom Presidio rules taking precedence.

## Running a Training Job

### Scheduled Training

The recommended approach is to set up a recurring training schedule so the model stays up to date automatically.

1. Go to **Settings → Training** and find the **Schedule Training** card.
2. Select a schedule (e.g. weekly on Sunday at midnight).
3. Click **Save Schedule**. The training job will run automatically at the configured time.

Only one schedule can be active at a time. To change the schedule, delete the existing one and create a new one.

### Manual Training

To trigger training immediately:

1. Go to **Settings → Training** and find the **Manual Training** card.
2. Optionally upload pre-annotated `.docx` documents as additional training data (see [below](#uploading-training-documents)).
3. Click **Run Training Now**.

A banner will appear at the top of the page while training is in progress. Training time depends on the amount of data — a few hundred examples typically completes in under a minute.

## Uploading Training Documents

You can supplement training data from accepted redactions by uploading pre-annotated Word documents. This is useful when you have existing labelled data or want to bootstrap the model before any documents have been completed.

Annotations are detected via Word's text highlight colours:

- **Bright green** highlight → THIRD_PARTY entity
- **Turquoise** highlight → OPERATIONAL entity

Both body paragraphs and table cells are scanned for highlighted text, so annotations in occurrence report tables (e.g. the Link/No columns or involved-officer blocks) are included in training.

1. Go to **Settings → Training → Manual Training**.
2. Click **Upload Documents** and select one or more `.docx` files.
3. The uploaded documents appear in the list below. They will be included in the next training run (scheduled or manual).
4. After training completes, the documents are marked as processed and will not be included in subsequent runs.

## Monitoring Training Runs

Training run history is available in **Settings → Training → Training Runs**. Each run shows:

- **Status**: whether training completed successfully or encountered an error
- **Started / Finished**: timestamps for the run
- **Source**: whether training data came from accepted redactions, uploaded documents, or both
- **Model**: the model produced by the run

If a run fails, the error message is shown in the run detail. Common causes include insufficient training data (fewer than 75 examples) or resource constraints.

## Activating a Model

After a successful training run, the new model must be activated before it is used for document processing.

1. Go to **Settings → Models**.
2. Find the model produced by the training run (listed by date).
3. Click **Set Active**. The previously active model is deactivated automatically.

From this point on, newly uploaded documents will be processed using the activated model. Documents already in the system are not reprocessed.

## Deleting Models

Models can be deleted from **Settings → Models** as long as they have not been used to process any documents. Models that have processed documents cannot be deleted (the button will be disabled with an explanation).
