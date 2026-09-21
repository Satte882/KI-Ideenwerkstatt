import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_bootstrap_superuser_does_nothing_without_credentials(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    call_command("bootstrap_superuser")

    assert not get_user_model().objects.exists()


@pytest.mark.django_db
def test_bootstrap_superuser_creates_and_updates_admin(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "Satinder")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "initial-test-password")

    call_command("bootstrap_superuser")

    user = get_user_model().objects.get(username="Satinder")
    assert user.is_active
    assert user.is_staff
    assert user.is_superuser
    assert user.check_password("initial-test-password")

    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "updated-test-password")
    call_command("bootstrap_superuser")

    user.refresh_from_db()
    assert user.check_password("updated-test-password")


@pytest.mark.django_db
def test_bootstrap_superuser_requires_both_credentials(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "Satinder")
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    with pytest.raises(CommandError):
        call_command("bootstrap_superuser")
