from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from ki_radar.core.models import TimeStampedModel


class DeliveryArchitectureArtifacts(TimeStampedModel):
    delivery_package = models.OneToOneField(
        "delivery.DeliveryPackage",
        on_delete=models.CASCADE,
        related_name="architecture_artifacts",
    )
    system_landscape = models.TextField(
        blank=True,
        verbose_name="Ist-/Ziel-Systemlandschaft",
    )
    system_responsibilities = models.TextField(
        blank=True,
        verbose_name="Systemverantwortung und Zielkomponenten",
    )
    data_flows = models.TextField(
        blank=True,
        verbose_name="Daten- und Informationsflüsse",
    )
    data_quality_and_access = models.TextField(
        blank=True,
        verbose_name="Datenqualität, Zugriff und Schutzbedarf",
    )
    integration_contracts = models.TextField(
        blank=True,
        verbose_name="Integrationsverträge und Verantwortlichkeiten",
    )
    integration_operations = models.TextField(
        blank=True,
        verbose_name="Integrationsbetrieb und Fehlerbehandlung",
    )
    artifacts_url = models.URLField(
        blank=True,
        verbose_name="Architekturartefakte und Diagramme",
    )

    def __str__(self) -> str:
        return f"Architekturartefakte für {self.delivery_package}"

    @property
    def missing_ready_fields(self) -> tuple[str, ...]:
        required = {
            "system_landscape": "Ist-/Ziel-Systemlandschaft",
            "system_responsibilities": "Systemverantwortung und Zielkomponenten",
            "data_flows": "Daten- und Informationsflüsse",
            "data_quality_and_access": "Datenqualität, Zugriff und Schutzbedarf",
            "integration_contracts": "Integrationsverträge und Verantwortlichkeiten",
            "integration_operations": "Integrationsbetrieb und Fehlerbehandlung",
        }
        return tuple(
            label for name, label in required.items() if not str(getattr(self, name, "")).strip()
        )


def get_delivery_architecture_artifacts(package) -> DeliveryArchitectureArtifacts | None:
    try:
        return package.architecture_artifacts
    except ObjectDoesNotExist:
        return None


@receiver(post_save, sender="delivery.DeliveryPackage")
def ensure_delivery_architecture_artifacts(sender, instance, created, **kwargs):
    payload = getattr(instance, "_architecture_artifacts_payload", None)
    if payload is not None:
        delattr(instance, "_architecture_artifacts_payload")
    elif created:
        payload = {
            "system_landscape": (
                f"Ist-Systeme und Arbeitsmittel:\n{instance.system_context}\n\n"
                "Ziel-Systemlandschaft und Systemverantwortung im Package konkretisieren."
            ),
            "system_responsibilities": (
                "Führendes System, fachlichen Owner, technischen Owner und Zielkomponenten "
                "konkretisieren."
            ),
            "data_flows": (
                f"Datenobjekte und Quellen:\n{instance.data_context}\n\n"
                "Schnittstellen und Integrationen:\n"
                f"{instance.integrations or 'Keine Integrationen dokumentiert.'}"
            ),
            "data_quality_and_access": (
                "Datenqualität, Zugriffsweg, Datenverantwortung, Schutzbedarf und "
                "Aktualisierung konkretisieren."
            ),
            "integration_contracts": (
                instance.integrations
                or (
                    "Keine technischen Integrationen vorgesehen; fachliche Verantwortlichkeiten "
                    "und Begründung bestätigen."
                )
            ),
            "integration_operations": (
                "Authentifizierung, Auslöser, Fehlerbehandlung, Retry/Fallback, Monitoring und "
                "technische Verantwortung konkretisieren."
            ),
        }
    if payload is None:
        return
    DeliveryArchitectureArtifacts.objects.update_or_create(
        delivery_package=instance,
        defaults=payload,
    )
