from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import build_initial_delivery_data
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase

SUPPLIER_GOLDEN_PATH_STREAM_KEY = "supplier-selection-golden-path"
SUPPLIER_GOLDEN_PATH_USE_CASE_KEY = "supplier-selection-golden-path"
SUPPLIER_GOLDEN_PATH_TITLE = "[DEMO] Automatisierte Lieferantenauswahl"


@transaction.atomic
def seed_supplier_golden_path_demo() -> dict[str, int]:
    today = timezone.localdate()
    coordinator = User.objects.get(username="demo_ki_koordinator")
    owner = User.objects.get(username="demo_business_owner")
    business_unit = BusinessUnit.objects.get(name="[DEMO] Prozesse & Organisation")

    use_case, _ = UseCase.objects.update_or_create(
        demo_key=SUPPLIER_GOLDEN_PATH_USE_CASE_KEY,
        defaults={
            "title": SUPPLIER_GOLDEN_PATH_TITLE,
            "summary": (
                "Angebotsdaten extrahieren und vergleichen, fehlende Angaben erkennen, "
                "Nachfassen unterstützen und eine begründete Vorauswahl erstellen."
            ),
            "problem_statement": (
                "Mindestens fünf Lieferantenangebote werden manuell bearbeitet. Uneinheitliche "
                "Formate, fehlende Angaben und wiederholtes Nachfassen erzeugen einen "
                "Kapazitätsengpass im Einkauf."
            ),
            "business_unit": business_unit,
            "affected_process": "Lieferantenauswahl und Beschaffungsentscheidung",
            "target_users": "Strategischer Einkauf und anfordernder Fachbereich",
            "submitter": owner,
            "business_owner": owner,
            "coordinator": coordinator,
            "technical_owner": coordinator,
            "status": UseCase.Status.REVIEW,
            "decision_status": UseCase.DecisionStatus.APPROVED,
            "priority": UseCase.Priority.HIGH,
            "next_review_date": today + timezone.timedelta(days=14),
            "pilot_start": None,
            "planned_pilot_end": today + timezone.timedelta(days=30),
            "actual_end_date": None,
            "solution_type": UseCase.SolutionType.ASSISTANT,
            "hosting_type": UseCase.HostingType.HYBRID,
            "provider": "Interne Umsetzung",
            "product_name": "Supplier Selection Demo",
            "model_name": "Dokumentenextraktion und regelgestützter Vergleich",
            "source_systems": "Shared Inbox, Dateiablage und ERP",
            "data_sources": (
                "Lieferantenangebote in PDF- und Word-Formaten, Kriterienkatalog und "
                "Lieferantenstammdaten"
            ),
            "interface_description": (
                "Angebote aus Shared Inbox und Dateiablage; ERP-Abgleich zunächst per Export."
            ),
            "intended_users": "Einkäuferinnen und Einkäufer mit Vergabeverantwortung",
            "intended_purpose": (
                "Angebote strukturieren, fehlende Angaben markieren, Nachfragen vorbereiten und "
                "eine nachvollziehbare Vorauswahl erstellen."
            ),
            "expected_benefit": (
                "Durchlaufzeit der Angebotsauswertung von fünf auf drei Arbeitstage reduzieren."
            ),
            "benefit_category": "Zeitersparnis und Entscheidungsqualität",
            "metric_name": "Durchlaufzeit der Angebotsauswertung",
            "metric_type": UseCase.MetricType.DURATION,
            "metric_direction": UseCase.MetricDirection.LOWER,
            "metric_unit": "Arbeitstage",
            "metric_baseline": Decimal("5"),
            "metric_target": Decimal("3"),
            "metric_actual": None,
            "metric_measurement_method": (
                "Median vom Eingang des fünften Angebots bis zur dokumentierten Vorauswahl."
            ),
            "metric_measurement_period": "",
            "metric_measured_at": None,
            "metric_evidence_url": "",
            "one_time_cost": Decimal("18000"),
            "recurring_cost": Decimal("1200"),
            "business_value": UseCase.Level.HIGH,
            "technical_feasibility": UseCase.Level.HIGH,
            "data_readiness": UseCase.Level.MEDIUM,
            "risk_complexity": UseCase.Level.MEDIUM,
            "human_oversight": (
                "Das System erstellt nur eine begründete Vorauswahl; die endgültige "
                "Vergabeentscheidung bleibt beim Einkauf."
            ),
            "support_responsibility": "IT Application Management und Einkauf",
            "ending_reason": "",
            "final_assessment": "",
            "lessons_learned": "",
            "data_and_access_handling": "",
            "replacement_solution": "",
            "is_archived": False,
        },
    )

    value_stream, _ = ValueStream.objects.update_or_create(
        demo_key=SUPPLIER_GOLDEN_PATH_STREAM_KEY,
        defaults={
            "name": "[DEMO] Beschaffung bis Zahlung - Lieferantenauswahl",
            "description": "End-to-End-Wertstrom vom freigegebenen Bedarf bis zur Zahlung.",
            "business_unit": business_unit,
            "owner": owner,
            "created_by": coordinator,
            "trigger": "Ein beschaffungsrelevanter Bedarf wurde fachlich freigegeben.",
            "outcome": "Lieferant ist nachvollziehbar ausgewählt, Leistung erbracht und bezahlt.",
            "scope_in": "Bedarf, Lieferantenauswahl, Bestellung, Lieferung, Leistung und Zahlung.",
            "scope_out": "Vertragsverhandlung und autonome Vergabeentscheidung.",
            "strategic_objective": "Beschaffungsentscheidungen beschleunigen und vereinheitlichen.",
            "stakeholders": "Einkauf, Fachbereich, Lieferanten, Compliance, IT und Buchhaltung.",
            "constraints": (
                "Mindestens fünf Angebote; endgültige Vergabe bleibt eine menschliche Entscheidung."
            ),
            "status": ValueStream.Status.ACTIVE,
        },
    )
    ValueStreamFocus.objects.update_or_create(
        value_stream=value_stream,
        defaults={
            "business_domain": BusinessDomain.PROCUREMENT,
            "capability": "Supplier Sourcing und Angebotsvergleich",
            "strategic_impact": ScreeningLevel.HIGH,
            "economic_potential": ScreeningLevel.HIGH,
            "pain_intensity": ScreeningLevel.HIGH,
            "data_accessibility": ScreeningLevel.MEDIUM,
            "change_effort": ScreeningLevel.MEDIUM,
            "status": ValueStreamFocus.Status.SELECTED,
            "rationale": (
                "Hoher manueller Aufwand, wiederkehrende Angebotsmengen und messbare "
                "Durchlaufzeit rechtfertigen den Deep Dive."
            ),
            "updated_by": coordinator,
        },
    )
    stage, _ = ValueStreamStage.objects.update_or_create(
        value_stream=value_stream,
        sequence=3,
        defaults={
            "name": "Lieferantenauswahl und Beschaffungsentscheidung",
            "description": "Angebote einholen, prüfen, vergleichen und Entscheidung vorbereiten.",
            "actors": "Einkauf, anfordernder Fachbereich und freigebende Stelle",
            "systems": "Shared Inbox, Dateiablage und ERP",
            "documents": "Mindestens fünf Angebote, Kriterienkatalog und Stammdaten",
            "pain_points": (
                "Uneinheitliche Formate, fehlende Angaben und wiederholtes manuelles Nachfassen."
            ),
            "baseline_metrics": "Median fünf Arbeitstage bis zur belastbaren Vorauswahl.",
        },
    )
    process, _ = ProcessAnalysis.objects.update_or_create(
        stage=stage,
        name="Angebote vergleichen und Lieferant vorauswählen",
        defaults={
            "status": ProcessAnalysis.Status.TARGET_DEFINED,
            "scope_start": "Mindestens fünf Lieferantenangebote liegen vor.",
            "scope_end": "Eine begründete Vorauswahl liegt dem Einkauf zur Entscheidung vor.",
            "trigger": "Eingang des fünften angeforderten Angebots.",
            "outcome": "Vollständiger, vergleichbarer Angebotsüberblick mit begründeter Vorauswahl.",
            "current_flow": (
                "Angebote öffnen, Vollständigkeit prüfen, Angaben übertragen, Rückfragen senden, "
                "Kriterien vergleichen und Entscheidungsvorlage erstellen."
            ),
            "roles": "Einkauf strukturiert und bewertet; Fachbereich prüft fachliche Kriterien.",
            "systems": "E-Mail, Word/PDF, Dateiablage, Tabellenkalkulation und ERP.",
            "data_objects": (
                "Angebote, Preis- und Leistungspositionen, Lieferzeiten, Vertragsbedingungen, "
                "Kriterienkatalog und Lieferantenstammdaten."
            ),
            "business_rules": "Mindestens fünf Angebote; Muss-Kriterien vor Bonus-Malus-Vergleich.",
            "handoffs": "Rückfragen an Lieferanten; finale Vergabe durch den Einkauf.",
            "bottlenecks": "Manuelle Extraktion, Medienbrüche, fehlende Angaben und Nachfassschleifen.",
            "exceptions": "Unvollständige Angebote, abweichende Einheiten und Nebenangebote.",
            "baseline_metrics": "Median fünf Arbeitstage; mehrere Rückfragen je Vorgang.",
            "target_state_principles": (
                "Daten automatisiert vorbereiten, Lücken sichtbar machen und die Vergabeentscheidung "
                "beim Menschen belassen."
            ),
            "analyzed_by": coordinator,
        },
    )
    option, _ = SolutionOption.objects.update_or_create(
        process_analysis=process,
        name="Assistierte Lieferantenauswahl",
        defaults={
            "option_type": SolutionOption.OptionType.ASSISTANT,
            "recommendation": SolutionOption.Recommendation.PREFERRED,
            "description": (
                "Angebotsdaten extrahieren und normalisieren, fehlende Angaben erkennen, "
                "Nachfragen vorbereiten und Lieferanten nach freigegebenen Kriterien vergleichen."
            ),
            "expected_value": "Weniger Bearbeitungszeit und konsistentere Vorauswahl.",
            "feasibility": "high",
            "data_requirements": "Angebote, Kriterienkatalog und Lieferantenstammdaten.",
            "application_impact": "Neuer assistierter Arbeitsbereich für den Einkauf.",
            "integration_impact": "Shared Inbox und Dateiablage; ERP-Abgleich zunächst per Export.",
            "technology_constraints": "Nachvollziehbare Kriterien und keine autonome Vergabe.",
            "risks": "Fehlerhafte Extraktion oder unangemessene Gewichtung einzelner Kriterien.",
            "architecture_fit": (
                "Dokumentenextraktion und Vergleich werden unterstützt; ERP und Einkauf bleiben "
                "führend."
            ),
            "created_by": coordinator,
        },
    )
    UseCaseOrigin.objects.update_or_create(
        use_case=use_case,
        defaults={"stage": stage, "process_analysis": process, "solution_option": option},
    )

    GovernanceAssessment.objects.update_or_create(
        use_case=use_case,
        basis_version="DEMO-GOLDEN-2026-01",
        defaults={
            "assessment_date": today,
            "reviewer": coordinator,
            "human_oversight_planned": True,
            "result": GovernanceAssessment.Result.NO_FLAGS,
            "rationale": "Keine Personaldaten; finale Lieferantenentscheidung bleibt beim Einkauf.",
            "evidence_url": "https://example.invalid/evidence/supplier-selection-golden-path",
            "next_assessment_date": today + timezone.timedelta(days=180),
        },
    )
    assessment, _ = DecisionAssessment.objects.update_or_create(
        use_case=use_case,
        version=1,
        defaults={
            "assessment_date": today,
            "assessed_by": coordinator,
            "business_value": UseCase.Level.HIGH,
            "strategic_fit": UseCase.Level.HIGH,
            "technical_feasibility": UseCase.Level.HIGH,
            "data_readiness": UseCase.Level.MEDIUM,
            "risk_complexity": UseCase.Level.MEDIUM,
            "evidence_quality": DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
            "evidence_recency": DecisionAssessment.ConfidenceFactor.SOLID,
            "evidence_coverage": DecisionAssessment.ConfidenceFactor.SOLID,
            "independent_review": DecisionAssessment.ConfidenceFactor.SOLID,
            "assumptions_resolved": DecisionAssessment.ConfidenceFactor.SOLID,
            "evidence_url": "https://example.invalid/evidence/supplier-selection-assessment",
            "rationale": "Prozessbaseline, Angebotsstichprobe und Lösungsrahmen liegen vor.",
            "governance_precheck_completed": True,
            "recommendation": UseCase.DecisionStatus.APPROVED,
        },
    )
    decision, _ = ApprovalDecision.objects.update_or_create(
        use_case=use_case,
        assessment=assessment,
        defaults={
            "decision_status": UseCase.DecisionStatus.APPROVED,
            "rationale": "Pilot und Delivery Package sind fachlich freigegeben.",
            "decided_by": coordinator,
            "governance_confirmed": True,
            "finalized_at": timezone.now(),
        },
    )

    initial = build_initial_delivery_data(use_case, decision)
    package = DeliveryPackage.objects.filter(use_case=use_case, version=1).first()
    if package is None:
        package = DeliveryPackage.objects.create(
            use_case=use_case,
            version=1,
            generated_from_decision=decision,
            created_by=coordinator,
            **initial,
        )
    if package.status != DeliveryPackage.Status.HANDED_OVER:
        for field_name, value in initial.items():
            setattr(package, field_name, value)
        package.status = DeliveryPackage.Status.READY
        package.generated_from_decision = decision
        package.created_by = coordinator
        package.external_delivery_url = "https://example.invalid/delivery/supplier-selection"
        package.save()

    return {"use_cases": 1, "value_streams": 1, "delivery_packages": 1}


@transaction.atomic
def clear_supplier_golden_path_demo() -> dict[str, int]:
    use_cases = UseCase.objects.filter(demo_key=SUPPLIER_GOLDEN_PATH_USE_CASE_KEY)
    DeliveryPackage.objects.filter(use_case__in=use_cases).delete()
    ApprovalDecision.objects.filter(use_case__in=use_cases).delete()
    DecisionAssessment.objects.filter(use_case__in=use_cases).delete()
    use_case_count = use_cases.count()
    use_cases.delete()
    value_streams = ValueStream.objects.filter(demo_key=SUPPLIER_GOLDEN_PATH_STREAM_KEY)
    value_stream_count = value_streams.count()
    value_streams.delete()
    return {"use_cases": use_case_count, "value_streams": value_stream_count}
