"""
Internal Review lifecycle service.

A review is a tracked post-disclosure re-review episode: it unlocks a disclosed
case's redaction decisions (via the provenance lock) for the duration of the
review. A review is opened, then closed exactly once — either **completed**
(re-export the amended disclosure) or **abandoned** (roll the redactions back so
the original disclosure stands). Both closures require a written outcome and
re-lock the case.
"""

from django.db import transaction
from django.utils import timezone

from .models import Case, InternalReview
from .snapshots import restore_redactions


class ReviewError(Exception):
    """A review lifecycle precondition was violated."""


@transaction.atomic
def open_review(case, by):
    """
    Open an Internal Review on a disclosed case.

    Precondition: the case has at least one completed disclosure ``Export``.
    Opening moves the case to ``UNDER_REVIEW`` while its documents stay
    ``COMPLETED`` and editable in place. Only one review may be open per case
    at a time — calling this while a review is already open returns the
    existing one (idempotent open) rather than creating a second.
    """
    if not case.exports.exists():
        raise ReviewError(
            "A review can only be opened on a case that has been disclosed."
        )

    existing = case.reviews.filter(status=InternalReview.Status.OPEN).first()
    if existing is not None:
        return existing

    review = InternalReview.objects.create(case=case, opened_by=by)
    # Documents remain COMPLETED and editable; only the case status moves.
    Case.objects.filter(pk=case.pk).update(status=Case.Status.UNDER_REVIEW)
    case.status = Case.Status.UNDER_REVIEW
    return review


def _clean_outcome(outcome):
    """A written outcome is mandatory on every review closure."""
    outcome = (outcome or "").strip()
    if not outcome:
        raise ReviewError("A written outcome is required to close a review.")
    return outcome


def _require_open(review):
    if review.status != InternalReview.Status.OPEN:
        raise ReviewError("Only an open review can be closed.")


def _relock(case, closed_review, *, status, outcome, by):
    """
    Record the closure on ``closed_review`` and return the case to a
    disclosed/locked state. With no open review left, the provenance lock
    re-engages automatically for any case that has been disclosed.
    """
    closed_review.status = status
    closed_review.outcome = outcome
    closed_review.closed_by = by
    closed_review.closed_at = timezone.now()
    closed_review.save(
        update_fields=["status", "outcome", "closed_by", "closed_at"]
    )
    Case.objects.filter(pk=case.pk).update(status=Case.Status.COMPLETED)
    case.status = Case.Status.COMPLETED


@transaction.atomic
def complete_review(review, outcome, by):
    """
    Complete an open review.

    Records the required ``outcome``, re-locks the case, and triggers a
    re-export that regenerates the full disclosure package for the case's
    current state — creating a new ``Export`` + ``RedactionSnapshot`` attributed
    to this review. The re-export is driven by completion here, not by the
    ordinary "all documents COMPLETED" export gate.
    """
    outcome = _clean_outcome(outcome)
    _require_open(review)

    case = review.case
    _relock(
        case,
        review,
        status=InternalReview.Status.COMPLETED,
        outcome=outcome,
        by=by,
    )

    # Attribute the regenerated package to this review.
    case.start_export(review=review)
    return review


@transaction.atomic
def abandon_review(review, outcome, by):
    """
    Abandon an open review.

    Records the required ``outcome``, restores the live redaction set from the
    latest snapshot so any edits made during the review are discarded and the
    original disclosure stands, and re-locks the case. No new export is
    produced.
    """
    outcome = _clean_outcome(outcome)
    _require_open(review)

    case = review.case
    snapshot = case.redaction_snapshots.order_by("-created_at", "-id").first()
    if snapshot is not None:
        restore_redactions(case, snapshot)

    _relock(
        case,
        review,
        status=InternalReview.Status.ABANDONED,
        outcome=outcome,
        by=by,
    )
    return review
