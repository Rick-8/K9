
"""
Django settings for K9 Handmade & Bespoke Gifts.

Django 6.1
Development: Windows / VS Code
Production: Heroku
Database: Neon PostgreSQL
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


# ---------------------------------------------------------------------
# BASE DIRECTORY
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------
# LOCAL ENVIRONMENT VARIABLES
# ---------------------------------------------------------------------

# env.py is only used for local development.
# It must NEVER be committed to Git.

if (BASE_DIR / "env.py").is_file():
    import env


# ---------------------------------------------------------------------
# DEVELOPMENT / PRODUCTION MODE
# ---------------------------------------------------------------------

DEBUG = os.getenv(
    "DEVELOPMENT", "False"
).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------
# SECRET KEY
# ---------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "")

if DEBUG:
    # Local-only fallback. Never used in production.
    if not SECRET_KEY:
        SECRET_KEY = (
            "django-insecure-k9-local-development-"
            "only-not-for-production-2026"
        )
else:
    if (
        not SECRET_KEY
        or len(SECRET_KEY) < 50
        or SECRET_KEY.startswith("django-insecure-")
    ):
        raise ImproperlyConfigured(
            "A secure SECRET_KEY of at least 50 "
            "characters must be configured in production."
        )


# ---------------------------------------------------------------------
# ALLOWED HOSTS AND CSRF
# ---------------------------------------------------------------------

def environment_list(name):
    return [
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    ]


ALLOWED_HOSTS = environment_list(
    "DJANGO_ALLOWED_HOSTS"
)

if DEBUG:
    ALLOWED_HOSTS.extend([
        "localhost",
        "127.0.0.1",
    ])
elif not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be configured "
        "in production."
    )


CSRF_TRUSTED_ORIGINS = environment_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS"
)


# ---------------------------------------------------------------------
# HTTPS / PRODUCTION SECURITY
# ---------------------------------------------------------------------

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = None

    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    SECURE_HSTS_SECONDS = 0

else:
    # Heroku terminates HTTPS at its trusted proxy.
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    SECURE_SSL_REDIRECT = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Enable HSTS after live HTTPS has been verified.
    SECURE_HSTS_SECONDS = int(
        os.getenv("DJANGO_HSTS_SECONDS", "0")
    )


# Do not include subdomains or preload until
# the domain configuration has been fully verified.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

SESSION_COOKIE_HTTPONLY = True

X_FRAME_OPTIONS = "DENY"


# ---------------------------------------------------------------------
# APPLICATIONS
# ---------------------------------------------------------------------

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # Django Allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # Local K9 apps
    "home",
    "bespoke.apps.BespokeConfig",
    "orders",
    "shop",
]

SITE_ID = 1


# ---------------------------------------------------------------------
# MIDDLEWARE
# ---------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Serve static files in production.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Required for Django Allauth.
    "allauth.account.middleware.AccountMiddleware",
]


# ---------------------------------------------------------------------
# URL CONFIGURATION
# ---------------------------------------------------------------------

ROOT_URLCONF = "core.urls"


# ---------------------------------------------------------------------
# TEMPLATES
# ---------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "home.context_processors.site_banner",
            ],
        },
    },
]


# ---------------------------------------------------------------------
# WSGI
# ---------------------------------------------------------------------

WSGI_APPLICATION = "core.wsgi.application"


# ---------------------------------------------------------------------
# DATABASE - NEON POSTGRESQL
# ---------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL must be configured."
    )

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=60,
        conn_health_checks=True,
        ssl_require=not DEBUG,
    )
}


# ---------------------------------------------------------------------
# PASSWORD VALIDATION
# ---------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ---------------------------------------------------------------------
# INTERNATIONALISATION
# ---------------------------------------------------------------------

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/London"

USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------
# STATIC FILES
# ---------------------------------------------------------------------

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# ---------------------------------------------------------------------
# STATIC FILE STORAGE
# ---------------------------------------------------------------------

STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# ---------------------------------------------------------------------
# EMAIL - DJANGO 6.1 MAILERS
# ---------------------------------------------------------------------

MAILERS = {
    "default": {
        "BACKEND": (
            "django.core.mail.backends.smtp."
            "EmailBackend"
        ),

        "OPTIONS": {
            "host": "smtp.gmail.com",
            "port": 587,

            "username": os.getenv(
                "EMAIL_HOST_USER"
            ),

            "password": os.getenv(
                "EMAIL_HOST_PASSWORD"
            ),

            "use_tls": True,
            "timeout": 10,
        },
    },
}

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    os.getenv(
        "EMAIL_HOST_USER",
        "donotreplyk61@gmail.com",
    ),
)


# ---------------------------------------------------------------------
# DJANGO ALLAUTH - SIGNUP
# ---------------------------------------------------------------------

ACCOUNT_SIGNUP_FIELDS = [
    "username*",
    "email*",
    "password1*",
    "password2*",
]


# ---------------------------------------------------------------------
# EMAIL VERIFICATION
# ---------------------------------------------------------------------

# Require email verification before login.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# Use clickable email links rather than codes.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = False

# Verification link expires after three days.
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3

# Login automatically after email verification.
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# Email subject prefix.
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[K9] "

# Signup completion page.
ACCOUNT_SIGNUP_REDIRECT_URL = "signup_complete"

# Redirect after verifying the email.
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = (
    "signup_complete"
)


# ---------------------------------------------------------------------
# AUTHENTICATION REDIRECTS
# ---------------------------------------------------------------------

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/"
