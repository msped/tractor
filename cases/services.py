from .models import Document, Redaction
from .ai_service import extract_entities_from_text
from django.db import transaction


def process_document_and_create_redactions(document_id):
    """
    Extracts text, runs AI, and creates redactions.
    """
    # --- Part 1: Fetch Document ---
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        print(f"Document with id {document_id} not found.")
        return

    # --- Part 2: AI Integration ---
    print(f"Starting AI analysis for {document.filename}...")
    extracted_text, ai_suggestions = extract_entities_from_text(
        document.original_file.path)
    print(f"Found {len(ai_suggestions)} potential redactions.")

    # --- Part 3: Create Redaction Objects in the Database ---
    # Transaction ensures all redactions are created or none are.
    with transaction.atomic():
        for suggestion in ai_suggestions:
            # For the prototype, we'll map all entities to PII
            # In production, the AI would return the correct type.
            redaction_type = Redaction.RedactionType.THIRD_PARTY_PII

            Redaction.objects.create(
                document=document,
                start_char=suggestion['start_char'],
                end_char=suggestion['end_char'],
                text=suggestion['text'],
                redaction_type=redaction_type,
                is_suggestion=True,
                is_accepted=False
            )

    # --- Final Step: Update Status and Extracted Text ---
    document.extracted_text = extracted_text
    document.status = Document.Status.READY_FOR_REVIEW
    document.save(update_fields=['status', 'extracted_text'])
    print(
        f"Successfully processed {document.filename}. \
        Status: READY_FOR_REVIEW"
    )
