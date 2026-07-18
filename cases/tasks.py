"""
Async task entry points for the cases app.

All django-q2 async_task() calls should reference this module so that
service functions can be renamed/moved without touching task routing strings.
"""

import logging

logger = logging.getLogger(__name__)


def process_document_and_create_redactions(document_id):
    from .models import Document
    from .services import process_document_and_create_redactions as _impl

    try:
        return _impl(document_id)
    except Exception:
        logger.exception(
            "Unhandled exception processing document %s — marking ERROR",
            document_id,
        )
        Document.objects.filter(pk=document_id).update(
            status=Document.Status.ERROR
        )
        raise


def find_and_flag_matching_text_in_case(redaction_id):
    from .services import find_and_flag_matching_text_in_case as _impl

    return _impl(redaction_id)


def export_case_documents(case_id, review_id=None):
    from .services import export_case_documents as _impl

    return _impl(case_id, review_id=review_id)


def delete_cases_past_retention_date():
    from .services import delete_cases_past_retention_date as _impl

    return _impl()


def delete_original_files_past_threshold():
    from .services import delete_original_files_past_threshold as _impl

    return _impl()
