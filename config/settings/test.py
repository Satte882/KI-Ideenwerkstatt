import os

from .base import *  # noqa: F403
from .base import BASE_DIR, DATABASES

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AXES_ENABLED = False
ACCELERATOR_FIELD_ADOPTION_ENABLED = os.getenv("ACCELERATOR_FIELD_ADOPTION_ENABLED") == "1"
DATABASES["default"]["CONN_MAX_AGE"] = 0
ANONYMIZATION_LEDGER_PATH = BASE_DIR / "var" / "test-anonymization-ledger.jsonl"

if os.getenv("USE_SQLITE_FOR_TESTS") == "1":
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}
    }
