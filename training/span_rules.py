"""
Span rules: format-specific adjustments to detector output.

A span rule runs inside ``ExtractionPipeline.run`` on every detector's output
*before* priority deduplication (see ADR-0001).  It may drop detector spans
and add spans of its own, which outrank every detector.

The one rule today handles **role-dependent fields**: fields of a record that
are disclosable to the data subject only when they hold a particular role on
that record.  The rule logic is generic; what makes it about occurrence
reports is the declarative rule data in ``OCCURRENCE_REPORT``.  A second
record format adds its own rule data, not code.

Every uncertain reading of the role resolves toward redaction: the field is
withheld as third-party information unless the data subject is confirmed to
hold the role.
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from cases.identity import IdentityMatch, match_person, parse_dob

from .pipeline import SpanRuleResult, ranges_overlap

# The entity type of a span this rule adds.  Deliberately outside the
# attribution whitelist in ``cases.attribution``, so DS resolution never
# reattributes a withheld field to the data subject.
ROLE_DEPENDENT_FIELD_ENTITY_TYPE = "ROLE_DEPENDENT_FIELD"


@dataclass(frozen=True)
class RoleDependentFieldRuleData:
    """
    The wording that identifies one record format's role-dependent fields.

    ``persons_heading`` starts the section listing the record's people, one
    per line.  The document holding exactly one such section is what makes
    it a record of this format.  ``role`` is the role that makes the fields
    disclosable, as the person lines print it.  ``field_labels`` are the
    labels that start each role-dependent field.
    """

    persons_heading: str
    role: str
    field_labels: tuple


OCCURRENCE_REPORT = RoleDependentFieldRuleData(
    persons_heading="Involved persons:",
    role="Person reporting",
    field_labels=("Reported time:", "Summary:", "Original Incident Report:"),
)


class RoleReading(Enum):
    """What the document says about the data subject's role on the record."""

    HOLDS_ROLE = "HOLDS_ROLE"
    OTHER_ROLE = "OTHER_ROLE"
    UNKNOWN = "UNKNOWN"


# A line that starts with a label: up to four words, the first capitalised,
# then a colon followed by whitespace or the end of the line.  So a wrapped
# value line such as "advised as follows: the matter..." is not a label, nor
# is a time ("10:00").  Commas, slashes and brackets are excluded so a person
# line such as "BLOGGS, Joe [A1B] / Person reporting / DOB: ..." is not
# either.
_LABEL_WORD = r"[A-Za-z0-9()'&.-]"
_LABEL_LINE_RE = re.compile(
    rf"[ \t]*[A-Z]{_LABEL_WORD}*(?:[ \t]+{_LABEL_WORD}+){{0,3}}:(?=\s|$)"
)

# Separates a person line's name from its roles and details.  Whitespace on
# both sides, so the slashes inside a date of birth do not split it.
_PERSON_PART_SEPARATOR_RE = re.compile(r"\s+/\s+")
_BRACKETED_CODE_RE = re.compile(r"\[[^\]]*\]")
# A date of birth runs to the next part separator or the end of the line, so
# a long-form date ("DOB: 2 January 1960") is read whole.
_DOB_RE = re.compile(r"\bDOB:[ \t]*(.*?)(?=\s+/\s+|$)", re.IGNORECASE)
# The longest date format a date of birth is printed in, in words.
_DOB_MAX_WORDS = 3


def _lines(text):
    """Yield ``(start, end)`` for each line of *text*, newline excluded."""
    start = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        yield start, start + len(content)
        start += len(line)


def _is_blank(text, start, end):
    """Whether the line [start, end) of *text* holds only whitespace."""
    return not text[start:end].strip()


def _is_label_line(text, start, end):
    """Whether the line [start, end) of *text* starts a new labelled field."""
    return _LABEL_LINE_RE.match(text, start, end) is not None


def _label_start(text, start, end, label):
    """Where *label* starts on the line [start, end), or None."""
    indent = len(text[start:end]) - len(text[start:end].lstrip(" \t"))
    label_start = start + indent
    candidate = text[label_start : label_start + len(label)]
    if candidate.casefold() == label.casefold():
        return label_start
    return None


@dataclass(frozen=True)
class _LabelledBlock:
    """
    A label at the start of a line and the value that follows it.

    ``start`` is where the label starts, ``label_end`` where it ends,
    ``value_start`` where the value's first non-blank character is, and
    ``end`` where the value ends, trailing whitespace excluded.  A
    role-dependent field is one; so is a persons section, whose value is its
    person lines.
    """

    start: int
    label_end: int
    value_start: int
    end: int

    @classmethod
    def of(cls, text, start, label_end, end):
        """The block of *text* in [start, end), its label ending at *label_end*."""
        end = start + len(text[start:end].rstrip())
        value = text[label_end:end]
        value_start = label_end + len(value) - len(value.lstrip())
        return cls(start, label_end, value_start, end)

    def overlaps(self, span):
        """Whether *span* shares a character with the block."""
        return ranges_overlap(
            span["start_char"], span["end_char"], self.start, self.end
        )

    def redacts_whole(self, span):
        """
        Whether *span* overlaps the block and either reaches into its label
        or covers its whole value.
        """
        if not self.overlaps(span):
            return False
        span_start, span_end = span["start_char"], span["end_char"]
        touches_label = span_start < self.label_end
        covers_value = span_start <= self.value_start and span_end >= self.end
        return touches_label or covers_value

    def crosses_edge(self, span):
        """Whether *span* lies partly inside the block and partly outside."""
        return self.overlaps(span) and (
            span["start_char"] < self.start or span["end_char"] > self.end
        )


def _labelled_blocks(text, label):
    """
    Every block that *label* starts in *text*.

    A block starts at its label at the beginning of a line and runs to just
    before the next line that starts with a label (see ``_LABEL_LINE_RE``),
    or a blank line, so a value that wraps onto following lines is included.
    A label that appears mid-line is part of the value.
    """
    lines = list(_lines(text))
    blocks = []
    for i, (start, end) in enumerate(lines):
        label_start = _label_start(text, start, end, label)
        if label_start is None:
            continue
        block_end = end
        for next_start, next_end in lines[i + 1 :]:
            if _is_blank(text, next_start, next_end) or _is_label_line(
                text, next_start, next_end
            ):
                break
            block_end = next_end
        blocks.append(
            _LabelledBlock.of(
                text, label_start, label_start + len(label), block_end
            )
        )
    return blocks


def _read_dob(line):
    """
    The date of birth a person line gives, as ``(present, dob)``.

    ``present`` is whether the line has a ``DOB:`` detail at all; ``dob`` is
    its date, or None when it cannot be read.  The date may be followed by
    other words in the same part ("02/01/1990 (aged 36)"), so the longest
    leading run of words that reads as a date wins.
    """
    match = _DOB_RE.search(line)
    if not match:
        return False, None
    words = match.group(1).split()
    for count in range(min(len(words), _DOB_MAX_WORDS), 0, -1):
        dob = parse_dob(" ".join(words[:count]))
        if dob is not None:
            return True, dob
    return True, None


def _trimmed(text, span, start, end):
    """
    A copy of *span* cut to [start, end) with surrounding whitespace dropped,
    or None if nothing but whitespace is left.
    """
    piece = text[start:end]
    if not piece.strip():
        return None
    start += len(piece) - len(piece.lstrip())
    end = start + len(piece.strip())
    return {
        **span,
        "text": text[start:end],
        "start_char": start,
        "end_char": end,
    }


def _outside_fields(text, span, fields):
    """
    *span* trimmed to its parts outside every field whose edge it crosses:
    one piece for each side that reaches outside.  A span that crosses no
    field edge comes back unchanged.
    """
    crossed = sorted(
        (field for field in fields if field.crosses_edge(span)),
        key=lambda field: field.start,
    )
    if not crossed:
        return [span]
    pieces = []
    cursor = span["start_char"]
    for field in crossed:
        pieces.append(_trimmed(text, span, cursor, field.start))
        cursor = max(cursor, field.end)
    pieces.append(_trimmed(text, span, cursor, span["end_char"]))
    return [piece for piece in pieces if piece is not None]


@dataclass(frozen=True)
class _PersonLine:
    """
    One entry in a persons section: the person's name, their roles
    (casefolded), and their date of birth.  ``dob_unreadable`` marks a line
    that gives a date of birth the parser cannot read.
    """

    name: str
    roles: frozenset
    dob: date | None
    dob_unreadable: bool = False


def _parse_person_line(line):
    """
    Read one person line: a name, optional bracketed codes, then
    slash-separated roles and details.  A part containing a colon
    ("DOB: ...") is a detail, not a role.  One part may combine several
    roles with semicolons ("Person reporting; Victim").
    """
    parts = _PERSON_PART_SEPARATOR_RE.split(line.strip())
    name = _BRACKETED_CODE_RE.sub(" ", parts[0]).strip()
    roles = frozenset(
        role.strip().casefold()
        for part in parts[1:]
        if ":" not in part
        for role in part.split(";")
        if role.strip()
    )
    has_dob, dob = _read_dob(line)
    return _PersonLine(
        name=name,
        roles=roles,
        dob=dob,
        dob_unreadable=has_dob and dob is None,
    )


@dataclass(frozen=True)
class RoleDependentFieldRule:
    """
    Disclose a record's role-dependent fields when the data subject is
    confirmed to hold the role that makes them disclosable, and withhold
    them as third-party information otherwise.
    """

    rule_data: RoleDependentFieldRuleData
    data_subject_name: str | None = None
    data_subject_dob: date | None = None

    def apply(self, text, stage_results):
        """
        Adjust every detector's spans for the document's role-dependent
        fields, and add a withheld-field span for each unless the data
        subject is confirmed to hold the role.
        """
        sections = _labelled_blocks(text, self.rule_data.persons_heading)
        if not sections:
            # Not a record of this format: leave every detector span alone.
            return SpanRuleResult(stage_results=stage_results)

        if len(sections) > 1:
            # More than one record in the document: one record's role must
            # never decide another's fields.
            reading = RoleReading.UNKNOWN
        else:
            reading = self._read_role(text, sections[0])

        fields = self._fields(text)
        # Whichever way the fields go, a span crossing a field's edge keeps
        # only its part outside the field, so the field's decision never
        # spills onto the text around it.
        stage_results = [
            [
                piece
                for span in results
                for piece in _outside_fields(text, span, fields)
            ]
            for results in stage_results
        ]

        if reading is RoleReading.HOLDS_ROLE:
            return SpanRuleResult(
                stage_results=self._disclose_fields(fields, stage_results)
            )

        return SpanRuleResult(
            stage_results=stage_results,
            added=[_withheld_span(text, field) for field in fields],
        )

    def _fields(self, text):
        """Every role-dependent field in *text*, for every field label."""
        return [
            field
            for label in self.rule_data.field_labels
            for field in _labelled_blocks(text, label)
        ]

    def _read_role(self, text, section):
        """
        The data subject's role, read from their own line in the persons
        *section*.  Only a line the identity matcher confirms unambiguously
        counts as theirs.  A line whose date of birth cannot be read is never
        theirs on the name alone: if the name matches at all, the reading is
        unknown.
        """
        person_lines = [
            line
            for line in text[section.label_end : section.end].splitlines()
            if line.strip()
        ]
        role = self.rule_data.role.casefold()

        # In line order, so the outcome never depends on set ordering.
        readings = []
        for person in map(_parse_person_line, person_lines):
            verdict = match_person(
                person.name,
                person.dob,
                ds_name=self.data_subject_name,
                ds_dob=self.data_subject_dob,
            )
            if person.dob_unreadable:
                # The date of birth could have confirmed or refuted the name,
                # so a name match alone never makes this line theirs.
                if verdict is not IdentityMatch.NO_MATCH:
                    readings.append(RoleReading.UNKNOWN)
                continue
            if verdict is not IdentityMatch.MATCH:
                continue
            if not person.roles:
                readings.append(RoleReading.UNKNOWN)
            elif role in person.roles:
                readings.append(RoleReading.HOLDS_ROLE)
            else:
                readings.append(RoleReading.OTHER_ROLE)

        if len(set(readings)) == 1:
            return readings[0]
        # No line matched, or the matching lines disagree.
        return RoleReading.UNKNOWN

    @staticmethod
    def _disclose_fields(fields, stage_results):
        """
        Drop, from every detector, each span that would redact a field as a
        whole: one that overlaps the field and either reaches into its label
        or covers its whole value.  Spans strictly inside the value, such as
        a third party named in a summary, are kept.  Nothing records the
        drop (an accepted exception to "no silent discard"; see ADR-0001).
        """
        return [
            [
                span
                for span in results
                if not any(field.redacts_whole(span) for field in fields)
            ]
            for results in stage_results
        ]


def _withheld_span(text, field):
    """The third-party span that withholds *field*, label and value."""
    return {
        "text": text[field.start : field.end],
        "label": "THIRD_PARTY",
        "start_char": field.start,
        "end_char": field.end,
        "entity_type": ROLE_DEPENDENT_FIELD_ENTITY_TYPE,
    }


def build_occurrence_report_rule(
    data_subject_name=None, data_subject_dob=None
):
    """The occurrence-report rule for one case's data subject."""
    return RoleDependentFieldRule(
        rule_data=OCCURRENCE_REPORT,
        data_subject_name=data_subject_name,
        data_subject_dob=data_subject_dob,
    )
