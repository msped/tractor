"""
Internal Review lifecycle service.

A review is a tracked post-disclosure re-review episode: it unlocks a disclosed
case's redaction decisions (via the provenance lock) for the duration of the
review. This slice provides opening; closure (complete/abandon) is added later.
"""

from django.db import transaction

from .models import Case, InternalReview


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
