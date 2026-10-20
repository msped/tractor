"""
Block structure of an extracted document.

A *block* is a run of text that reads as one unit about one subject: a
paragraph, a heading, a single row of a table, or — when the document has no
structure to read — a line.  Blocks are what make it possible to say whose
detail a phone number is: a number in the same row as "BLOGGS, Joe" is Joe's,
while the same number three paragraphs away is nobody's in particular.

Pure offset arithmetic over the structure already captured at extraction time:
no ORM, no document parsing, no I/O.  Offsets are absolute positions in the
NER text, the same coordinates every extractor reports spans in.

A table is deliberately split into one block *per row* rather than one block
per table.  A record layout puts a person in one cell and their details in
sibling cells of the same row, so the row is the unit that groups them; a
whole-table block would merge every person in the table into one undecidable
group.
"""

from dataclasses import dataclass


class BlockKind:
    """Where a block came from.  Carried for diagnostics, not for decisions."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE_ROW = "table_row"
    # One line of a document with no element structure (pasted text, PDF).
    LINE = "line"


@dataclass(frozen=True)
class Block:
    """A half-open range [start, end) of the NER text that reads as one unit."""

    start: int
    end: int
    kind: str

    def contains(self, span_start, span_end):
        """
        True when [span_start, span_end) lies wholly inside this block.

        Containment is total on purpose.  A span overlapping two blocks belongs
        to neither: it has no single subject, and guessing one would attribute a
        detail to a person it may not describe.
        """
        return span_start >= self.start and span_end <= self.end


def _table_row_blocks(table):
    """One block per row of *table*, from its cells' absolute offsets."""
    rows = {}
    for cell in table.get("cells") or []:
        # A merged continuation occupies no text — its start and end are both
        # the cursor position — so it would drag a row's range to the left.
        if cell.get("isMergedContinuation"):
            continue
        start, end = cell.get("start"), cell.get("end")
        if start is None or end is None:
            continue
        row = cell.get("row")
        if row in rows:
            low, high = rows[row]
            rows[row] = (min(low, start), max(high, end))
        else:
            rows[row] = (start, end)

    return [
        Block(start=start, end=end, kind=BlockKind.TABLE_ROW)
        for _, (start, end) in sorted(rows.items())
        if end > start
    ]


def _line_blocks(extracted_text):
    """
    One block per non-blank line, for a document with no element structure.

    The line is the unit because this path carries pasted text, and a record
    copied out of a source system arrives one record per line — a name and its
    details separated by tabs or runs of spaces, which is the same shape as a
    table row.  Grouping by blank line instead would put a whole report in one
    block, and a block holding many people attributes nothing.

    Lines adapt to how the text was wrapped: a soft-wrapped prose paragraph is
    one long line and therefore one block, while hard-wrapped prose fragments
    into several.  Fragmenting only ever loses attributions, never invents
    them, so the failure is toward redaction.

    Sentences are deliberately *not* the unit.  Splitting on terminal
    punctuation would cut this content in the wrong places — initials and
    honorifics put full stops mid-record ("HUGHES, R. #0723222", "Mr. Smith"),
    so a record would fragment away from its own identifier — while record
    lines carry no terminal punctuation at all, so sentence splitting would buy
    nothing exactly where attribution matters most.
    """
    if not extracted_text or not extracted_text.strip():
        return []

    blocks = []
    pos = 0
    for line in extracted_text.split("\n"):
        start, end = pos, pos + len(line)
        pos = end + 1  # the "\n" the split consumed

        if not line.strip():
            continue
        # Trim to the text itself so surrounding whitespace — the tab-padding
        # a pasted record is full of — is not claimed by a block.
        start += len(line) - len(line.lstrip())
        end -= len(line) - len(line.rstrip())
        blocks.append(Block(start=start, end=end, kind=BlockKind.LINE))
    return blocks


def build_blocks(extracted_text, structure=None, tables=None):
    """
    Blocks for a document, in document order.

    *structure* is ``Document.extracted_structure`` (the element list) and
    *tables* is ``Document.extracted_tables``.  When *structure* is None —
    pasted text and PDFs, which have no element list — blocks come from the
    lines of the text instead.

    The unstructured path is not a rare fallback: text pasted into the document
    dialog is stored as a ``.txt`` file, so it is the path most documents take
    when a team pastes records in rather than uploading files.  It is weaker
    than the DOCX path in one specific way — a table loses its cell boundaries
    and arrives as flat text — but a pasted record keeps its one-record-per-line
    shape, which is the shape attribution needs.
    """
    if structure is None:
        return _line_blocks(extracted_text)

    tables_by_id = {
        table.get("id"): table for table in (tables or []) if "id" in table
    }

    blocks = []
    for element in structure:
        kind = element.get("type")

        if kind == "table":
            table = tables_by_id.get(element.get("table_id"))
            row_blocks = _table_row_blocks(table) if table else []
            if row_blocks:
                blocks.extend(row_blocks)
                continue
            # No cell offsets to work from — fall back to the table as one
            # block. Attribution then finds several people in it and resolves
            # nothing, which is the correct outcome for an unreadable table.
            kind = BlockKind.TABLE_ROW

        start, end = element.get("start"), element.get("end")
        if start is None or end is None or end <= start:
            continue
        blocks.append(Block(start=start, end=end, kind=kind))

    return blocks


def block_for_span(blocks, span_start, span_end):
    """
    The block wholly containing [span_start, span_end), or None.

    None covers both a span outside every block and a span straddling two.
    """
    for block in blocks:
        if block.contains(span_start, span_end):
            return block
    return None
