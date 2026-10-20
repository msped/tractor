from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Document, InternalReview, Redaction


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    """
    When a document is first created, trigger the AI processing task.
    """
    if created and instance.status == Document.Status.PROCESSING:
        instance.start_processing()


@receiver(pre_save, sender=Redaction)
def redaction_pre_save(sender, instance, **kwargs):
    """
    Store the pre-save decision state so post_save can tell what just changed.

    The type alone is not enough: propagation now keys off a human acceptance
    landing on a DS_INFO row, which can happen without the type changing at
    all (a reviewer confirming a suggestion the system proposed).
    """
    original = None
    if instance.pk:
        original = Redaction.objects.filter(pk=instance.pk).first()

    instance._original_redaction_type = (
        original.redaction_type if original else None
    )
    instance._original_is_accepted = (
        original.is_accepted if original else False
    )
    instance._original_decided_by = original.decided_by if original else None


def _is_human_accepted(redaction_type, is_accepted, decided_by):
    """A DS_INFO row carrying a human's acceptance."""
    return (
        redaction_type == Redaction.RedactionType.DS_INFORMATION
        and is_accepted
        and decided_by == Redaction.DecidedBy.HUMAN
    )


@receiver(post_save, sender=Redaction)
def redaction_post_save(sender, instance, created, **kwargs):
    """
    When a human accepts a redaction as DS_INFO, trigger a task to find that
    same text in all other documents in the case.

    Propagation is a *human decision spreading*, so it waits for one.  The
    trigger is a human acceptance newly landing on a DS_INFO row, however it
    arrived: with the row (a manual highlight), with a type change
    (change-type-and-accept), or on a suggestion the system proposed and a
    reviewer has now confirmed.

    Two things this deliberately does not fire for:

    * A DS_INFO row the *system* produced — whether proposed pending by span
      resolution or accepted under ``DS_RECORD_MATCH``.  Broadcasting an
      unconfirmed inference case-wide is exactly what must not happen, and
      every document runs its own resolution pass during its own processing,
      with ``_apply_case_ds_info_to_document`` pulling in the case's already
      accepted terms.  Nothing is lost by waiting.
    * A human *rejection*, which is a decision not to treat the text as the
      data subject's and must not spread as though it were.
    """
    if not _is_human_accepted(
        instance.redaction_type, instance.is_accepted, instance.decided_by
    ):
        return

    # Only fire when the acceptance is new. Re-saving a row that was already
    # human-accepted DS_INFO changed nothing worth broadcasting again.
    if not created and _is_human_accepted(
        getattr(instance, "_original_redaction_type", None),
        getattr(instance, "_original_is_accepted", False),
        getattr(instance, "_original_decided_by", None),
    ):
        return

    # During an Internal Review, propagation is no longer fire-and-forget: the
    # reviewer previews the affected documents and confirms before it applies
    # (see cases.views.RedactionPropagationView). Suppress the automatic task
    # so no case-wide write happens without that confirmation.
    review_open = InternalReview.objects.filter(
        case=instance.document.case_id,
        status=InternalReview.Status.OPEN,
    ).exists()
    if review_open:
        return

    from django_q.tasks import async_task

    async_task(
        "cases.tasks.find_and_flag_matching_text_in_case",
        instance.id,
    )
