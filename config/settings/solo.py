"""Explicitly local, isolated solo practice. Never use for deployment."""

from django.core.exceptions import ImproperlyConfigured

from .base import BASE_DIR, MIDDLEWARE, TEMPLATES, env
from .dev import *  # noqa: F403

SOLO_TEST_MODE = True
SOLO_DATABASE_NAME = env("SOLO_DATABASE_NAME", "ki_radar_solo")
if (
    not SOLO_DATABASE_NAME.startswith("ki_radar_solo")
    or not SOLO_DATABASE_NAME.replace("_", "").isalnum()
):
    raise ImproperlyConfigured("Solo mode requires a ki_radar_solo* database.")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": SOLO_DATABASE_NAME,
        "HOST": "127.0.0.1",
        "PORT": env("SOLO_DATABASE_PORT", "5433"),
        "USER": env("POSTGRES_USER", "ki_radar"),
        "PASSWORD": env("POSTGRES_PASSWORD", "ki_radar_local"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 5},
    }
}
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
SESSION_COOKIE_NAME = "ki_solo_session"
CSRF_COOKIE_NAME = "ki_solo_csrf"
SESSION_COOKIE_AGE = 14400
AXES_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
INVESTIGATION_SOURCE_UPLOAD_ROOT = BASE_DIR / "var" / "solo" / "sources"
ANONYMIZATION_LEDGER_PATH = BASE_DIR / "var" / "solo" / "anonymization-ledger.jsonl"
MIDDLEWARE = [*MIDDLEWARE, "ki_radar.solo.access.LocalSoloMiddleware"]
TEMPLATES[0]["OPTIONS"]["context_processors"] = [
    *TEMPLATES[0]["OPTIONS"]["context_processors"],
    "ki_radar.solo.access.context",
]
