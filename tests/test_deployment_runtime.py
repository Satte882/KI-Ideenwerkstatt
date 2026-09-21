from importlib import import_module
from pathlib import Path


def test_production_serves_collected_static_files(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-only-secret")

    production_settings = import_module("config.settings.prod")

    assert production_settings.MIDDLEWARE[1] == "whitenoise.middleware.WhiteNoiseMiddleware"
    assert production_settings.STORAGES["staticfiles"]["BACKEND"] == (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


def test_container_start_command_uses_render_port_with_local_fallback():
    start_script = Path("scripts/start-web.sh").read_text(encoding="utf-8")

    assert "0.0.0.0:${PORT:-8000}" in start_script
    assert '"${WEB_CONCURRENCY:-3}"' in start_script


def test_container_bootstraps_optional_superuser():
    entrypoint = Path("scripts/entrypoint.sh").read_text(encoding="utf-8")

    assert "python manage.py bootstrap_superuser" in entrypoint
