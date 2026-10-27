"""Fixed, versioned synthetic packets, not generated observations or decisions."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from ki_radar.accelerator.investigation_ingestion import create_managed_discovery_source_folder
from ki_radar.accelerator.investigation_tools import (
    DiscoverySnapshotRequest,
    create_discovery_source_snapshot,
)
from ki_radar.accelerator.services import create_autonomous_capture_session

PACKETS = {
    "A": {
        "title": "Kundenanfragen zuordnen",
        "problem_statement": "SOLO-A-v1: Im synthetischen Test-Service werden freie "
        "Kundenanfragen manuell gelesen und einer verantwortlichen Stelle zugeordnet.",
        "business_context": "Serviceleitung und Sachbearbeitung berichten uneinheitliche "
        "Zuordnung. Im Test stehen frei erfundene Anfragen und freigegebene Zuständigkeitsregeln "
        "bereit. Fehlende Zuordnung könnte Antworten verzögern; Ursache und Geschäftswirkung "
        "sind nicht bewiesen. Hypothese: weniger Klärarbeit könnte verlässliche Kundenbetreuung "
        "bei mehr Anfragen ermöglichen. Baseline, Geldbeträge und Wirkung unbekannt. "
        "Organisatorisch: Zuständigkeiten klären; regelbasiert: Schlüsselwörter pflegen; "
        "KI: freie Formulierungen vorschlagen, Mensch prüft. Alle Varianten kosten Einführung, "
        "Pflege und Schulung; KI zusätzlich Betrieb und Einzelprüfung. "
        "Qualitative Screeningannahmen für diesen Test: strategischer Beitrag, Potenzial, "
        "Problemintensität, Datenzugang und Änderungsaufwand jeweils mittel; keine Messwerte.",
    },
    "B": {
        "title": "Strategisches Servicewachstum",
        "problem_statement": "SOLO-B-v1: Die synthetische Geschäftsführung will mehr "
        "Kundenanfragen bei verlässlichen Servicezusagen bearbeiten. Ist-Daten sind unbekannt.",
        "business_context": "Menschlich gewählter Untersuchungsrahmen: Eingang einer "
        "Kundenanfrage bis zur verantworteten Antwortvorbereitung. Verbindliche Buchung und "
        "Durchführung sind ausgeschlossen. Serviceleitung verantwortet den begrenzten Versuch. "
        "Eine bestätigte Einzelursache, globale Screeningwerte, Kosten und Baseline fehlen. "
        "Zu vergleichen sind eine verbindliche Quelle mit Zuständigkeit und Vertretung, "
        "regelbasierte Verteilung und assistierte Quellenanzeige. Assistenz kann Verbindlichkeit "
        "nicht herstellen. Einführung, Quellenpflege und Schulung sind nötig; bei KI zusätzlich "
        "Integration, Betrieb und menschliche Prüfung. Wirkung und Tragfähigkeit bleiben offen.",
    },
}
SCOPE = {
    "scope_start": "Eingang einer Kundenanfrage",
    "scope_end": "Verantwortete Antwortvorbereitung",
    "scope_out": "Verbindliche Buchung und operative Durchführung",
    "reason": "Synthetischer menschlicher Untersuchungsrahmen; keine Überlegenheit nachgewiesen",
    "validation_step": "Ist-Ablauf und verfügbare Daten mit Serviceverantwortlichen erheben",
}


def source_text(case):
    packet = PACKETS[case]
    return (
        f"SYNTHETISCHES SOLO-QUELLENPAKET {case}-v1\n"
        f"{packet['problem_statement']}\n{packet['business_context']}\n"
    )


@transaction.atomic
def start_discovery(actor, case):
    from .access import require_isolation

    require_isolation()
    packet = PACKETS[case]
    session = create_autonomous_capture_session(
        actor=actor,
        problem_statement=packet["problem_statement"],
        business_context=packet["business_context"],
        **({"strategic_scope": dict(SCOPE)} if case == "B" else {}),
    )
    folder = create_managed_discovery_source_folder(
        actor=actor,
        capture_session_id=session.pk,
        name=f"Synthetisches SOLO-{case}-v1",
        uploads=[SimpleUploadedFile(f"SOLO-{case}-v1.md", source_text(case).encode("utf-8"))],
    )
    create_discovery_source_snapshot(
        actor=actor,
        request=DiscoverySnapshotRequest(capture_session_id=session.pk, folder_id=folder.pk),
    )
    return session
