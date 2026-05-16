"""
Async task entry points for the cases app.

All django-q2 async_task() calls should reference this module so that
service functions can be renamed/moved without touching task routing strings.
"""


def process_document_and_create_redactions(document_id):
    from .services import process_document_and_create_redactions as _impl

    return _impl(document_id)


def find_and_flag_matching_text_in_case(redaction_id):
    from .services import find_and_flag_matching_text_in_case as _impl

    return _impl(redaction_id)


def export_case_documents(case_id):
    from .services import export_case_documents as _impl

    return _impl(case_id)
