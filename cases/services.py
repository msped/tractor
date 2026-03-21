import logging
import os
import re
import shutil
import zipfile
from html import escape as html_escape

import inflect
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from training.loader import DEFAULT_GLINER_MODEL, GLiNERModelManager, SpanCatModelManager
from training.services import extract_entities_from_text

from .models import Case, Document, DocumentExportSettings, Redaction

logger = logging.getLogger(__name__)

# Mapping from spaCy entity labels to Redaction types
ENTITY_LABEL_TO_REDACTION_TYPE = {
    "DS_INFORMATION": Redaction.RedactionType.DS_INFORMATION,
    "THIRD_PARTY": Redaction.RedactionType.THIRD_PARTY_PII,
    "OPERATIONAL": Redaction.RedactionType.OPERATIONAL_DATA,
}

# Common date formats for matching data subject DOB
_DOB_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%d %B %Y",
    "%d %b %Y",
    "%-d %B %Y",
    "%-d %b %Y",
]


def _matches_data_subject(text, case):
    """
    Check if entity text matches the case's data subject name or DOB.
    Returns True if the text should be excluded from THIRD_PARTY suggestions.
    """
    text_lower = text.strip().lower()
    if not text_lower:
        return False

    # Check against data subject name
    ds_name = getattr(case, "data_subject_name", None)
    if ds_name:
        ds_name_lower = ds_name.strip().lower()
        # Full name match (case-insensitive)
        if text_lower == ds_name_lower or ds_name_lower in text_lower:
            return True
        # Individual name parts match (ignore single-char parts like initials)
        name_parts = [p for p in ds_name_lower.split() if len(p) > 1]
        if text_lower in name_parts:
            return True

    # Check against data subject DOB
    ds_dob = getattr(case, "data_subject_dob", None)
    if ds_dob:
        for fmt in _DOB_FORMATS:
            try:
                formatted = ds_dob.strftime(fmt)
                if text_lower == formatted.lower():
                    return True
            except ValueError:
                continue

    return False


def process_document_and_create_redactions(document_id):
    """
    The main background task. Fetches the active model from the database.
    """
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        print(f"Document with id {document_id} not found.")
        return

    if document.status != Document.Status.PROCESSING:
        print(f"Document {document_id} is no longer processing (status: {document.status}). Aborting.")
        return

    gliner_manager = GLiNERModelManager.get_instance()
    spancat_manager = SpanCatModelManager.get_instance()

    document.spacy_model = spancat_manager.get_model_entry()
    document.save(update_fields=["spacy_model"])

    model_display = gliner_manager.model_name or DEFAULT_GLINER_MODEL
    print(
        f"Starting text extraction and AI analysis for {document.filename} \
        using model '{model_display}'..."
    )

    extracted_text, ai_suggestions, tables, structure = extract_entities_from_text(document.original_file.path)

    if not extracted_text:
        document.status = Document.Status.ERROR
        document.save(update_fields=["status"])
        return

    document.extracted_text = extracted_text
    document.extracted_tables = tables
    document.extracted_structure = structure
    document.save(update_fields=["extracted_text", "extracted_tables", "extracted_structure"])

    case = document.case

    with transaction.atomic():
        for suggestion in ai_suggestions:
            # Filter out entities matching the data subject's name/DOB
            if _matches_data_subject(suggestion["text"], case):
                continue

            redaction_type = ENTITY_LABEL_TO_REDACTION_TYPE.get(
                suggestion["label"],
                Redaction.RedactionType.THIRD_PARTY_PII,  # fallback default
            )
            Redaction.objects.create(
                document=document,
                start_char=suggestion["start_char"],
                end_char=suggestion["end_char"],
                text=suggestion["text"],
                redaction_type=redaction_type,
                is_suggestion=True,
                is_accepted=False,
            )

    document.status = Document.Status.READY_FOR_REVIEW
    document.save(update_fields=["status"])
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
        source_redaction = Redaction.objects.select_related("document__case").get(id=redaction_id)
    except Redaction.DoesNotExist:
        print(f"Source redaction with id {redaction_id} not found.")
        return

    search_term = source_redaction.text
    source_document = source_redaction.document
    case = source_document.case

    other_documents = Document.objects.filter(
        case=case, status__in=[Document.Status.READY_FOR_REVIEW, Document.Status.COMPLETED]
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
    sorted_variations = sorted(search_variations, key=len, reverse=True)

    # Create a regex pattern that matches variations as a whole word.
    # The \b ensures we only match whole words/phrases.
    pattern = r"\b(" + "|".join(re.escape(term) for term in sorted_variations) + r")\b"

    print(
        f"Searching for variations of '{search_term}' in \
        {other_documents.count()} other documents for case \
        {case.case_reference}."
    )

    for document in other_documents:
        if not document.extracted_text:
            continue

        document_modified = False

        with transaction.atomic():
            # Find all matches for the pattern
            for match in re.finditer(pattern, document.extracted_text, re.IGNORECASE):
                start, end = match.span()
                text = match.group(0)

                # Try to find an existing redaction at this position
                existing_redaction = (
                    Redaction.objects.filter(document=document, start_char=start, end_char=end)
                    .exclude(redaction_type=Redaction.RedactionType.DS_INFORMATION)
                    .first()
                )

                if existing_redaction:
                    # A redaction already exists.
                    # Update it if it's not already DS_INFO.
                    if existing_redaction.redaction_type != Redaction.RedactionType.DS_INFORMATION:
                        existing_redaction.redaction_type = Redaction.RedactionType.DS_INFORMATION
                        # Reset its status to a pending suggestion for review
                        existing_redaction.is_suggestion = True
                        existing_redaction.is_accepted = False
                        existing_redaction.justification = None
                        existing_redaction.save(
                            update_fields=["redaction_type", "is_suggestion", "is_accepted", "justification"]
                        )
                        document_modified = True
                else:
                    # No redaction exists, so create a new one.
                    Redaction.objects.create(
                        document=document,
                        start_char=start,
                        end_char=end,
                        text=text,
                        redaction_type=Redaction.RedactionType.DS_INFORMATION,
                        is_suggestion=True,
                        is_accepted=False,
                    )
                    document_modified = True

            # If we modified this document and it was already completed,
            # revert its status so it can be reviewed again.
            if document_modified and document.status == Document.Status.COMPLETED:
                document.status = Document.Status.READY_FOR_REVIEW
                document.save(update_fields=["status"])


def _apply_redactions_to_segment(full_text, start, end, sorted_redactions, mode):
    """
    Apply accepted redactions to a slice of full_text[start:end].
    Returns an HTML string with redaction spans inserted.
    """
    parts = []
    prev = start

    for r in sorted_redactions:
        if r.end_char <= start or r.start_char >= end:
            continue

        r_start = max(r.start_char, start)
        r_end = min(r.end_char, end)

        if r_start < prev:
            continue

        # Expand backwards to include any immediately preceding prefix symbol (e.g. '#')
        # that was not captured in the stored span (handles documents processed before
        # the extraction-layer fix).
        while r_start > prev and full_text[r_start - 1] in {"#"}:
            r_start -= 1

        parts.append(html_escape(full_text[prev:r_start]))

        # Use the clipped portion within this segment, not r.text, so that cross-cell
        # redactions don't bleed the full text into both cells.
        clipped_text = full_text[r_start:r_end]
        is_redaction_start = r_start == r.start_char

        if mode == "disclosure":
            if is_redaction_start and hasattr(r, "context"):
                part = f'<span class="redaction disclosure-context">[{html_escape(r.context.text)}]</span>'
            else:
                block_text = "█" * len(clipped_text)
                part = f'<span class="redaction">{block_text}</span>'
        else:
            part = f'<span class="redaction type-{r.redaction_type}">{html_escape(clipped_text)}</span>'
            if is_redaction_start and hasattr(r, "context"):
                part += f'<span class="internal-context-note">[Context: {html_escape(r.context.text)}]</span>'

        parts.append(part)
        prev = r_end

    parts.append(html_escape(full_text[prev:end]))
    return "".join(parts)


def _render_table_with_redactions(table_data, full_text, sorted_redactions, mode):
    """
    Render a table as an HTML <table> with redactions applied within each cell.
    Falls back to escaped plain text if no cell data is available.
    """
    cells = table_data.get("cells", [])

    if not cells:
        return html_escape(table_data.get("text", ""))

    col_widths = table_data.get("colWidths", [])
    has_merge_info = any("isMergedContinuation" in c for c in cells)

    rows_dict = {}
    for cell in cells:
        row_idx = cell["row"]
        if row_idx not in rows_dict:
            rows_dict[row_idx] = {}
        rows_dict[row_idx][cell["col"]] = cell

    # For documents processed before merge detection was added, apply a heuristic:
    # adjacent cells in the same row with identical non-empty text are likely merged.
    if not has_merge_info:
        for row_cells in rows_dict.values():
            prev_cell = None
            for col_idx in sorted(row_cells.keys()):
                cell = row_cells[col_idx]
                cell_text = cell["text"].strip()
                prev_text = prev_cell["text"].strip() if prev_cell is not None else None
                if prev_cell is not None and cell_text and cell_text == prev_text:
                    cell["isMergedContinuation"] = True
                    prev_cell["colspan"] = prev_cell.get("colspan", 1) + 1
                else:
                    cell.setdefault("isMergedContinuation", False)
                    cell.setdefault("colspan", 1)
                    cell.setdefault("rowspan", 1)
                    prev_cell = cell
    else:
        for cell in cells:
            cell.setdefault("colspan", 1)
            cell.setdefault("rowspan", 1)

    # Derive equal fallback widths from physical column count (including merge cols)
    if not col_widths:
        num_cols = max((cell["col"] for cell in cells), default=0) + 1
        col_widths = [round(100 / num_cols, 2)] * num_cols

    table_html = '<table style="border-collapse: collapse; width: 100%; margin: 1em 0; table-layout: fixed;">'
    table_html += "<colgroup>"
    for w in col_widths:
        table_html += f'<col style="width: {w}%;">' if w is not None else "<col>"
    table_html += "</colgroup>"

    for row_idx in sorted(rows_dict.keys()):
        row_cells = rows_dict[row_idx]
        table_html += "<tr>"
        for col_idx in sorted(row_cells.keys()):
            cell = row_cells[col_idx]
            if cell.get("isMergedContinuation", False):
                continue
            colspan = cell.get("colspan", 1)
            rowspan = cell.get("rowspan", 1)
            cell_style = cell.get("style", "padding: 6px 8px;")
            cell_content = _apply_redactions_to_segment(full_text, cell["start"], cell["end"], sorted_redactions, mode)
            span_attrs = ""
            if colspan > 1:
                span_attrs += f' colspan="{colspan}"'
            if rowspan > 1:
                span_attrs += f' rowspan="{rowspan}"'
            table_html += f'<td{span_attrs} style="{cell_style}">{cell_content}</td>'
        table_html += "</tr>"

    table_html += "</table>"
    return table_html


def _build_export_css(settings, case_reference=""):
    """
    Dynamically build the WeasyPrint CSS string from DocumentExportSettings.
    Header/footer use @page margin boxes. Companion left/right boxes are
    explicitly zeroed (width: 0; content: "") so the center box gets the full
    available width and long text wraps correctly rather than overflowing.
    """
    has_header = bool(settings.header_text)
    has_footer = bool(settings.footer_text)
    has_page_numbers = settings.page_numbers_enabled

    top_margin = "2.5cm" if has_header else "2cm"
    bottom_margin = "2.5cm" if (has_footer or has_page_numbers) else "2cm"

    page_rules = ""
    if has_header:
        escaped = settings.header_text.replace('"', '\\"')
        page_rules += (
            '  @top-left { content: ""; width: 0; }\n'
            f'  @top-center {{ content: "{escaped}"; font-size: 9pt; color: #555;'
            f" text-align: center; white-space: normal; }}\n"
            '  @top-right { content: ""; width: 0; }\n'
        )
    if has_footer and has_page_numbers:
        escaped = settings.footer_text.replace('"', '\\"')
        page_rules += (
            '  @bottom-left { content: ""; width: 0; }\n'
            f'  @bottom-center {{ content: "{escaped}\\A Page " counter(page) " of " counter(pages);'
            f" font-size: 9pt; color: #555; text-align: center; white-space: pre-wrap; }}\n"
            '  @bottom-right { content: ""; width: 0; }\n'
        )
    elif has_footer:
        escaped = settings.footer_text.replace('"', '\\"')
        page_rules += (
            '  @bottom-left { content: ""; width: 0; }\n'
            f'  @bottom-center {{ content: "{escaped}"; font-size: 9pt; color: #555;'
            f" text-align: center; white-space: normal; }}\n"
            '  @bottom-right { content: ""; width: 0; }\n'
        )
    elif has_page_numbers:
        page_rules += (
            '  @bottom-left { content: ""; width: 0; }\n'
            '  @bottom-center { content: "Page " counter(page) " of " counter(pages);'
            " font-size: 9pt; color: #555; text-align: center; }\n"
            '  @bottom-right { content: ""; width: 0; }\n'
        )

    watermark_label = settings.watermark_text
    if settings.watermark_include_case_ref and case_reference:
        watermark_label = f"{watermark_label} {case_reference}" if watermark_label else case_reference

    watermark_css = ""
    if watermark_label:
        watermark_css = (
            ".watermark { position: fixed; top: 45%; left: 50%; "
            "transform: translate(-50%, -50%) rotate(-45deg); "
            "font-size: 72pt; color: rgba(200,200,200,0.35); white-space: nowrap; }\n"
        )

    return (
        f"@page {{ size: A4; margin: {top_margin} 2cm {bottom_margin} 2cm;\n{page_rules}}}\n"
        "body { line-height: 1.4; }\n"
        ".text-block { white-space: pre-wrap; word-wrap: break-word; }\n"
        "table { border-collapse: collapse; width: 100%; margin: 1em 0; }\n"
        "td { padding: 4px 6px; text-align: left; white-space: normal; overflow-wrap: break-word; word-wrap: break-word; vertical-align: top; }\n"
        "th { background-color: #f2f2f2; font-weight: bold; }\n"
        ".redaction { background-color: black; color: black; }\n"
        ".disclosure-context { background-color: initial; color: initial; font-style: italic; }\n"
        ".type-PII { background-color: rgba(46, 204, 113, 0.7); color: initial; }\n"
        ".type-OP_DATA { background-color: rgba(0, 221, 255, 0.7); color: initial; }\n"
        ".type-DS_INFO { background-color: rgba(177, 156, 217, 0.8); color: initial; }\n"
        ".internal-context-note { color: #555; font-style: italic; font-size: 0.9em; }\n" + watermark_css
    )


def _generate_pdf_from_document(document, mode="disclosure", export_settings=None, case_reference=""):
    """
    Generates a PDF for a single document.
    mode: 'disclosure' (black boxes) or 'redacted' (color highlights)
    DOCX tables are rendered as HTML tables with redactions applied per-cell.
    """
    if export_settings is None:
        export_settings = DocumentExportSettings.get()

    text = document.extracted_text
    if not text:
        return None

    redactions = document.redactions.filter(is_accepted=True).select_related("context")
    sorted_redactions = sorted(redactions, key=lambda r: r.start_char)

    tables = document.extracted_tables or []
    sorted_tables = sorted(tables, key=lambda t: t["ner_start"])

    # Split the document into table regions and plain text regions, rendering each
    # appropriately. Table cells are rendered as <td> elements with redactions applied
    # within the cell bounds. Plain text segments use html_escape to prevent the
    # document's own <, >, & characters being interpreted as HTML.
    html_parts = []
    prev_pos = 0

    for table in sorted_tables:
        ner_start = table["ner_start"]
        ner_end = table["ner_end"]

        if prev_pos < ner_start:
            segment = _apply_redactions_to_segment(text, prev_pos, ner_start, sorted_redactions, mode)
            html_parts.append(f'<div class="text-block">{segment}</div>')

        html_parts.append(_render_table_with_redactions(table, text, sorted_redactions, mode))
        prev_pos = ner_end + 1  # +1 to skip the newline separator after the table

    if prev_pos < len(text):
        segment = _apply_redactions_to_segment(text, prev_pos, len(text), sorted_redactions, mode)
        html_parts.append(f'<div class="text-block">{segment}</div>')

    body_content = "".join(html_parts)

    watermark_label = export_settings.watermark_text
    if export_settings.watermark_include_case_ref and case_reference:
        watermark_label = f"{watermark_label} {case_reference}" if watermark_label else case_reference
    watermark_html = f'<div class="watermark">{html_escape(watermark_label)}</div>' if watermark_label else ""

    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head><title>{html_escape(document.filename or "")}</title></head>
    <body style="font-family: {export_settings.font_family_css};">
    {watermark_html}
    {body_content}
    </body>
    </html>
    """

    css_string = _build_export_css(export_settings, case_reference)

    font_config = FontConfiguration()
    return HTML(string=html_string).write_pdf(
        stylesheets=[CSS(string=css_string, font_config=font_config)], font_config=font_config
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
    unedited_dir = os.path.join(temp_export_dir, "unedited")
    redacted_dir = os.path.join(temp_export_dir, "redacted")
    disclosure_dir = os.path.join(temp_export_dir, "disclosure")
    os.makedirs(unedited_dir)
    os.makedirs(redacted_dir)
    os.makedirs(disclosure_dir)

    export_settings = DocumentExportSettings.get()
    documents = case.documents.all()

    for doc in documents:
        if doc.original_file:
            shutil.copy(doc.original_file.path, os.path.join(unedited_dir, doc.original_file.name.split("/")[-1]))

        redacted_pdf_content = _generate_pdf_from_document(
            doc, mode="redacted", export_settings=export_settings, case_reference=case.case_reference
        )
        if redacted_pdf_content:
            with open(os.path.join(redacted_dir, f"{doc.filename}.pdf"), "wb") as f:
                f.write(redacted_pdf_content)

        disclosure_pdf_content = _generate_pdf_from_document(
            doc, mode="disclosure", export_settings=export_settings, case_reference=case.case_reference
        )
        if disclosure_pdf_content:
            with open(os.path.join(disclosure_dir, f"{doc.filename}.pdf"), "wb") as f:
                f.write(disclosure_pdf_content)

    zip_file_path = f"{temp_export_dir}.zip"
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(temp_export_dir):
            for file in files:
                full_path = os.path.join(root, file)
                # Arcname is the path inside the zip file
                arcname = os.path.relpath(full_path, temp_export_dir)
                zipf.write(full_path, arcname)

    with open(zip_file_path, "rb") as f:
        zip_content = f.read()
        case.export_file.save(f"disclosure_package_{case.case_reference}.zip", ContentFile(zip_content), save=False)

    case.export_status = Case.ExportStatus.COMPLETED
    case.save(update_fields=["export_file", "export_status"])

    shutil.rmtree(temp_export_dir)
    os.remove(zip_file_path)


def delete_cases_past_retention_date():
    today = timezone.now().date()

    cases_to_delete_qs = Case.objects.filter(retention_review_date__lt=today)
    count = cases_to_delete_qs.count()

    if count == 0:
        message = "No cases are due for deletion."
        logger.info(message)
        return message

    logger.info(f"Found {count} case(s) due for deletion.")

    deleted_case_refs = []
    for case in cases_to_delete_qs.iterator():
        case_ref = case.case_reference
        logger.info(f"Deleting case {case_ref} " + f"(Retention Date: {case.retention_review_date})")
        case.delete()
        deleted_case_refs.append(case_ref)
        logger.info(f"Successfully deleted case {case_ref}.")

    return f"Successfully deleted {len(deleted_case_refs)} " + f"case(s): {', '.join(deleted_case_refs)}."
