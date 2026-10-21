"""
Data subject identity matching.

Answers one question: is this candidate person the case's data subject — yes,
no, or can't tell?  Pure logic: no ORM, no document, no I/O, so the rule that
protects a third party who shares a surname with the data subject can be
tested directly.

"Can't tell" is a first-class answer.  Callers must resolve it toward
redaction, never toward disclosure — an uncertain identity that is treated as
the data subject discloses someone else's details.
"""

import re
from enum import Enum

# Date formats a document might print the data subject's date of birth in.
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

# Dropped before comparison so "Mr John Doe" still matches "John Doe".  Only
# ever dropped when at least one other token survives, since any of these can
# also be a surname.
_HONORIFICS = frozenset(
    {"mr", "mrs", "ms", "mx", "miss", "dr", "prof", "sir", "dame", "rev"}
)


class IdentityMatch(Enum):
    """Whether a candidate person is the data subject."""

    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


def name_tokens(name):
    """
    Reduce a name to the set of word tokens used for comparison.

    Lowercased, apostrophes dropped and every other non-alphanumeric treated as
    a separator, so "O'BRIEN, John-Paul" and "john paul obrien" reduce alike.
    Comparison is order-free, which is what makes "Surname, Forename" and
    "Forename Surname" equal.  Single characters are dropped, so a bare initial
    is never evidence of identity on its own.
    """
    if not name:
        return frozenset()

    cleaned = re.sub(r"['’]", "", name.casefold())
    tokens = {t for t in re.split(r"[^a-z0-9]+", cleaned) if len(t) > 1}

    meaningful = tokens - _HONORIFICS
    return frozenset(meaningful or tokens)


def _match_name(name, ds_name):
    """Compare two names by token set, three ways."""
    candidate = name_tokens(name)
    subject = name_tokens(ds_name)

    if not candidate or not subject:
        return IdentityMatch.NO_MATCH
    if candidate == subject:
        return IdentityMatch.MATCH
    if candidate & subject:
        # One name is part of the other, or they share only some tokens.  Both
        # are uncertain: a bare "Bloggs" may be a relative rather than the data
        # subject "Joe Bloggs", and a span covering "Joe Bloggs and Jane Smith"
        # covers a third party as well as the data subject.
        return IdentityMatch.AMBIGUOUS
    return IdentityMatch.NO_MATCH


def match_person(name, dob=None, *, ds_name, ds_dob=None):
    """
    Decide whether a candidate person is the case's data subject.

    *name* is the name as the document writes it; *dob* is a date the document
    supplies for that same person, where one is available.  *ds_name* and
    *ds_dob* come from the case record.

    A date of birth only ever corroborates or refutes — it resolves an
    uncertain name match, and it overrides a confident one.  Two people with
    similar names and different dates of birth are different people, which is
    the whole point of checking it.  A date of birth alone never establishes
    identity: if the names do not overlap at all, agreeing dates are a
    coincidence between two different people.
    """
    verdict = _match_name(name, ds_name)

    if dob is None or ds_dob is None:
        return verdict

    if dob != ds_dob:
        return IdentityMatch.NO_MATCH

    if verdict is IdentityMatch.AMBIGUOUS:
        return IdentityMatch.MATCH
    return verdict


def matches_dob_text(text, ds_dob):
    """
    True if *text* is the data subject's date of birth written out.

    Covers a span that is the date itself rather than a person, in any of the
    formats a source system might print.
    """
    if not ds_dob or not text or not text.strip():
        return False

    candidate = text.strip().casefold()
    for fmt in _DOB_FORMATS:
        try:
            formatted = ds_dob.strftime(fmt)
        except ValueError:
            continue
        if candidate == formatted.casefold():
            return True
    return False


# A word as it sits in a document.  Apostrophes are kept inside the token so
# "O'Brien" is one word, matching how name_tokens reduces it.
_WORD_RE = re.compile(r"[A-Za-z0-9'’]+")

# A character that continues a word.  A run butting against one is part of a
# longer name — "Hughes" inside "Hughes-Smith" is not the data subject.
_CONTINUATION_RE = re.compile(r"[-'’\w]")


def _normalise(raw):
    """Reduce one document word the same way :func:`name_tokens` would."""
    return re.sub(r"['’]", "", raw.casefold())


def _is_free_standing(text, start, end):
    """Whether [start, end) is bounded by something other than more word."""
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not (
        _CONTINUATION_RE.match(before) or _CONTINUATION_RE.match(after)
    )


def _name_occurrences(text, ds_name):
    """
    Every run of whole words in *text* whose tokens are exactly the data
    subject's.

    Set equality, not containment, and for the same reason ``_match_name``
    draws the line there: a run that merely shares tokens is the
    ``AMBIGUOUS`` case, and these occurrences are disclosed rather than
    withheld, so resolving an uncertain one toward the data subject would put
    a third party's name into the clear.  Order-free, so "HUGHES, GRACE" is
    found from a record reading "Grace Hughes".
    """
    subject = name_tokens(ds_name)
    if not subject:
        return []

    words = [
        (m.start(), m.end(), _normalise(m.group(0)))
        for m in _WORD_RE.finditer(text)
    ]
    words = [w for w in words if len(w[2]) > 1]

    occurrences = []
    i = 0
    while i < len(words):
        seen = set()
        end_index = None
        for j in range(i, len(words)):
            token = words[j][2]
            if token not in subject:
                break
            seen.add(token)
            if seen == subject:
                end_index = j
                break

        if end_index is not None:
            start, end = words[i][0], words[end_index][1]
            if _is_free_standing(text, start, end):
                occurrences.append((start, end))
                i = end_index + 1
                continue
        i += 1

    return occurrences


def _dob_occurrences(text, ds_dob):
    """Every printing of the data subject's date of birth in *text*."""
    if not ds_dob:
        return []

    occurrences = []
    for fmt in _DOB_FORMATS:
        try:
            rendered = ds_dob.strftime(fmt)
        except ValueError:
            continue
        if not rendered:
            continue
        for match in re.finditer(re.escape(rendered), text, re.IGNORECASE):
            if _is_free_standing(text, match.start(), match.end()):
                occurrences.append((match.start(), match.end()))
    return occurrences


def find_identity_occurrences(text, *, ds_name=None, ds_dob=None):
    """
    Locate the data subject's own name and date of birth within *text*.

    Where :func:`match_person` judges a span someone else chose, this finds
    the data subject inside text nobody has split up yet — the case of a
    detector claiming a whole sentence, with the data subject's name sitting
    somewhere in the middle of it.

    Returns merged, sorted ``(start, end)`` ranges.
    """
    if not text:
        return []

    found = _name_occurrences(text, ds_name) + _dob_occurrences(text, ds_dob)

    merged = []
    for start, end in sorted(found):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]
