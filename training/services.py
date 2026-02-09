import re

from docx import Document
from docx.oxml.ns import qn
from spacy_layout import spaCyLayout

from .loader import SpacyModelManager


def _table_has_borders(table):
    """
    Check if a DOCX table has visible borders by inspecting w:tblBorders.
    Returns True if any border element has a visible style (e.g. "single", "double"),
    False if all borders are "none" or "nil".
    Defaults to True if tblPr or tblBorders is absent (Word default is bordered).
    """
    tbl_pr = table._tbl.find(qn("w:tblPr"))
    if tbl_pr is None:
        return True

    tbl_borders = tbl_pr.find(qn("w:tblBorders"))
    if tbl_borders is None:
        return True

    border_names = ["w:top", "w:left", "w:bottom", "w:right", "w:insideH", "w:insideV"]
    no_border_values = {"none", "nil"}

    for name in border_names:
        border_el = tbl_borders.find(qn(name))
        if border_el is not None:
            val = border_el.get(qn("w:val"))
            if val and val not in no_border_values:
                return True

    return False


def extract_table_with_styling(table, table_start_position, has_borders=True):
    """
    Extract table with full cell formatting as structured data for frontend rendering.
    Returns (html, cells) where:
    - html: Pre-rendered HTML for fallback
    - cells: List of cell data with text, styling, and character positions for highlighting
    """
    html = '<table style="border-collapse: collapse; width: 100%;">'
    cells = []
    position = table_start_position

    for row_idx, row in enumerate(table.rows):
        html += "<tr>"
        for col_idx, cell in enumerate(row.cells):
            # Get cell shading (background color)
            tc_pr = cell._tc.get_or_add_tcPr()
            shading = tc_pr.find(qn("w:shd"))
            bg_color = None
            if shading is not None:
                fill = shading.get(qn("w:fill"))
                if fill and fill != "auto":
                    bg_color = f"#{fill}"

            # Build cell style
            cell_style = "border: 1px solid #000; padding: 6px 8px;" if has_borders else "padding: 6px 8px;"
            if bg_color:
                cell_style += f" background-color: {bg_color};"

            # Get cell text (plain, for NER matching)
            cell_text = cell.text.replace("\n", " ")

            # Get text with run formatting for HTML
            cell_html = ""
            text_runs = []
            for para in cell.paragraphs:
                for run in para.runs:
                    text = run.text
                    if not text:
                        continue
                    styles = []
                    if run.bold:
                        styles.append("font-weight: bold")
                    if run.italic:
                        styles.append("font-style: italic")
                    if run.font.color and run.font.color.rgb:
                        styles.append(f"color: #{run.font.color.rgb}")

                    text_runs.append({"text": text, "style": "; ".join(styles) if styles else None})

                    if styles:
                        cell_html += f'<span style="{"; ".join(styles)}">{text}</span>'
                    else:
                        cell_html += text
                cell_html += "<br>"

            # Store cell data with position info
            cell_end = position + len(cell_text)
            cells.append(
                {
                    "row": row_idx,
                    "col": col_idx,
                    "text": cell_text,
                    "start": position,
                    "end": cell_end,
                    "style": cell_style,
                    "bgColor": bg_color,
                    "runs": text_runs,
                }
            )

            # Move position: +1 for tab separator (or newline at end of row)
            position = cell_end + 1

            html += f'<td style="{cell_style}">{cell_html.rstrip("<br>")}</td>'
        html += "</tr>"

    html += "</table>"
    return html, cells


def extract_document_structure(path):
    """
    Extract document structure from DOCX files using python-docx.
    Returns (elements, tables_data) where:
    - elements: list of {type, level, text, start, end} for headings/paragraphs
    - tables_data: list of {id, html, text, ner_start, ner_end} for tables

    For non-DOCX files, returns (None, None) to signal fallback to spaCyLayout.
    """
    if not path.lower().endswith((".docx", ".doc")):
        return None, None

    try:
        doc = Document(path)
    except Exception:
        return None, None

    elements = []
    tables_data = []
    position = 0
    full_text_parts = []
    table_index = 0

    # Iterate through document body elements in order
    for element in doc.element.body:
        tag = element.tag.split("}")[-1]  # Remove namespace

        if tag == "p":
            # Find the matching paragraph object
            for para in doc.paragraphs:
                if para._element is element:
                    text = para.text
                    if not text.strip():
                        continue

                    style_name = para.style.name if para.style else "Normal"
                    element_type = "heading" if style_name.startswith("Heading") else "paragraph"
                    level = None
                    if element_type == "heading":
                        try:
                            level = int(style_name.split()[-1])
                        except (ValueError, IndexError):
                            level = 1

                    elements.append(
                        {
                            "type": element_type,
                            "level": level,
                            "text": text,
                            "start": position,
                            "end": position + len(text),
                        }
                    )
                    full_text_parts.append(text)
                    position += len(text) + 1  # +1 for newline
                    break

        elif tag == "tbl":
            # Find the matching table object
            for tbl in doc.tables:
                if tbl._tbl is element:
                    # Build plain text for NER (tab-separated values)
                    text_rows = []
                    for row in tbl.rows:
                        row_cells = [cell.text.replace("\n", " ") for cell in row.cells]
                        text_rows.append("\t".join(row_cells))
                    table_text = "\n".join(text_rows)

                    # Check if table has visible borders
                    has_borders = _table_has_borders(tbl)

                    # Extract styled HTML and cell data with positions
                    html, cells = extract_table_with_styling(tbl, position, has_borders)

                    tables_data.append(
                        {
                            "id": table_index,
                            "html": html,
                            "text": table_text,
                            "cells": cells,
                            "hasBorders": has_borders,
                            "ner_start": position,
                            "ner_end": position + len(table_text),
                        }
                    )

                    # Add table element to structure
                    elements.append(
                        {
                            "type": "table",
                            "table_id": table_index,
                            "start": position,
                            "end": position + len(table_text),
                        }
                    )

                    full_text_parts.append(table_text)
                    position += len(table_text) + 1
                    table_index += 1
                    break

    full_text = "\n".join(full_text_parts)
    return elements, tables_data, full_text


def extract_entities_from_text(path):
    """
    Processes a document with the currently active spaCy model.
    Extracts tables separately and stores them with HTML and text
    representations. Returns (ner_text, entities, tables, structure).

    For DOCX files, uses python-docx to extract document structure
    (headings, paragraphs, tables with styling). For other formats,
    falls back to spaCyLayout.

    Each table entry includes ner_start/ner_end positions marking
    where the table text sits within the returned ner_text.

    Structure is a list of elements with type, text, and character positions.
    """
    nlp = SpacyModelManager.get_instance().get_model()
    if not nlp:
        raise ValueError("No active spaCy model found.")

    # Try structure extraction for DOCX files first
    structure_result = extract_document_structure(path)

    if structure_result[0] is not None:
        # DOCX file - use python-docx extraction
        structure, tables, ner_text = structure_result

        if not ner_text or not ner_text.strip():
            raise ValueError("No text found in the document.")

        ner_doc = nlp(ner_text)

        results = []
        for ent in ner_doc.ents:
            results.append(
                {
                    "text": ent.text,
                    "label": ent.label_,
                    "start_char": ent.start_char,
                    "end_char": ent.end_char,
                }
            )

        return ner_text, results, tables, structure

    # Fallback to spaCyLayout for non-DOCX files (PDF, etc.)
    tables = []

    def capture_table(df):
        """Callback for spaCyLayout: captures table data and returns a placeholder."""
        table_idx = len(tables)
        tables.append(
            {
                "id": table_idx,
                "html": df.to_html(index=False, border=1),
                "text": df.to_csv(index=False, sep="\t"),
            }
        )
        return f"{{{{TABLE:{table_idx}}}}}"

    layout = spaCyLayout(nlp, display_table=capture_table)
    doc = layout(path)

    text = doc.text if doc.text else ""

    # Normalize whitespace on placeholder text first
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Replace placeholders with table text, tracking positions
    ner_text = text
    for table in tables:
        placeholder = f"{{{{TABLE:{table['id']}}}}}"
        pos = ner_text.find(placeholder)
        if pos >= 0:
            table_text = table["text"]
            table["ner_start"] = pos
            table["ner_end"] = pos + len(table_text)
            ner_text = ner_text[:pos] + table_text + ner_text[pos + len(placeholder) :]

    if not ner_text.strip():
        raise ValueError("No text found in the document.")

    ner_doc = nlp(ner_text)

    results = []
    for ent in ner_doc.ents:
        results.append(
            {
                "text": ent.text,
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
            }
        )

    # For non-DOCX files, structure is None (fallback to plain text rendering)
    return ner_text, results, tables, None
