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
