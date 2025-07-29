import re
import os
import shutil
import zipfile
from .models import Case, Document, Redaction
import inflect
from .ai_service import extract_entities_from_text
from django.db import transaction
from django.core.files.base import ContentFile
from weasyprint import HTML, CSS


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


def _generate_pdf_from_document(document, mode='disclosure'):
    """
    Generates a PDF for a single document.
    mode: 'disclosure' (black boxes) or 'redacted' (color highlights)
    """
    text = document.extracted_text
    if not text:
        return None

    redactions = document.redactions.filter(is_accepted=True)

    # Sort redactions in reverse order to handle nested tags correctly
    sorted_redactions = sorted(
        redactions, key=lambda r: r.start_char, reverse=True)

    for r in sorted_redactions:
        if mode == 'disclosure':
            replacement = f'<span class="redaction">{r.text}</span>'
        else:  # 'redacted' mode
            replacement = f'<span class="redaction type-{r.redaction_type}">\
            {r.text}</span>'
        text = text[:r.start_char] + replacement + text[r.end_char:]

    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head><title>{document.filename}</title></head>
    <body>
    <pre style="white-space: pre-wrap; word-wrap: break-word; \
        font-family: monospace;">{text}</pre></body>
    </html>
    """

    css_string = """
    .redaction { background-color: black; color: black; }
    .type-PII { background-color: rgba(46, 204, 113, 0.7); color: initial; }
    .type-OP_DATA { background-color: rgba(0, 221, 255, 0.7); color: initial; }
    .type-DS_INFO { background-color: rgba(177, 156, 217, 0.8);\
          color: initial; }
    """

    return HTML(string=html_string).write_pdf(
        stylesheets=[CSS(string=css_string)]
    )


def export_case_documents(case_id):
    """
    Background task to generate a ZIP file for a case.
    """
    try:
        case = Case.objects.get(id=case_id)
    except Case.DoesNotExist:
        return

    # Create a temporary directory for this export
    temp_export_dir = f"/tmp/export_{case_id}"
    if os.path.exists(temp_export_dir):
        shutil.rmtree(temp_export_dir)

    # Define and create the required folder structure
    unedited_dir = os.path.join(temp_export_dir, 'unedited')
    redacted_dir = os.path.join(temp_export_dir, 'redacted')
    disclosure_dir = os.path.join(temp_export_dir, 'disclosure')
    os.makedirs(unedited_dir)
    os.makedirs(redacted_dir)
    os.makedirs(disclosure_dir)

    documents = case.documents.all()

    for doc in documents:
        # 1. Copy original file to 'unedited'
        if doc.original_file:
            shutil.copy(doc.original_file.path, os.path.join(
                unedited_dir, doc.original_file.name.split('/')[-1]))

        # 2. Generate 'redacted' PDF
        redacted_pdf_content = _generate_pdf_from_document(
            doc, mode='redacted')
        if redacted_pdf_content:
            with open(
                os.path.join(redacted_dir, f"{doc.filename}.pdf"), 'wb'
            ) as f:
                f.write(redacted_pdf_content)

        # 3. Generate 'disclosure' PDF
        disclosure_pdf_content = _generate_pdf_from_document(
            doc, mode='disclosure')
        if disclosure_pdf_content:
            with open(
                os.path.join(disclosure_dir, f"{doc.filename}.pdf"), 'wb'
            ) as f:
                f.write(disclosure_pdf_content)

    # 4. Create the ZIP file
    zip_file_path = f"{temp_export_dir}.zip"
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(temp_export_dir):
            for file in files:
                full_path = os.path.join(root, file)
                # Arcname is the path inside the zip file
                arcname = os.path.relpath(full_path, temp_export_dir)
                zipf.write(full_path, arcname)

    # 5. Save the ZIP to the Case model and update status
    with open(zip_file_path, 'rb') as f:
        zip_content = f.read()
        case.export_file.save(
            f"disclosure_package_{case.case_reference}.zip",
            ContentFile(
                zip_content
            ), save=False
        )

    case.export_status = Case.ExportStatus.COMPLETED
    case.save(update_fields=['export_file', 'export_status'])

    # 6. Clean up temporary files
    shutil.rmtree(temp_export_dir)
    os.remove(zip_file_path)
