import mimetypes

from django.contrib import admin
from django.urls import include, path

# Some browsers and operating systems map .css/.js to the wrong type; declare them explicitly.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

# Static files are served by WhiteNoise (see settings.MIDDLEWARE), so no static route is needed here.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("clinic.urls")),
]
