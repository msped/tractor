from django.contrib import admin

from .models import Model

# This makes the Schedule model from django-q2 and our
# new Model appear in your admin site.
admin.site.register(Model)
