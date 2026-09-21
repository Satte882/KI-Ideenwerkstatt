from __future__ import annotations

import json

from .architecture_artifacts import get_delivery_architecture_artifacts
from .models import DELIVERY_SECTION_DEFINITIONS, DeliveryPackage
from .readiness import delivery_status_snapshot, evaluate_delivery_readiness


def _review_summary(package: DeliveryPackage) -> str:
    reviews = {review.section_key: review for review in package.section_reviews.all()}
    rows = ["| Sektion | Herkunft | Prüfstatus | Bestätigt durch |", "|---|---|---|---|"]
    for key, label in DELIVERY_SECTION_DEFINITIONS:
        review = reviews.get(key)
        if review is None:
            rows.append(f"| {label} | - | Fehlt | - |")
            continue
        confirmed = []
        if review.business_confirmed_by:
            confirmed.append(f"fachlich: {review.business_confirmed_by}")
        if review.technical_confirmed_by:
            confirmed.append(f"technisch: {review.technical_confirmed_by}")
        rows.append(
            f"| {label} | {review.get_content_origin_display()} | "
            f"{review.get_review_status_display()} | {', '.join(confirmed) or '-'} |"
        )
    return "\n".join(rows)


def _source_manifest(package: DeliveryPackage) -> str:
    review = package.section_reviews.first()
    if review is None or not review.source_manifest:
        return "-"
    return f"```json\n{json.dumps(review.source_manifest, ensure_ascii=False, indent=2)}\n```"


def _role_source_decisions(package: DeliveryPackage) -> str:
    decisions = package.role_source_decisions.select_related("decided_by").all()
    if not decisions:
        return "Keine Quellenentscheidungen dokumentiert."
    rows = [
        "| Zeitpunkt | Rolle | Alt | Neue Quelle | Entscheidung | Begründung | Person |",
        "|---|---|---|---|---|---|---|",
    ]
    for decision in decisions:
        rows.append(
            f"| {decision.decided_at:%d.%m.%Y %H:%M} | "
            f"{decision.get_role_key_display()} | {decision.old_value_label or '-'} | "
            f"{decision.new_value_label or '-'} | {decision.get_decision_display()} | "
            f"{decision.rationale} | {decision.decided_by or 'Gelöschte Person'} |"
        )
    return "\n".join(rows)


def _moscow_prioritization(package: DeliveryPackage) -> str:
    return "\n\n".join(
        [
            (
                "MoSCoW priorisiert den Umfang dieser Delivery-Version. "
                "'Won't this time' bezeichnet bewusst zurückgestellten, grundsätzlich "
                "zulässigen Umfang und ist nicht mit 'Nicht im Scope' gleichzusetzen."
            ),
            f"### Must / MVP-Scope\n{package.mvp_scope or '-'}",
            f"### Should\n{package.should_scope or '-'}",
            f"### Could\n{package.could_scope or '-'}",
            f"### Won't this time\n{package.wont_this_time or '-'}",
        ]
    )


def render_delivery_markdown(package: DeliveryPackage) -> str:
    sections = [
        ("Problem und Geschäftskontext", package.problem_context),
        ("Ziel und Ergebnis", package.target_outcome),
        (
            "Scope-Grenzen",
            f"### Im Scope\n{package.in_scope}\n\n### Nicht im Scope\n{package.out_of_scope}",
        ),
        (
            "Priorisierung für diese Delivery-Version (MoSCoW)",
            _moscow_prioritization(package),
        ),
        ("Nutzer und Szenarien", package.users_and_scenarios),
        ("Lösungsrahmen", package.solution_outline),
        ("Systemkontext", package.system_context),
        ("Datenkontext", package.data_context),
        ("Integrationen", package.integrations),
        ("Funktionale Anforderungen", package.functional_requirements),
        ("Nichtfunktionale Anforderungen", package.non_functional_requirements),
        ("Security, Datenschutz und Recht", package.security_privacy_requirements),
        ("Menschliche Aufsicht", package.human_oversight),
        ("Logging und Audit", package.logging_and_audit),
        ("Betrieb und Support", package.operations_and_support),
        ("Akzeptanzkriterien", package.acceptance_criteria),
        ("Testfälle", package.test_scenarios),
        (
            f"Übernommener Messstand bei Erstellung von Delivery v{package.version}",
            package.measurement_plan,
        ),
        ("Abhängigkeiten", package.dependencies),
        ("Risiken", package.risks),
        ("Annahmen", package.assumptions),
        ("Architekturentscheidungen", package.architecture_decisions),
        ("Initiales Backlog", package.initial_backlog),
        ("Übergabehinweise", package.handover_notes),
    ]
    artifacts = get_delivery_architecture_artifacts(package)
    if artifacts is not None:
        sections.extend(
            [
                ("Ist-/Ziel-Systemlandschaft", artifacts.system_landscape),
                ("Systemverantwortung und Zielkomponenten", artifacts.system_responsibilities),
                ("Daten- und Informationsflüsse", artifacts.data_flows),
                ("Datenqualität, Zugriff und Schutzbedarf", artifacts.data_quality_and_access),
                (
                    "Integrationsverträge und Verantwortlichkeiten",
                    artifacts.integration_contracts,
                ),
                ("Integrationsbetrieb und Fehlerbehandlung", artifacts.integration_operations),
                (
                    "Architekturartefakte und Diagramme",
                    artifacts.artifacts_url
                    or (
                        "Im Delivery Package dokumentiert: Zielarchitektur/Systemkontext "
                        "sowie Daten-/Informationsfluss. Externe Referenz: nicht "
                        "hinterlegt (optional)."
                    ),
                ),
            ]
        )

    findings = evaluate_delivery_readiness(package)
    status = delivery_status_snapshot(package)
    findings_text = (
        "\n".join(
            f"- **{finding.severity.upper()} · {finding.code}:** {finding.message}"
            for finding in findings
        )
        or "Keine offenen Readiness-Findings."
    )
    sections.extend(
        [
            ("Sektionsprüfung", _review_summary(package)),
            ("Quellenstand", _source_manifest(package)),
            ("Quellenentscheidungen", _role_source_decisions(package)),
            ("Readiness-Findings", findings_text),
        ]
    )

    body = "\n\n".join(f"## {title}\n\n{content or '-'}" for title, content in sections)
    return (
        f"# Delivery Package - {package.use_case.short_id} {package.use_case.title}\n\n"
        f"Version: {package.version}  \n"
        f"Readiness-Schema: {package.readiness_schema_version}  \n"
        f"Status: {status.label}  \n"
        f"Technical Owner: {package.technical_owner or 'Nicht benannt'}\n\n"
        "Methodische Referenz: `docs/DELIVERY_METHODOLOGY.md`\n\n"
        f"{body}\n"
    )
