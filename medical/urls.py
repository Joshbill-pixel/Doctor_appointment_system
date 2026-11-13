import mimetypes

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

# Some browsers and operating systems map .css/.js to the wrong type; declare them explicitly.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("clinic.urls")),
    # Serve the project's own static files (CSS, JS, images) in every mode.
    # For a high-traffic production site, let the web server or WhiteNoise serve them instead.
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATICFILES_DIRS[0]}),
]
