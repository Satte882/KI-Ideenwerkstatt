from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import build_initial_delivery_data, hand_over_package
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase

INVOICE_STREAM_KEY = "invoice-check-golden-path"
INVOICE_STREAM_NAME = "[DEMO] Beschaffung bis Zahlung"
INVOICE_USE_CASE_KEY = "invoice-check-golden-path"
INVOICE_USE_CASE_TITLE = "[DEMO] Automatische Rechnungspruefung"

SUPPLIER_STREAM_KEY = "supplier-selection-incomplete"
SUPPLIER_STREAM_NAME = "[DEMO] Lieferantenauswahl und Beauftragung"

ORDER_STREAM_KEY = "order-approval-non-ai"
ORDER_STREAM_NAME = "[DEMO] Bedarf bis Bestellung"

DOCUMENT_USE_CASE_KEY = "document-routing-handed-over"
DOCUMENT_USE_CASE_TITLE = "[DEMO] Klassifikation eingehender Dokumente"
CUSTOMER_USE_CASE_KEY = "customer-service-conditional"
CUSTOMER_USE_CASE_TITLE = "[DEMO] Unterstuetzung bei Kundenanfragen"
APPLICANT_USE_CASE_KEY = "applicant-screening-stopped"
APPLICANT_USE_CASE_TITLE = "[DEMO] Vorsortierung von Bewerbungsunterlagen"
DIRECT_INTAKE_KEY = "direct-intake-incomplete"
DIRECT_INTAKE_TITLE = "[DEMO] Priorisierung interner Anfragen"


def _demo_use_case(*, key: str, title: str) -> UseCase:
    use_case = UseCase.objects.filter(demo_key=key).first()
    if use_case is not None:
        return use_case
    return UseCase.objects.get(title=title)


def _upsert_value_stream(*, key: str, name: str, defaults: dict) -> ValueStream:
    value_stream = ValueStream.objects.filter(demo_key=key).first()
    if value_stream is None:
        value_stream = ValueStream.objects.filter(name=name).first()
    if value_stream is None:
        return ValueStream.objects.create(demo_key=key, name=name, **defaults)
    for field_name, value in {"demo_key": key, "name": name, **defaults}.items():
        setattr(value_stream, field_name, value)
    value_stream.save()
    return value_stream


def _upsert_assessment(
    *,
    use_case: UseCase,
    coordinator,
    recommendation: str,
    business_value: str,
    technical_feasibility: str,
    data_readiness: str,
    risk_complexity: str,
    rationale: str,
    evidence_quality: int = DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
    factor: int = DecisionAssessment.ConfidenceFactor.SOLID,
) -> DecisionAssessment:
    assessment, _ = DecisionAssessment.objects.update_or_create(
        use_case=use_case,
        version=1,
        defaults={
            "assessment_date": timezone.localdate(),
            "assessed_by": coordinator,
            "business_value": business_value,
            "strategic_fit": business_value,
            "technical_feasibility": technical_feasibility,
            "data_readiness": data_readiness,
            "risk_complexity": risk_complexity,
            "evidence_quality": evidence_quality,
            "evidence_recency": factor,
            "evidence_coverage": factor,
            "independent_review": factor,
            "assumptions_resolved": factor,
            "evidence_url": f"https://example.invalid/evidence/{use_case.demo_key or use_case.pk}",
            "rationale": rationale,
            "governance_precheck_completed": True,
            "recommendation": recommendation,
        },
    )
    return assessment


def _upsert_decision(
    *,
    use_case: UseCase,
    assessment: DecisionAssessment,
    coordinator,
    decision_status: str,
    rationale: str,
    finalized: bool,
    conditions: str = "",
    condition_due_days: int | None = None,
) -> ApprovalDecision:
    decision, _ = ApprovalDecision.objects.update_or_create(
        use_case=use_case,
        assessment=assessment,
        defaults={
            "decision_status": decision_status,
            "rationale": rationale,
            "decided_by": coordinator,
            "governance_confirmed": True,
            "conditions": conditions,
            "condition_owner": use_case.business_owner if conditions else None,
            "condition_due_date": (
                timezone.localdate() + timezone.timedelta(days=condition_due_days)
                if condition_due_days is not None
                else None
            ),
            "second_approved_by": None,
            "finalized_at": timezone.now() if finalized else None,
        },
    )
    return decision


def _seed_invoice_golden_path() -> tuple[ValueStream, ProcessAnalysis, int, int]:
    use_case = _demo_use_case(key=INVOICE_USE_CASE_KEY, title=INVOICE_USE_CASE_TITLE)
    owner = use_case.business_owner
    coordinator = use_case.coordinator
    if owner is None or coordinator is None:
        raise RuntimeError("The invoice demo requires owner and coordinator roles.")

    value_stream = _upsert_value_stream(
        key=INVOICE_STREAM_KEY,
        name=INVOICE_STREAM_NAME,
        defaults={
            "description": "End-to-End-Wertschöpfung vom Bedarf bis zur bezahlten Leistung.",
            "business_unit": use_case.business_unit,
            "owner": owner,
            "created_by": coordinator,
            "trigger": "Ein fachlich freigegebener Bedarf liegt vor.",
            "outcome": "Die Leistung ist geprüft, verbucht und bezahlt.",
            "scope_in": "Bedarf, Beschaffung, Leistungserbringung und Zahlung.",
            "scope_out": "Strategische Lieferantenentwicklung und Vertragsverhandlung.",
            "strategic_objective": "Durchlaufzeit senken und Entscheidungen nachvollziehbar machen.",
            "stakeholders": "Fachbereich, Einkauf, Lieferanten, Buchhaltung und IT.",
            "constraints": "Das ERP bleibt führend; Entscheidungen werden nicht vollautomatisiert.",
            "status": ValueStream.Status.ACTIVE,
        },
    )
    stage, _ = ValueStreamStage.objects.update_or_create(
        value_stream=value_stream,
        sequence=5,
        defaults={
            "name": "Eingangsrechnung prüfen",
            "description": "Rechnung mit Bestellung und Wareneingang abgleichen.",
            "actors": "Einkauf, Buchhaltung und fachliche Freigabe.",
            "systems": "ERP und Dokumentenmanagement.",
            "documents": "Rechnung, Bestellung und Wareneingang.",
            "pain_points": "Manuelle Prüfung dauert lange; Abweichungen werden uneinheitlich bewertet.",
            "baseline_metrics": "Rund elf Minuten Prüfzeit je Rechnung.",
        },
    )
    process, _ = ProcessAnalysis.objects.update_or_create(
        stage=stage,
        name="Eingangsrechnungsprüfung",
        defaults={
            "status": ProcessAnalysis.Status.TARGET_DEFINED,
            "scope_start": "Eine Rechnung ist eingegangen.",
            "scope_end": "Die Rechnung ist freigegeben oder zur Klärung zurückgegeben.",
            "trigger": "Eingang einer neuen Rechnung.",
            "outcome": "Nachvollziehbare Zahlungsfreigabe oder begründete Abweichung.",
            "current_flow": (
                "Rechnung öffnen, Bestell- und Wareneingangsdaten suchen, Positionen "
                "vergleichen, Abweichungen bewerten und Freigabe dokumentieren."
            ),
            "roles": "Buchhaltung prüft formal; Einkauf und Fachbereich klären Abweichungen.",
            "systems": "ERP, Dokumentenmanagement und E-Mail.",
            "data_objects": "Rechnung, Bestellung, Wareneingang und Lieferantenstammdaten.",
            "business_rules": "Betrag, Menge, Preis und Bestellbezug müssen plausibel sein.",
            "handoffs": "Buchhaltung übergibt Abweichungen an Einkauf oder Fachbereich.",
            "bottlenecks": "Manuelle Suche, Medienbrüche und Rückfragen verursachen Wartezeit.",
            "exceptions": "Teilrechnungen, fehlende Bestellnummern und abweichende Mengeneinheiten.",
            "baseline_metrics": "Elf Minuten je Rechnung; mehrere Rückfragen pro Woche.",
            "target_state_principles": (
                "Standardfälle automatisiert vorbereiten, Abweichungen erklären und die "
                "fachliche Freigabe beim Menschen belassen."
            ),
            "analyzed_by": coordinator,
        },
    )
    option, _ = SolutionOption.objects.update_or_create(
        process_analysis=process,
        name="Regel- und KI-gestützte Rechnungsprüfung",
        defaults={
            "option_type": SolutionOption.OptionType.ASSISTANT,
            "recommendation": SolutionOption.Recommendation.PREFERRED,
            "description": (
                "Rechnungsdaten extrahieren, regelbasiert abgleichen und nicht eindeutige "
                "Abweichungen zur fachlichen Prüfung markieren."
            ),
            "expected_value": "Prüfzeit reduzieren und Abweichungen konsistenter behandeln.",
            "feasibility": "medium",
            "data_requirements": "Rechnungen, Bestellungen und Wareneingangsdaten.",
            "application_impact": "Erweiterung der internen Rechnungsprüfung.",
            "integration_impact": "ERP- und Dokumentenmanagement-Schnittstelle.",
            "technology_constraints": "Interne Verarbeitung und nachvollziehbare Regeln.",
            "risks": "Sonderfälle dürfen nicht fälschlich automatisch freigegeben werden.",
            "architecture_fit": (
                "Standardfälle werden vorbereitet; das ERP bleibt führend und der Mensch "
                "entscheidet über Abweichungen."
            ),
            "created_by": coordinator,
        },
    )
    UseCaseOrigin.objects.update_or_create(
        use_case=use_case,
        defaults={
            "stage": stage,
            "process_analysis": process,
            "solution_option": option,
        },
    )

    assessment = _upsert_assessment(
        use_case=use_case,
        coordinator=coordinator,
        recommendation=UseCase.DecisionStatus.APPROVED,
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        rationale="Prozessmessung, Datenstichprobe und technischer Lösungsrahmen liegen vor.",
    )
    decision = _upsert_decision(
        use_case=use_case,
        assessment=assessment,
        coordinator=coordinator,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Pilot und Delivery Package sind für den Demo-Use-Case freigegeben.",
        finalized=True,
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.technical_owner = coordinator
    use_case.save(update_fields=["decision_status", "technical_owner", "updated_at"])

    initial = build_initial_delivery_data(use_case, decision)
    package = DeliveryPackage.objects.filter(use_case=use_case, version=1).first()
    if package is None:
        DeliveryPackage.objects.create(
            use_case=use_case,
            version=1,
            status=DeliveryPackage.Status.READY,
            generated_from_decision=decision,
            created_by=coordinator,
            technical_owner=coordinator,
            **initial,
        )
    elif package.status != DeliveryPackage.Status.HANDED_OVER:
        package.status = DeliveryPackage.Status.READY
        package.generated_from_decision = decision
        package.created_by = coordinator
        package.technical_owner = coordinator
        for field_name, value in initial.items():
            setattr(package, field_name, value)
        package.save()

    return value_stream, process, 1, 1


def _seed_incomplete_supplier_discovery(
    reference_use_case: UseCase,
) -> tuple[ValueStream, ProcessAnalysis]:
    owner = reference_use_case.business_owner
    coordinator = reference_use_case.coordinator
    value_stream = _upsert_value_stream(
        key=SUPPLIER_STREAM_KEY,
        name=SUPPLIER_STREAM_NAME,
        defaults={
            "description": "Lieferanten identifizieren, vergleichen und für eine Beauftragung auswählen.",
            "business_unit": reference_use_case.business_unit,
            "owner": owner,
            "created_by": coordinator,
            "trigger": "Ein beschaffungsrelevanter Bedarf wurde freigegeben.",
            "outcome": "Ein geeigneter Lieferant ist nachvollziehbar ausgewählt.",
            "scope_in": "Lieferantensuche, Anfrage, Angebotsvergleich und Auswahlentscheidung.",
            "scope_out": "Vertragsabschluss und operative Leistungserbringung.",
            "strategic_objective": "Vergleichbarkeit erhöhen und Durchlaufzeiten reduzieren.",
            "stakeholders": "Einkauf, Fachbereich, Compliance und Lieferanten.",
            "constraints": "Mindestens fünf Lieferanten sind anzufragen.",
            "status": ValueStream.Status.ACTIVE,
        },
    )
    stage, _ = ValueStreamStage.objects.update_or_create(
        value_stream=value_stream,
        sequence=3,
        defaults={
            "name": "Lieferantenvorauswahl",
            "description": "Angebote einholen, fehlende Informationen nachfordern und vergleichen.",
            "actors": "Einkauf und anfordernder Fachbereich.",
            "systems": "E-Mail, Dateiablage und ERP.",
            "documents": "Angebote, Kriterienkatalog und Lieferantenstammdaten.",
            "pain_points": "Angebote sind uneinheitlich; Informationen fehlen oder sind schwer vergleichbar.",
            "baseline_metrics": "",
        },
    )
    process, _ = ProcessAnalysis.objects.update_or_create(
        stage=stage,
        name="Lieferantenvorauswahl und Angebotsvergleich",
        defaults={
            "status": ProcessAnalysis.Status.DRAFT,
            "scope_start": "Der freigegebene Bedarf liegt dem Einkauf vor.",
            "scope_end": "Eine dokumentierte Vorauswahl liegt vor.",
            "trigger": "Beschaffungsanfrage des Fachbereichs.",
            "outcome": "Vergleichbare Angebote und begründete Vorauswahl.",
            "current_flow": "Anfragen versenden, Rückläufe sammeln und manuell in Tabellen übertragen.",
            "roles": "Einkauf koordiniert; Fachbereich bewertet fachliche Kriterien.",
            "systems": "E-Mail, Word, PDF und Tabellenkalkulation.",
            "data_objects": "",
            "business_rules": "Mindestens fünf Anbieter; Muss-Kriterien sind noch nicht vollständig dokumentiert.",
            "handoffs": "Rückfragen zwischen Einkauf, Fachbereich und Lieferanten.",
            "bottlenecks": "Fehlende Angaben werden spät erkannt; Angebote sind strukturell uneinheitlich.",
            "exceptions": "Nicht alle Anbieter antworten fristgerecht.",
            "baseline_metrics": "",
            "target_state_principles": "Fehlende Angaben früh erkennen und Entscheidungen nachvollziehbar machen.",
            "analyzed_by": coordinator,
        },
    )
    process.solution_options.all().delete()
    return value_stream, process


def _seed_non_ai_order_approval(
    reference_use_case: UseCase,
) -> tuple[ValueStream, ProcessAnalysis, int]:
    owner = reference_use_case.business_owner
    coordinator = reference_use_case.coordinator
    value_stream = _upsert_value_stream(
        key=ORDER_STREAM_KEY,
        name=ORDER_STREAM_NAME,
        defaults={
            "description": "Bedarf erfassen, prüfen, freigeben und als Bestellung auslösen.",
            "business_unit": reference_use_case.business_unit,
            "owner": owner,
            "created_by": coordinator,
            "trigger": "Ein operativer Bedarf wurde erfasst.",
            "outcome": "Eine regelkonforme Bestellung wurde ausgelöst.",
            "scope_in": "Bedarfsmeldung, Prüfung, Freigabe und Bestellung.",
            "scope_out": "Wareneingang, Rechnungsprüfung und Zahlung.",
            "strategic_objective": "Kleine Bestellungen schneller und regelkonform freigeben.",
            "stakeholders": "Fachbereich, Einkauf, Controlling und IT.",
            "constraints": "Budget- und Betragsgrenzen bleiben verbindlich.",
            "status": ValueStream.Status.ACTIVE,
        },
    )
    stage, _ = ValueStreamStage.objects.update_or_create(
        value_stream=value_stream,
        sequence=2,
        defaults={
            "name": "Kleine Bestellung freigeben",
            "description": "Bedarf gegen Budget, Betrag und Warengruppe prüfen.",
            "actors": "Anfordernde Person, Kostenstellenverantwortung und Einkauf.",
            "systems": "ERP und Beschaffungsportal.",
            "documents": "Bedarfsmeldung, Budget und Freigaberegeln.",
            "pain_points": "Auch kleine Standardbestellungen warten auf manuelle Einzelentscheidungen.",
            "baseline_metrics": "Durchschnittlich 1,5 Arbeitstage Wartezeit.",
        },
    )
    process, _ = ProcessAnalysis.objects.update_or_create(
        stage=stage,
        name="Freigabe kleiner Standardbestellungen",
        defaults={
            "status": ProcessAnalysis.Status.TARGET_DEFINED,
            "scope_start": "Eine vollständige Bedarfsmeldung liegt vor.",
            "scope_end": "Die Bestellung ist freigegeben oder begründet abgelehnt.",
            "trigger": "Bedarfsmeldung unterhalb der definierten Betragsgrenze.",
            "outcome": "Regelkonforme Entscheidung ohne unnötige Wartezeit.",
            "current_flow": "Jede Bestellung wird manuell durch dieselbe Freigabestufe geprüft.",
            "roles": "Fachbereich meldet; Kostenstellenverantwortung und Einkauf prüfen.",
            "systems": "ERP und Beschaffungsportal.",
            "data_objects": "Bestellwert, Warengruppe, Budget, Lieferant und Kostenstelle.",
            "business_rules": "Unter 500 Euro, freigegebener Lieferant und verfügbares Budget.",
            "handoffs": "Fachbereich an Kostenstellenverantwortung, danach Einkauf.",
            "bottlenecks": "Standardfälle warten trotz eindeutiger Regeln auf manuelle Freigabe.",
            "exceptions": "Neue Lieferanten oder gesperrte Warengruppen bleiben manuell.",
            "baseline_metrics": "1,5 Arbeitstage; 80 Prozent erfüllen dieselben Standardregeln.",
            "target_state_principles": "Deterministische Regeln automatisieren; Ausnahmen manuell prüfen.",
            "analyzed_by": coordinator,
        },
    )
    options = [
        {
            "name": "Delegationsregel vereinfachen",
            "option_type": SolutionOption.OptionType.ORGANIZATIONAL,
            "recommendation": SolutionOption.Recommendation.CANDIDATE,
            "description": "Freigabeverantwortung für geringe Beträge organisatorisch delegieren.",
            "expected_value": "Weniger Wartezeit ohne neue Technologie.",
            "feasibility": "high",
        },
        {
            "name": "Regelbasierte automatische Freigabe",
            "option_type": SolutionOption.OptionType.RULE_AUTOMATION,
            "recommendation": SolutionOption.Recommendation.PREFERRED,
            "description": "Eindeutige Betrags-, Budget- und Lieferantenregeln serverseitig auswerten.",
            "expected_value": "Standardfälle sofort entscheiden und Ausnahmen gezielt vorlegen.",
            "feasibility": "high",
        },
        {
            "name": "Generative KI als Freigabeinstanz",
            "option_type": SolutionOption.OptionType.GENERATIVE_AI,
            "recommendation": SolutionOption.Recommendation.REJECTED,
            "description": "Ein Sprachmodell bewertet Bestellanträge und entscheidet über Freigaben.",
            "expected_value": "Kein zusätzlicher Nutzen gegenüber eindeutigen Geschäftsregeln.",
            "feasibility": "medium",
        },
    ]
    names = []
    for option_data in options:
        names.append(option_data["name"])
        SolutionOption.objects.update_or_create(
            process_analysis=process,
            name=option_data["name"],
            defaults={
                **option_data,
                "data_requirements": "Bestellwert, Budget, Warengruppe und Lieferantenstatus.",
                "application_impact": "Erweiterung des vorhandenen Beschaffungsportals.",
                "integration_impact": "ERP-Regelprüfung.",
                "technology_constraints": "Deterministische und auditierbare Entscheidung.",
                "risks": "Fehlerhafte Stammdaten können zu falschen Regelentscheidungen führen.",
                "architecture_fit": "Regeln sind transparent, testbar und für diesen Scope ausreichend.",
                "created_by": coordinator,
            },
        )
    process.solution_options.exclude(name__in=names).delete()
    return value_stream, process, len(options)


def _seed_curated_use_case_decisions() -> int:
    direct = _demo_use_case(key=DIRECT_INTAKE_KEY, title=DIRECT_INTAKE_TITLE)
    direct.data_sources = ""
    direct.decision_status = UseCase.DecisionStatus.CLARIFICATION
    direct.save(update_fields=["data_sources", "decision_status", "updated_at"])

    customer = _demo_use_case(key=CUSTOMER_USE_CASE_KEY, title=CUSTOMER_USE_CASE_TITLE)
    coordinator = customer.coordinator
    if coordinator is None:
        raise RuntimeError("The customer service demo requires a coordinator.")
    customer.decision_status = UseCase.DecisionStatus.READY
    customer.save(update_fields=["decision_status", "updated_at"])
    customer_assessment = _upsert_assessment(
        use_case=customer,
        coordinator=coordinator,
        recommendation=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.HIGH,
        rationale="Nutzen ist plausibel; externe Kommunikation benötigt verbindliche Auflagen.",
        evidence_quality=DecisionAssessment.EvidenceQuality.SAMPLE,
        factor=DecisionAssessment.ConfidenceFactor.SOLID,
    )
    _upsert_decision(
        use_case=customer,
        assessment=customer_assessment,
        coordinator=coordinator,
        decision_status=UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
        rationale="Pilot kann nach unabhängiger Zweitfreigabe unter Auflagen fortgesetzt werden.",
        finalized=False,
        conditions="Vier-Augen-Prinzip, freigegebene Textbausteine und Nachmessung nach 60 Tagen.",
        condition_due_days=14,
    )

    applicant = _demo_use_case(key=APPLICANT_USE_CASE_KEY, title=APPLICANT_USE_CASE_TITLE)
    applicant_coordinator = applicant.coordinator
    if applicant_coordinator is None:
        raise RuntimeError("The applicant screening demo requires a coordinator.")
    applicant_assessment = _upsert_assessment(
        use_case=applicant,
        coordinator=applicant_coordinator,
        recommendation=UseCase.DecisionStatus.NOT_PURSUED,
        business_value=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.LOW,
        risk_complexity=UseCase.Level.HIGH,
        rationale="Automatisierte Personenbewertung ist für den begrenzten Nutzen nicht vertretbar.",
        evidence_quality=DecisionAssessment.EvidenceQuality.EXPERT_OPINION,
        factor=DecisionAssessment.ConfidenceFactor.LIMITED,
    )
    _upsert_decision(
        use_case=applicant,
        assessment=applicant_assessment,
        coordinator=applicant_coordinator,
        decision_status=UseCase.DecisionStatus.NOT_PURSUED,
        rationale="Das Vorhaben wird nach Governance- und Risikoprüfung beendet.",
        finalized=True,
    )
    applicant.decision_status = UseCase.DecisionStatus.NOT_PURSUED
    applicant.save(update_fields=["decision_status", "updated_at"])
    return 2


def _seed_handed_over_document_package() -> int:
    use_case = _demo_use_case(key=DOCUMENT_USE_CASE_KEY, title=DOCUMENT_USE_CASE_TITLE)
    coordinator = use_case.coordinator
    if coordinator is None:
        raise RuntimeError("The document routing demo requires a coordinator.")
    assessment = _upsert_assessment(
        use_case=use_case,
        coordinator=coordinator,
        recommendation=UseCase.DecisionStatus.APPROVED,
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.HIGH,
        risk_complexity=UseCase.Level.LOW,
        rationale="Stichprobe, Betriebsdaten und fachliche Abnahme bestätigen die Umsetzungsreife.",
    )
    decision = _upsert_decision(
        use_case=use_case,
        assessment=assessment,
        coordinator=coordinator,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Die Dokumentenklassifikation ist freigegeben und an Delivery übergeben.",
        finalized=True,
    )
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.technical_owner = coordinator
    use_case.save(update_fields=["decision_status", "technical_owner", "updated_at"])

    initial = build_initial_delivery_data(use_case, decision)
    initial["external_delivery_url"] = "https://example.invalid/delivery/document-routing"
    initial["handover_notes"] = (
        "Demo-Handover abgeschlossen. Die übergebene Version bleibt unveränderlich; "
        "Änderungen erfolgen über eine neue Package-Version."
    )
    package = DeliveryPackage.objects.filter(use_case=use_case, version=1).first()
    if package is None:
        package = DeliveryPackage.objects.create(
            use_case=use_case,
            version=1,
            status=DeliveryPackage.Status.READY,
            generated_from_decision=decision,
            created_by=coordinator,
            technical_owner=coordinator,
            **initial,
        )
        hand_over_package(package, coordinator)
    elif package.status != DeliveryPackage.Status.HANDED_OVER:
        package.status = DeliveryPackage.Status.READY
        package.generated_from_decision = decision
        package.created_by = coordinator
        package.technical_owner = coordinator
        for field_name, value in initial.items():
            setattr(package, field_name, value)
        package.save()
        hand_over_package(package, coordinator)
    return 1


@transaction.atomic
def seed_demo_architecture_data() -> dict[str, int]:
    invoice_use_case = _demo_use_case(key=INVOICE_USE_CASE_KEY, title=INVOICE_USE_CASE_TITLE)
    invoice_stream, invoice_process, invoice_options, invoice_packages = _seed_invoice_golden_path()
    supplier_stream, supplier_process = _seed_incomplete_supplier_discovery(invoice_use_case)
    order_stream, order_process, order_options = _seed_non_ai_order_approval(invoice_use_case)
    _seed_curated_use_case_decisions()
    handed_over_packages = _seed_handed_over_document_package()

    return {
        "value_streams": len({invoice_stream.pk, supplier_stream.pk, order_stream.pk}),
        "process_analyses": len({invoice_process.pk, supplier_process.pk, order_process.pk}),
        "solution_options": invoice_options + order_options,
        "delivery_packages": invoice_packages + handed_over_packages,
    }


@transaction.atomic
def clear_demo_architecture_data() -> dict[str, int]:
    demo_use_cases = UseCase.objects.filter(
        demo_key__in=[
            INVOICE_USE_CASE_KEY,
            DOCUMENT_USE_CASE_KEY,
            CUSTOMER_USE_CASE_KEY,
            APPLICANT_USE_CASE_KEY,
        ]
    ) | UseCase.objects.filter(
        title__in=[
            INVOICE_USE_CASE_TITLE,
            DOCUMENT_USE_CASE_TITLE,
            CUSTOMER_USE_CASE_TITLE,
            APPLICANT_USE_CASE_TITLE,
        ]
    )
    delivery_count, _ = DeliveryPackage.objects.filter(use_case__in=demo_use_cases).delete()
    decision_count, _ = ApprovalDecision.objects.filter(use_case__in=demo_use_cases).delete()
    assessment_count, _ = DecisionAssessment.objects.filter(use_case__in=demo_use_cases).delete()

    stream_filter = ValueStream.objects.filter(
        demo_key__in=[INVOICE_STREAM_KEY, SUPPLIER_STREAM_KEY, ORDER_STREAM_KEY]
    ) | ValueStream.objects.filter(
        name__in=[INVOICE_STREAM_NAME, SUPPLIER_STREAM_NAME, ORDER_STREAM_NAME]
    )
    origin_count, _ = UseCaseOrigin.objects.filter(stage__value_stream__in=stream_filter).delete()
    process_count = ProcessAnalysis.objects.filter(stage__value_stream__in=stream_filter).count()
    option_count = SolutionOption.objects.filter(
        process_analysis__stage__value_stream__in=stream_filter
    ).count()
    stream_count, _ = stream_filter.delete()
    return {
        "delivery_packages": delivery_count,
        "approval_decisions": decision_count,
        "decision_assessments": assessment_count,
        "architecture_origins": origin_count,
        "value_streams": stream_count,
        "process_analyses": process_count,
        "solution_options": option_count,
    }
