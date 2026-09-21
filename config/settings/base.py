from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parents[2]


def load_local_env_file() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if not name or name in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[name] = value


load_local_env_file()


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    file_name = os.getenv(f"{name}_FILE")
    if file_name:
        try:
            value = Path(file_name).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Could not read secret file for {name}: {file_name}") from exc
    else:
        value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def openrouter_api_url() -> str:
    configured_url = env("OPENROUTER_API_URL", "")
    if configured_url:
        return configured_url
    openai_base_url = env("OPENAI_BASE_URL", "").rstrip("/")
    if "openrouter.ai" in openai_base_url:
        if openai_base_url.endswith("/chat/completions"):
            return openai_base_url
        return f"{openai_base_url}/chat/completions"
    return "https://openrouter.ai/api/v1/chat/completions"


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [
    x.strip() for x in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()
]
CSRF_TRUSTED_ORIGINS = [
    x.strip() for x in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "simple_history",
    "ki_radar.core",
    "ki_radar.accelerator",
    "ki_radar.accounts",
    "ki_radar.architecture",
    "ki_radar.use_cases",
    "ki_radar.governance",
    "ki_radar.reviews",
    "ki_radar.notifications",
    "ki_radar.reporting",
    "ki_radar.delivery",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ki_radar.core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
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
                "ki_radar.core.context_processors.navigation_context",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

database_url = env("DATABASE_URL")
if database_url:
    parsed_database_url = urlsplit(database_url)
    database_config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed_database_url.path.lstrip("/")),
        "USER": unquote(parsed_database_url.username or ""),
        "PASSWORD": unquote(parsed_database_url.password or ""),
        "HOST": parsed_database_url.hostname or "localhost",
        "PORT": str(parsed_database_url.port or 5432),
    }
else:
    database_config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "ki_radar"),
        "USER": env("POSTGRES_USER", "ki_radar"),
        "PASSWORD": env("POSTGRES_PASSWORD", "ki_radar_local"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }

database_config.update(
    {
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {"connect_timeout": 5},
    }
)
DATABASES = {"default": database_config}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de-de"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Europe/Berlin")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "reporting:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", "1800"))
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

AXES_FAILURE_LIMIT = int(env("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_HTTP_RESPONSE_CODE = 429

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

ANONYMIZATION_LEDGER_PATH = Path(
    env("ANONYMIZATION_LEDGER_PATH", str(BASE_DIR / "var" / "anonymization-ledger.jsonl"))
)
MONITORING_TOKEN = env("MONITORING_TOKEN", "")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", "") or (
    env("OPENAI_API_KEY", "") if "openrouter.ai" in env("OPENAI_BASE_URL", "") else ""
)
OPENROUTER_MODEL = env("OPENROUTER_MODEL", "")
OPENROUTER_API_URL = openrouter_api_url()
OPENROUTER_TIMEOUT_SECONDS = env("OPENROUTER_TIMEOUT_SECONDS", "30")
OPENROUTER_APP_NAME = env("OPENROUTER_APP_NAME", "KI-Radar")
OPENROUTER_SITE_URL = env("OPENROUTER_SITE_URL", "")
OPENROUTER_MAX_RESPONSE_BYTES = env("OPENROUTER_MAX_RESPONSE_BYTES", "8000000")
OPENROUTER_REASONING_EXCLUDE = env_bool("OPENROUTER_REASONING_EXCLUDE", True)
ACCELERATOR_LLM_TIMEOUT_SECONDS = env(
    "ACCELERATOR_LLM_TIMEOUT_SECONDS",
    "60",
)
ACCELERATOR_LLM_MAX_INPUT_CHARS = env("ACCELERATOR_LLM_MAX_INPUT_CHARS", "12000")
ACCELERATOR_LLM_MAX_OUTPUT_TOKENS = env("ACCELERATOR_LLM_MAX_OUTPUT_TOKENS", "4096")
ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS = env(
    "ACCELERATOR_CAPTURE_MAX_OUTPUT_TOKENS",
    "32768",
)
ACCELERATOR_CAPTURE_TEMPERATURE = env("ACCELERATOR_CAPTURE_TEMPERATURE", "")
ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT = env(
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT",
    "3",
)
ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY = env(
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY",
    "20",
)
ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY = env(
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY",
    "100",
)
ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS = env(
    "ACCELERATOR_SOLUTION_GENERATION_MAX_OUTPUT_TOKENS",
    "16384",
)
ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT = env(
    "ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT",
    "20",
)
ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS = env(
    "ACCELERATOR_SOLUTION_CRITIC_MAX_INPUT_CHARS",
    "100000",
)
ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS = env(
    "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS",
    "90",
)
JOB_FRESHNESS_HOURS = int(env("JOB_FRESHNESS_HOURS", "26"))
SENTRY_DSN = env("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", "development")
APP_VERSION = env("APP_VERSION", "dev")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=SENTRY_ENVIRONMENT,
        release=APP_VERSION,
        send_default_pii=False,
        traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        max_request_body_size="never",
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security.DisallowedHost": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "axes.watch_login": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
