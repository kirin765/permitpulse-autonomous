from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "permitpulse",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "permitpulse.middleware.OrganizationResolverMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def _database_config() -> dict:
    database_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

    parsed = urlparse(database_url)
    engine = "django.db.backends.postgresql"
    if parsed.scheme.startswith("sqlite"):
        engine = "django.db.backends.sqlite3"

    if engine == "django.db.backends.sqlite3":
        raw_path = parsed.path or ""
        if raw_path in {"", "/"}:
            db_name = BASE_DIR / "db.sqlite3"
        elif raw_path == "/:memory:":
            db_name = ":memory:"
        elif raw_path.startswith("/"):
            db_name = BASE_DIR / raw_path.lstrip("/")
        else:
            db_name = raw_path
        return {
            "default": {
                "ENGINE": engine,
                "NAME": db_name,
            }
        }

    query = parse_qs(parsed.query)
    options = {}
    if "sslmode" in query and query["sslmode"]:
        options["sslmode"] = query["sslmode"][0]
    elif (parsed.hostname or "").endswith(".supabase.co"):
        # Supabase connections require TLS.
        options["sslmode"] = "require"

    config = {
        "default": {
            "ENGINE": engine,
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
        }
    }
    if options:
        config["default"]["OPTIONS"] = options
    return config


DATABASES = _database_config()

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

PERMITPULSE_CITY_CODES = ["NYC", "LA", "SF"]
PERMITPULSE_CONFIDENCE_THRESHOLD = float(os.getenv("PERMITPULSE_CONFIDENCE_THRESHOLD", "0.8"))
AUTONOMY_TARGET_AVAILABILITY = float(os.getenv("AUTONOMY_TARGET_AVAILABILITY", "99.9"))
AUTONOMY_TARGET_AUTO_RECOVERY = float(os.getenv("AUTONOMY_TARGET_AUTO_RECOVERY", "95"))
CRON_SHARED_SECRET = os.getenv("CRON_SHARED_SECRET", "")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_IDS = {
    "starter": os.getenv("STRIPE_STARTER_PRICE_ID", "price_starter"),
    "pro": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro"),
    "team": os.getenv("STRIPE_TEAM_PRICE_ID", "price_team"),
}

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
