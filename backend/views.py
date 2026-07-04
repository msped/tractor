import os

from django.core.exceptions import SuspiciousOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView


class MediaServeView(APIView):
    """
    Serve media files (uploaded originals, export packages) to
    authenticated users.

    In production Django does not serve MEDIA_URL itself and nginx proxies
    /media/ through to the backend, so without this view every FileField
    URL 404s — and serving the files straight from nginx would expose
    unredacted case documents without authentication.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, path):
        try:
            if not default_storage.exists(path):
                raise Http404
            file_handle = default_storage.open(path, "rb")
        except SuspiciousOperation:
            # Path traversal attempt — present as a plain not-found.
            raise Http404
        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=os.path.basename(path),
        )
