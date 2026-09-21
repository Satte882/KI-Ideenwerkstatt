from __future__ import annotations

from django.db import transaction

from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase

DEMO_USE_CASE_IDENTITIES = {
    "internal-knowledge-assistant": "[DEMO] Interner Wissensassistent",
    "invoice-check-golden-path": "[DEMO] Automatische Rechnungspruefung",
    "meeting-summary-review": "[DEMO] Zusammenfassung von Besprechungen",
    "document-routing-handed-over": "[DEMO] Klassifikation eingehender Dokumente",
    "customer-service-conditional": "[DEMO] Unterstuetzung bei Kundenanfragen",
    "forecast-low-data-readiness": "[DEMO] Absatz- oder Bedarfsprognose",
    "text-quality-idea": "[DEMO] Qualitaetspruefung von Texten",
    "contract-extraction-risk-review": "[DEMO] Extraktion von Vertragsinformationen",
    "direct-intake-incomplete": "[DEMO] Priorisierung interner Anfragen",
    "applicant-screening-stopped": "[DEMO] Vorsortierung von Bewerbungsunterlagen",
}

DEMO_VALUE_STREAM_IDENTITIES = {
    "invoice-check-golden-path": "[DEMO] Beschaffung bis Zahlung",
    "supplier-selection-incomplete": "[DEMO] Lieferantenauswahl und Beauftragung",
    "order-approval-non-ai": "[DEMO] Bedarf bis Bestellung",
}


def demo_use_case_keys() -> list[str]:
    return list(DEMO_USE_CASE_IDENTITIES)


def demo_value_stream_keys() -> list[str]:
    return list(DEMO_VALUE_STREAM_IDENTITIES)


def _restore_display_value(model, *, key: str, expected: str, field_name: str) -> None:
    instance = model.objects.filter(demo_key=key).first()
    if instance is None or getattr(instance, field_name) == expected:
        return
    conflict = model.objects.filter(**{field_name: expected}).exclude(pk=instance.pk).first()
    if conflict is not None:
        raise RuntimeError(
            f"Demo identity conflict for {model.__name__} '{key}': "
            f"'{expected}' is already used by another object."
        )
    setattr(instance, field_name, expected)
    instance.save(update_fields=[field_name, "updated_at"])


def _assign_key(model, *, key: str, expected: str, field_name: str) -> None:
    keyed = model.objects.filter(demo_key=key).first()
    if keyed is not None:
        return
    matches = model.objects.filter(**{field_name: expected})
    if matches.count() > 1:
        raise RuntimeError(
            f"Demo identity conflict for {model.__name__} '{key}': "
            f"multiple objects use '{expected}'."
        )
    instance = matches.first()
    if instance is None:
        return
    instance.demo_key = key
    instance.save(update_fields=["demo_key", "updated_at"])


@transaction.atomic
def prepare_demo_identities() -> None:
    """Restore canonical display names before legacy title/name based seed code runs.

    The stable demo_key is the identity. Display titles remain editable in a demo, but a
    subsequent seed restores them before the existing idempotent update_or_create calls.
    """

    for key, title in DEMO_USE_CASE_IDENTITIES.items():
        _restore_display_value(UseCase, key=key, expected=title, field_name="title")
    for key, name in DEMO_VALUE_STREAM_IDENTITIES.items():
        _restore_display_value(ValueStream, key=key, expected=name, field_name="name")


@transaction.atomic
def assign_demo_identities() -> None:
    """Attach stable keys to newly seeded or legacy demo root objects."""

    for key, title in DEMO_USE_CASE_IDENTITIES.items():
        _assign_key(UseCase, key=key, expected=title, field_name="title")
    for key, name in DEMO_VALUE_STREAM_IDENTITIES.items():
        _assign_key(ValueStream, key=key, expected=name, field_name="name")
