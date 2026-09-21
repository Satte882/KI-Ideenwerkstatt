from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from django.urls import reverse

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.core.navigation import with_return_to
from ki_radar.use_cases.permissions import can_edit_use_case

from .models import DELIVERY_SECTION_DEFINITIONS, SECTION_REVIEW_REQUIREMENTS, DeliveryPackage
from .permissions import allowed_edit_sections, can_review_section
from .readiness import (
    ARCHITECTURE_REQUIRED_FIELDS,
    READY_REQUIRED_FIELDS,
    ReadinessFinding,
    evaluate_delivery_readiness,
)
from .services import technical_owner_source_state

SECTION_LABELS = dict(DELIVERY_SECTION_DEFINITIONS)
SECTION_ORDER = {key: index for index, (key, _label) in enumerate(DELIVERY_SECTION_DEFINITIONS)}
PACKAGE_FIELD_ORDER = {
    field_name: index
    for index, field_name in enumerate(
        field_name
        for section_key, _label in DELIVERY_SECTION_DEFINITIONS
        for field_name in READY_REQUIRED_FIELDS[section_key]
    )
}
ARCHITECTURE_FIELD_ORDER = {
    field_name: len(PACKAGE_FIELD_ORDER) + index
    for index, field_name in enumerate(ARCHITECTURE_REQUIRED_FIELDS)
}
FIELD_ORDER = PACKAGE_FIELD_ORDER | ARCHITECTURE_FIELD_ORDER
PACKAGE_FIELD_CODES = {
    f"{field_name.upper()}_{suffix}": field_name
    for field_name in PACKAGE_FIELD_ORDER
    for suffix in ("MISSING", "GENERIC")
}
ARCHITECTURE_FIELD_CODES = {
    f"{field_name.upper()}_{suffix}": field_name
    for field_name in ARCHITECTURE_FIELD_ORDER
    for suffix in ("MISSING", "GENERIC")
}
FIELD_CODES = PACKAGE_FIELD_CODES | ARCHITECTURE_FIELD_CODES
FIELD_CODES |= {
    "EVALUATION_POPULATION_MISSING": "measurement_plan",
    "EVALUATION_SAMPLE_SIZE_MISSING": "measurement_plan",
    "EVALUATION_UNCERTAINTY_UNDOCUMENTED": "measurement_plan",
    "RECALL_POSITIVE_CASES_MISSING": "measurement_plan",
    "CRITICAL_ERROR_CLASSES_UNDOCUMENTED": "test_scenarios",
    "OUTPUT_TYPE_SEMANTICS_MISSING": "human_oversight",
    "PREDICTIVE_CONFIDENCE_SEMANTICS_INCOMPLETE": "human_oversight",
    "GENERATIVE_NUMERIC_CONFIDENCE_UNJUSTIFIED": "human_oversight",
    "GENERATIVE_GROUNDING_INCOMPLETE": "human_oversight",
    "RULE_BASED_OUTPUT_EVIDENCE_INCOMPLETE": "human_oversight",
    "LATENCY_RETRY_BUDGET_CONFLICT": "non_functional_requirements",
    "RETENTION_SEMANTICS_INCOMPLETE": "logging_and_audit",
}

RESPONSIBILITY_CODES = {
    "TECHNICAL_OWNER_MISSING",
    "TECHNICAL_OWNER_INACTIVE",
    "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED",
}
STRUCTURE_CODES = {
    "SECTION_REVIEW_MISSING",
    "SOURCE_MANIFEST_MISSING",
    "ARCHITECTURE_ARTIFACTS_MISSING",
}
REVIEW_CODES = {
    "SECTION_BLOCKED",
    "SECTION_NEEDS_REVIEW",
    "REQUIRED_CONFIRMATION_MISSING",
    "NOT_APPLICABLE_REASON_MISSING",
    "INDEPENDENT_CONFIRMATION_MISSING",
}
CONDITION_CODES = {
    "CONDITION_OWNER_MISSING",
    "CONDITION_DUE_DATE_MISSING",
    "APPROVAL_CONDITIONS_NOT_TRANSFERRED",
}


@dataclass(frozen=True)
class ActionableFinding:
    code: str
    section_key: str
    severity: str
    message: str
    title: str
    priority_class: int
    action_label: str
    url: str
    responsible_role: str
    responsible_person: str
    can_execute: bool
    field_name: str = ""
    field_label: str = ""
    rule: str = ""
    cause: str = ""

    @property
    def sort_key(self) -> tuple[int, int, int, str]:
        return (
            self.priority_class,
            SECTION_ORDER.get(self.section_key, 99),
            FIELD_ORDER.get(self.field_name, 999),
            self.code,
        )


def _display_name(user) -> str:
    return user.get_display_name() if user else "Nicht benannt"


def section_responsibility(package: DeliveryPackage, section_key: str) -> tuple[str, str]:
    requirements = SECTION_REVIEW_REQUIREMENTS.get(section_key, frozenset())
    business_owner = package.use_case.business_owner
    technical_owner = package.technical_owner

    if requirements == {"business"}:
        return "Business Owner", _display_name(business_owner)
    if requirements == {"technical"}:
        return "Technical Owner (Technik, Daten und KI)", _display_name(technical_owner)
    if requirements == {"business", "technical"}:
        if technical_owner and technical_owner.pk == business_owner.pk:
            return (
                "Business Owner sowie Technical Owner (Technik, Daten und KI)",
                _display_name(business_owner),
            )
        return (
            "Business Owner und Technical Owner (Technik, Daten und KI)",
            f"{_display_name(business_owner)} / {_display_name(technical_owner)}",
        )
    return "KI-Koordinator", "Berechtigte Koordination"


def _priority(code: str, severity: str) -> int:
    if code in RESPONSIBILITY_CODES:
        return 1
    if code in STRUCTURE_CODES:
        return 2
    if code in FIELD_CODES or code in CONDITION_CODES:
        return 3
    if code in REVIEW_CODES:
        return 4
    if severity == "warning":
        return 6
    return 3


def _field_label(package: DeliveryPackage, field_name: str) -> str:
    if field_name in ARCHITECTURE_REQUIRED_FIELDS:
        return ARCHITECTURE_REQUIRED_FIELDS[field_name]
    return str(package._meta.get_field(field_name).verbose_name)


def _finding_rule(code: str, field_name: str) -> str:
    if code in PACKAGE_FIELD_CODES | ARCHITECTURE_FIELD_CODES and code.endswith("_MISSING"):
        return "Pflichtangabe muss vollständig ausgefüllt sein."
    if code in PACKAGE_FIELD_CODES | ARCHITECTURE_FIELD_CODES and code.endswith("_GENERIC"):
        return "Inhalt muss konkret und projektspezifisch sein; Vorlagentext reicht nicht aus."
    rules = {
        "TECHNICAL_OWNER_MISSING": (
            "Vor der Übergabe muss ein aktiver Technical Owner benannt sein."
        ),
        "TECHNICAL_OWNER_INACTIVE": (
            "Die technische Verantwortung muss einer aktiven Person zugeordnet sein."
        ),
        "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED": (
            "Eine geänderte Rollenzuordnung muss vor der Übergabe explizit entschieden werden."
        ),
        "SECTION_REVIEW_MISSING": ("Jede Delivery-Sektion benötigt eine strukturierte Prüfung."),
        "SOURCE_MANIFEST_MISSING": (
            "Jede Delivery-Sektion benötigt einen nachvollziehbaren Quellenstand."
        ),
        "ARCHITECTURE_ARTIFACTS_MISSING": (
            "Der Architektur- und Datenkontext muss als umsetzungsbezogenes Artefakt vorliegen."
        ),
        "SECTION_BLOCKED": "Eine blockierte Sektion verhindert die Delivery Readiness.",
        "SECTION_NEEDS_REVIEW": ("Jede Sektion muss vor der Übergabe vollständig geprüft sein."),
        "REQUIRED_CONFIRMATION_MISSING": (
            "Alle erforderlichen fachlichen und technischen Bestätigungen müssen vorliegen."
        ),
        "NOT_APPLICABLE_REASON_MISSING": (
            "Nichtanwendbarkeit ist nur mit einer konkreten Begründung zulässig."
        ),
        "INDEPENDENT_CONFIRMATION_MISSING": (
            "Fachliche und technische Bestätigung müssen von zwei verschiedenen "
            "Personen stammen; eine Admin-Sonderbestätigung reicht für die Übergabe nicht aus."
        ),
        "CONDITION_OWNER_MISSING": (
            "Jede verbindliche Auflage benötigt eine verantwortliche Person."
        ),
        "CONDITION_DUE_DATE_MISSING": ("Jede verbindliche Auflage benötigt eine Fälligkeit."),
        "APPROVAL_CONDITIONS_NOT_TRANSFERRED": (
            "Verbindliche Freigabeauflagen müssen vollständig in die Übergabehinweise "
            "übernommen werden."
        ),
        "SOURCE_CHANGED_AFTER_SNAPSHOT": (
            "Quellenänderungen nach dem Package-Snapshot müssen sichtbar geprüft werden."
        ),
        "EVALUATION_POPULATION_MISSING": (
            "Prozentgrenzen müssen einer konkret benannten Testpopulation zugeordnet sein."
        ),
        "EVALUATION_SAMPLE_SIZE_MISSING": (
            "Prozentgrenzen benötigen eine numerisch dokumentierte Stichprobengröße."
        ),
        "EVALUATION_UNCERTAINTY_UNDOCUMENTED": (
            "Die Aussagekraft kleiner Stichproben muss über Unsicherheit, Fehlerspanne "
            "oder eine gleichwertige Einordnung sichtbar sein."
        ),
        "RECALL_POSITIVE_CASES_MISSING": (
            "Recall-Ziele benötigen die numerische Anzahl positiver Fälle im Testset."
        ),
        "CRITICAL_ERROR_CLASSES_UNDOCUMENTED": (
            "Seltene und kritische Fehlerklassen benötigen konkrete, gezählte Testfälle "
            "oder kuratierte Testsets."
        ),
        "OUTPUT_TYPE_SEMANTICS_MISSING": (
            "Confidence und Unsicherheit müssen mindestens einem konkreten Output-Typ "
            "zugeordnet sein."
        ),
        "PREDICTIVE_CONFIDENCE_SEMANTICS_INCOMPLETE": (
            "Numerische Confidence für Extraktion oder Klassifikation benötigt eine "
            "fachlich dokumentierte Semantik."
        ),
        "GENERATIVE_NUMERIC_CONFIDENCE_UNJUSTIFIED": (
            "Numerische Confidence ist nur bei fachlich definierter und belastbarer "
            "Semantik zulässig."
        ),
        "GENERATIVE_GROUNDING_INCOMPLETE": (
            "Generative Ausgaben benötigen Grounding oder Quellenbezug und eine sichtbare "
            "Kennzeichnung unsicherer Grundlagen."
        ),
        "RULE_BASED_OUTPUT_EVIDENCE_INCOMPLETE": (
            "Regelbasierte Prüfungen müssen Regelreferenz und Prüfergebnis ausweisen."
        ),
        "LATENCY_RETRY_BUDGET_CONFLICT": (
            "Synchrone Versuche einschließlich Retries müssen im nutzerseitigen "
            "Ende-zu-Ende-Budget bleiben."
        ),
        "RETENTION_SEMANTICS_INCOMPLETE": (
            "Audit-Metadaten und schutzbedürftige Rohinhalte benötigen getrennte "
            "Zwecke, Fristen und Löschregeln."
        ),
    }
    return rules.get(code, "Die Delivery-Readiness-Regel für diesen Punkt ist noch nicht erfüllt.")


def _package_edit_url(package: DeliveryPackage, field_name: str, return_to: str) -> str:
    base = reverse("delivery:package_update", kwargs={"pk": package.pk})
    target = f"{base}?{urlencode({'highlight': field_name})}#field-{field_name}"
    return with_return_to(target, return_to)


def _use_case_edit_url(package: DeliveryPackage, field_name: str, return_to: str) -> str:
    base = reverse("use_cases:edit", kwargs={"pk": package.use_case.pk})
    target = f"{base}?{urlencode({'highlight': field_name})}#field-{field_name}"
    return with_return_to(target, return_to)


def _build_action(
    package: DeliveryPackage,
    finding: ReadinessFinding,
    user,
    *,
    return_to: str,
    technical_owner_source_decision_is_next: bool = False,
) -> ActionableFinding:
    code = finding.code
    section_key = finding.section_key
    responsible_role, responsible_person = section_responsibility(package, section_key)
    priority_class = _priority(code, finding.severity)
    title = finding.message
    action_label = ""
    url = ""
    can_execute = False
    field_name = FIELD_CODES.get(code, "")
    field_label = _field_label(package, field_name) if field_name else ""

    if code == "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED":
        title = "Änderung des Technical Owners entscheiden"
        action_label = "Abweichung auflösen"
        field_label = "Technical Owner"
        responsible_role = "KI-Koordinator"
        responsible_person = "Berechtigte Koordination"
        can_execute = is_coordinator(user)
        if can_execute:
            url = f"{package.get_absolute_url()}#technical-owner-source-change"
    elif code in {"TECHNICAL_OWNER_MISSING", "TECHNICAL_OWNER_INACTIVE"}:
        field_label = "Technical Owner"
        if technical_owner_source_decision_is_next:
            title = "Änderung des Technical Owners entscheiden"
            action_label = "Abweichung auflösen"
            responsible_role = "KI-Koordinator"
            responsible_person = "Berechtigte Koordination"
            can_execute = is_coordinator(user)
            if can_execute:
                url = f"{package.get_absolute_url()}#technical-owner-source-change"
        else:
            if code.endswith("MISSING"):
                title = "Technical Owner benennen"
            else:
                title = "Technical Owner ersetzen"
            action_label = "Technical Owner zuordnen"
            responsible_role = "Business Owner oder KI-Koordinator"
            responsible_person = _display_name(package.use_case.business_owner)
            can_execute = can_edit_use_case(user, package.use_case)
            if can_execute:
                url = _use_case_edit_url(package, "technical_owner", return_to)
    elif field_name:
        title = f"{field_label} {'konkretisieren' if code.endswith('GENERIC') else 'ergänzen'}"
        action_label = "Feld bearbeiten"
        can_execute = section_key in allowed_edit_sections(user, package)
        if can_execute:
            url = _package_edit_url(package, field_name, return_to)
    elif code in REVIEW_CODES:
        label = SECTION_LABELS.get(section_key, section_key)
        field_label = "Sektionsprüfung"
        title = (
            f"Begründung für „{label}“ ergänzen"
            if code == "NOT_APPLICABLE_REASON_MISSING"
            else f"Unabhängige Kontrolle für „{label}“ durchführen"
            if code == "INDEPENDENT_CONFIRMATION_MISSING"
            else f"Sektion „{label}“ prüfen"
        )
        action_label = "Sektion prüfen"
        can_execute = can_review_section(user, package, section_key)
        if can_execute:
            url = f"{package.get_absolute_url()}#section-{section_key}"
    elif code == "ARCHITECTURE_ARTIFACTS_MISSING":
        title = "Architekturkontext anlegen"
        action_label = "Architekturkontext bearbeiten"
        field_label = "Architektur- und Datenartefakte"
        responsible_role, responsible_person = section_responsibility(
            package, "architecture_and_data"
        )
        can_execute = "architecture_and_data" in allowed_edit_sections(user, package)
        if can_execute:
            url = _package_edit_url(package, "system_landscape", return_to)
    elif code in {"SECTION_REVIEW_MISSING", "SOURCE_MANIFEST_MISSING"}:
        label = SECTION_LABELS.get(section_key, section_key)
        field_label = "Sektionsstruktur" if code == "SECTION_REVIEW_MISSING" else "Quellenstand"
        title = f"Struktur für „{label}“ wiederherstellen"
        action_label = "Readiness öffnen"
        responsible_role = "KI-Koordinator"
        responsible_person = "Berechtigte Koordination"
        can_execute = is_coordinator(user)
        if can_execute:
            url = f"{package.get_absolute_url()}#section-{section_key}"
    elif code in {"CONDITION_OWNER_MISSING", "CONDITION_DUE_DATE_MISSING"}:
        field_label = (
            "Auflagenverantwortung" if code.endswith("OWNER_MISSING") else "Auflagenfälligkeit"
        )
        title = "Freigabeauflage vervollständigen"
        action_label = "Freigabe prüfen"
        responsible_role = "KI-Koordinator"
        responsible_person = "Berechtigte Koordination"
        can_execute = is_coordinator(user)
        if can_execute:
            url = f"{package.use_case.get_absolute_url()}#approval"
    elif code == "APPROVAL_CONDITIONS_NOT_TRANSFERRED":
        field_label = "Übergabehinweise"
        title = "Freigabeauflagen in die Übergabe übernehmen"
        action_label = "Übergabehinweise bearbeiten"
        can_execute = "delivery_control" in allowed_edit_sections(user, package)
        if can_execute:
            url = _package_edit_url(package, "handover_notes", return_to)
    elif code == "SOURCE_CHANGED_AFTER_SNAPSHOT":
        field_label = "Quellenstand"
        title = "Geänderte Quelle prüfen"
        action_label = "Use Case öffnen"
        responsible_role = "KI-Koordinator"
        responsible_person = "Berechtigte Koordination"
        can_execute = is_coordinator(user)
        if can_execute:
            url = package.use_case.get_absolute_url()
    return ActionableFinding(
        code=code,
        section_key=section_key,
        severity=finding.severity,
        message=finding.message,
        title=title,
        priority_class=priority_class,
        action_label=action_label,
        url=url,
        responsible_role=responsible_role,
        responsible_person=responsible_person,
        can_execute=can_execute,
        field_name=field_name,
        field_label=field_label,
        rule=_finding_rule(code, field_name),
        cause=finding.message,
    )


def build_actionable_findings(
    package: DeliveryPackage,
    user,
    *,
    return_to: str | None = None,
) -> list[ActionableFinding]:
    target = return_to or package.get_absolute_url()
    raw_findings = evaluate_delivery_readiness(package)
    use_case_owner = package.use_case.technical_owner
    technical_owner_source = technical_owner_source_state(package)
    technical_owner_source_decision_is_next = bool(
        use_case_owner
        and use_case_owner.is_active
        and not use_case_owner.is_anonymized
        and technical_owner_source
        and technical_owner_source["source_changed"]
    )
    actions = [
        _build_action(
            package,
            finding,
            user,
            return_to=target,
            technical_owner_source_decision_is_next=technical_owner_source_decision_is_next,
        )
        for finding in raw_findings
    ]
    return sorted(actions, key=lambda item: item.sort_key)


def primary_delivery_action(
    package: DeliveryPackage,
    user,
    *,
    return_to: str | None = None,
) -> ActionableFinding | None:
    return next(
        (
            finding
            for finding in build_actionable_findings(package, user, return_to=return_to)
            if finding.severity == "blocker"
        ),
        None,
    )
