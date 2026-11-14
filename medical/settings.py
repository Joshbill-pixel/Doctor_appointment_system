"""Settings for the BSU Medical Consultation & Appointment Portal.

Every value that differs between development and production can be set with an
environment variable (see README.md and render.yaml). Running on Render is detected
automatically through the RENDER / RENDER_EXTERNAL_HOSTNAME variables Render sets.
"""
import os
from pathlib import Path

import dj_database_url
from django.contrib.messages import constants as message_constants
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


ON_RENDER = bool(os.environ.get("RENDER"))
RENDER_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")

# Debug is off by default on Render, on by default everywhere else (local development).
DEBUG = env_bool("DJANGO_DEBUG", default=not ON_RENDER)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-change-me-before-deploying"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
if RENDER_HOSTNAME and RENDER_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_HOSTNAME)

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if RENDER_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "clinic",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves collected static files directly from the app server.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "medical.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "clinic.context_processors.portal",
            ],
        },
    },
]

WSGI_APPLICATION = "medical.wsgi.application"

# Local development uses SQLite. On Render, DATABASE_URL is injected from the managed PostgreSQL database.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # "remember me" sessions last two weeks
PASSWORD_RESET_TIMEOUT = 60 * 60 * 2

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

# E-mail: development prints messages to the console. Set the SMTP variables for production.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "BSU Medical Centre <no-reply@bsu.edu.ng>")

# Portal branding and rules
if os.environ.get("SITE_URL"):
    SITE_URL = os.environ["SITE_URL"].rstrip("/")
elif RENDER_HOSTNAME:
    SITE_URL = f"https://{RENDER_HOSTNAME}"
else:
    SITE_URL = "http://127.0.0.1:8000"
CLINIC_NAME = "BSU Medical Centre"
CLINIC_FULL_NAME = "Benue State University Medical Consultation Centre"
CLINIC_ADDRESS = "Benue State University, Makurdi, Benue State, Nigeria"
CLINIC_PHONE = os.environ.get("CLINIC_PHONE", "+234 800 000 0000")
CLINIC_EMAIL = os.environ.get("CLINIC_EMAIL", "medical@bsu.edu.ng")
BOOKING_WINDOW_DAYS = 60   # how far ahead patients may book
CHANGE_CUTOFF_HOURS = 2    # cancel / reschedule closes this many hours before the visit

# Production hardening: enabled automatically when DEBUG is off.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Render terminates TLS at its edge and forwards the original scheme in X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("DJANGO_BEHIND_HTTPS_PROXY", True) else None
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    # Render already redirects http:// to https:// at its edge, so this stays off unless you need it.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)

# Send application logs and errors to stdout, where Render shows them in its log viewer.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
