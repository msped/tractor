import re
from .models import Document, Redaction
import inflect
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


def find_and_flag_matching_text_in_case(redaction_id):
    """
    When a user marks a piece of text as DS_INFORMATION, this function
    searches for that same text in all other documents in the case and
    creates new DS_INFORMATION suggestions.
    """
    try:
        source_redaction = Redaction.objects.select_related(
            'document__case').get(id=redaction_id)
    except Redaction.DoesNotExist:
        print(f"Source redaction with id {redaction_id} not found.")
        return

    search_term = source_redaction.text
    source_document = source_redaction.document
    case = source_document.case

    # Get all other documents in the case.
    other_documents = Document.objects.filter(
        case=case,
        status__in=[
            Document.Status.READY_FOR_REVIEW,
            Document.Status.COMPLETED
        ]
    ).exclude(id=source_document.id)

    if not search_term.strip():
        return

    p = inflect.engine()
    search_variations = {search_term}

    # Generate plural form (e.g., "party" -> "parties")
    plural_form = p.plural(search_term)
    if plural_form and plural_form != search_term:
        search_variations.add(plural_form)

    # Generate singular form (e.g., "parties" -> "party")
    singular_form = p.singular_noun(search_term)
    if singular_form and singular_form != search_term:
        search_variations.add(singular_form)

    # Sort variations by length (desc) to match longer phrases first,
    # e.g., "data subjects" before "data".
    sorted_variations = sorted(list(search_variations), key=len, reverse=True)

    # Create a regex pattern that matches variations as a whole word.
    # The \b ensures we only match whole words/phrases.
    pattern = r'\b(' + '|'.join(re.escape(term)
                                for term in sorted_variations) + r')\b'

    print(
        f"Searching for variations of '{search_term}' in \
        {other_documents.count()} other documents for case \
        {case.case_reference}.")

    for document in other_documents:
        if not document.extracted_text:
            continue

        document_modified = False

        with transaction.atomic():
            # Find all non-overlapping, case-insensitive
            # matches for the pattern
            for match in re.finditer(
                pattern,
                document.extracted_text,
                re.IGNORECASE
            ):
                start, end = match.span()
                text = match.group(0)

                # Try to find an existing redaction at this position
                existing_redaction = Redaction.objects.filter(
                    document=document, start_char=start, end_char=end
                ).exclude(
                    redaction_type=Redaction.RedactionType.DS_INFORMATION
                ).first()

                if existing_redaction:
                    # A redaction already exists.
                    # Update it if it's not already DS_INFO.
                    if existing_redaction.redaction_type != \
                            Redaction.RedactionType.DS_INFORMATION:
                        existing_redaction.redaction_type = \
                            Redaction.RedactionType.DS_INFORMATION
                        # Reset its status to a pending suggestion for review
                        existing_redaction.is_suggestion = True
                        existing_redaction.is_accepted = False
                        existing_redaction.justification = None
                        existing_redaction.save(
                            update_fields=[
                                'redaction_type',
                                'is_suggestion',
                                'is_accepted',
                                'justification'
                            ]
                        )
                        document_modified = True
                else:
                    # No redaction exists, so create a new one.
                    Redaction.objects.create(
                        document=document,
                        start_char=start, end_char=end, text=text,
                        redaction_type=Redaction.RedactionType.DS_INFORMATION,
                        is_suggestion=True, is_accepted=False
                    )
                    document_modified = True

            # If we modified this document and it was already completed,
            # revert its status so it can be reviewed again.
            if document_modified and document.status \
                    == Document.Status.COMPLETED:
                document.status = Document.Status.READY_FOR_REVIEW
                document.save(update_fields=['status'])
