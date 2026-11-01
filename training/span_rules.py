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
from datetime import date, datetime
from enum import Enum

from cases.identity import IdentityMatch, match_person

from .pipeline import SpanRuleResult

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


# A line that starts with a label: words followed by a colon.  Commas,
# slashes and brackets are excluded so a person line such as
# "BLOGGS, Joe [A1B] / Person reporting / DOB: ..." is not read as a label.
_LABEL_LINE_RE = re.compile(r"[ \t]*[A-Za-z][A-Za-z0-9 ()'&.-]*:")

# Separates a person line's name from its roles and details.  Whitespace on
# both sides, so the slashes inside a date of birth do not split it.
_PERSON_PART_SEPARATOR_RE = re.compile(r"\s+/\s+")
_BRACKETED_CODE_RE = re.compile(r"\[[^\]]*\]")
_DOB_RE = re.compile(r"\bDOB:\s*(\S+)", re.IGNORECASE)
_DOB_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d")


def _lines(text):
    """Yield ``(start, end)`` for each line of *text*, newline excluded."""
    start = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        yield start, start + len(content)
        start += len(line)


def _is_blank(text, start, end):
    return not text[start:end].strip()


def _is_label_line(text, start, end):
    return _LABEL_LINE_RE.match(text, start, end) is not None


def _label_start(text, start, end, label):
    """Where *label* starts on the line [start, end), or None."""
    indent = len(text[start:end]) - len(text[start:end].lstrip(" \t"))
    label_start = start + indent
    candidate = text[label_start : label_start + len(label)]
    if candidate.casefold() == label.casefold():
        return label_start
    return None


def _field_extents(text, label):
    """
    Every ``(start, end)`` field that *label* starts in *text*.

    A field starts at its label at the beginning of a line and runs to just
    before the next line that starts with a label, or a blank line.  A label
    that appears mid-line is part of the value.
    """
    lines = list(_lines(text))
    extents = []
    for i, (start, end) in enumerate(lines):
        label_start = _label_start(text, start, end, label)
        if label_start is None:
            continue
        field_end = end
        for next_start, next_end in lines[i + 1 :]:
            if _is_blank(text, next_start, next_end) or _is_label_line(
                text, next_start, next_end
            ):
                break
            field_end = next_end
        value = text[label_start:field_end].rstrip()
        extents.append((label_start, label_start + len(value)))
    return extents


def _parse_dob(line):
    match = _DOB_RE.search(line)
    if not match:
        return None
    for fmt in _DOB_FORMATS:
        try:
            return datetime.strptime(match.group(1), fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class _PersonLine:
    name: str
    roles: frozenset
    dob: date | None


def _parse_person_line(line):
    """
    Read one person line: a name, optional bracketed codes, then
    slash-separated roles and details.  A part containing a colon
    ("DOB: ...") is a detail, not a role.
    """
    parts = _PERSON_PART_SEPARATOR_RE.split(line.strip())
    name = _BRACKETED_CODE_RE.sub(" ", parts[0]).strip()
    roles = frozenset(
        part.strip().casefold() for part in parts[1:] if ":" not in part
    )
    return _PersonLine(name=name, roles=roles, dob=_parse_dob(line))


@dataclass(frozen=True)
class RoleDependentFieldRule:
    """
    Withhold a record's role-dependent fields unless the data subject is
    confirmed to hold the role that makes them disclosable.
    """

    rule_data: RoleDependentFieldRuleData
    data_subject_name: str | None = None
    data_subject_dob: date | None = None

    def apply(self, text, stage_results):
        sections = _field_extents(text, self.rule_data.persons_heading)
        if not sections:
            # Not a record of this format: leave every detector span alone.
            return SpanRuleResult(stage_results=stage_results)

        if len(sections) > 1:
            # More than one record in the document: one record's role must
            # never decide another's fields.
            reading = RoleReading.UNKNOWN
        else:
            reading = self._read_role(text, *sections[0])

        if reading is RoleReading.HOLDS_ROLE:
            # Disclosing the fields is a separate change; until then they are
            # left as the detectors found them.
            return SpanRuleResult(stage_results=stage_results)

        return SpanRuleResult(
            stage_results=stage_results,
            added=[
                self._withheld_span(text, start, end)
                for label in self.rule_data.field_labels
                for start, end in _field_extents(text, label)
            ],
        )

    def _read_role(self, text, section_start, section_end):
        """
        The data subject's role, read from their own line in the persons
        section.  Only a line the identity matcher confirms unambiguously
        counts as theirs.
        """
        heading_end = section_start + len(self.rule_data.persons_heading)
        person_lines = [
            line
            for line in text[heading_end:section_end].splitlines()
            if line.strip()
        ]
        role = self.rule_data.role.casefold()

        readings = set()
        for person in map(_parse_person_line, person_lines):
            verdict = match_person(
                person.name,
                person.dob,
                ds_name=self.data_subject_name,
                ds_dob=self.data_subject_dob,
            )
            if verdict is not IdentityMatch.MATCH:
                continue
            if not person.roles:
                readings.add(RoleReading.UNKNOWN)
            elif role in person.roles:
                readings.add(RoleReading.HOLDS_ROLE)
            else:
                readings.add(RoleReading.OTHER_ROLE)

        if len(readings) == 1:
            return readings.pop()
        # No line matched, or the matching lines disagree.
        return RoleReading.UNKNOWN

    @staticmethod
    def _withheld_span(text, start, end):
        return {
            "text": text[start:end],
            "label": "THIRD_PARTY",
            "start_char": start,
            "end_char": end,
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
