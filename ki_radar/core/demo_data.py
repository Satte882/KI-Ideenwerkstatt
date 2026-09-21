from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    GROUP_READER,
    ensure_groups,
)
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.reviews.models import Review
from ki_radar.use_cases.models import UseCase

DEMO_PREFIX = "[DEMO]"
DEMO_MARKER = "KI-Radar Demo-Datensatz"

DEMO_BUSINESS_UNITS = [
    {
        "name": f"{DEMO_PREFIX} Prozesse & Organisation",
        "description": f"{DEMO_MARKER}: branchenneutrale Einheit fuer Prozessautomatisierung.",
    },
    {
        "name": f"{DEMO_PREFIX} Kunden- & Serviceprozesse",
        "description": f"{DEMO_MARKER}: Einheit fuer servicebezogene Use Cases.",
    },
    {
        "name": f"{DEMO_PREFIX} Daten & Plattformen",
        "description": f"{DEMO_MARKER}: Einheit fuer Daten-, Analyse- und Plattformthemen.",
    },
]

DEMO_USERS = [
    {
        "username": "demo_ki_koordinator",
        "first_name": "Kim",
        "last_name": "Koordination",
        "email": "ki.koordinator@example.invalid",
        "job_function": f"{DEMO_PREFIX} KI-Koordinator",
        "group": GROUP_COORDINATOR,
        "business_unit": f"{DEMO_PREFIX} Daten & Plattformen",
    },
    {
        "username": "demo_ki_pruefer",
        "first_name": "Robin",
        "last_name": "Review",
        "email": "ki.pruefer@example.invalid",
        "job_function": f"{DEMO_PREFIX} Unabhängige Zweitprüfung",
        "group": GROUP_COORDINATOR,
        "business_unit": f"{DEMO_PREFIX} Daten & Plattformen",
    },
    {
        "username": "demo_business_owner",
        "first_name": "Bente",
        "last_name": "Owner",
        "email": "business.owner@example.invalid",
        "job_function": f"{DEMO_PREFIX} Business Owner",
        "group": GROUP_BUSINESS_OWNER,
        "business_unit": f"{DEMO_PREFIX} Prozesse & Organisation",
    },
    {
        "username": "demo_leser",
        "first_name": "Lea",
        "last_name": "Leser",
        "email": "leser@example.invalid",
        "job_function": f"{DEMO_PREFIX} Leser",
        "group": GROUP_READER,
        "business_unit": f"{DEMO_PREFIX} Kunden- & Serviceprozesse",
    },
]


@dataclass(frozen=True)
class GovernanceTemplate:
    personal_data: bool = False
    employee_data: bool = False
    automated_person_assessment: bool = False
    influences_person_decisions: bool = False
    external_ai_or_cloud: bool = False
    generated_external_content: bool = False
    human_oversight_planned: bool = True
    privacy_review_required: bool = False
    security_review_required: bool = False
    legal_review_required: bool = False
    result: str = GovernanceAssessment.Result.NO_FLAGS
    rationale: str = ""
    evidence_url: str = ""
    next_assessment_offset: int | None = 180


@dataclass(frozen=True)
class ReviewTemplate:
    offset: int
    previous_status: str
    new_status: str
    decision: str
    rationale: str
    open_actions: str = ""
    action_due_offset: int | None = None
    next_review_offset: int | None = None
    go_live_exception_confirmed: bool = False


@dataclass(frozen=True)
class UseCaseTemplate:
    title: str
    business_unit: str
    status: str
    priority: str
    next_review_offset: int | None
    problem_statement: str
    affected_process: str
    expected_benefit: str
    business_value: str
    technical_feasibility: str
    data_readiness: str
    risk_complexity: str
    solution_type: str
    hosting_type: str
    provider: str
    product_name: str
    model_name: str
    source_systems: str
    data_sources: str
    target_users: str
    intended_users: str
    intended_purpose: str
    benefit_category: str
    baseline: str = ""
    success_criterion: str = ""
    target_value: str = ""
    realized_result: str = ""
    one_time_cost: Decimal | None = None
    recurring_cost: Decimal | None = None
    pilot_start_offset: int | None = None
    planned_pilot_end_offset: int | None = None
    actual_end_offset: int | None = None
    privacy_review_required: bool = False
    security_review_required: bool = False
    legal_review_required: bool = False
    privacy_review_completed: bool = False
    security_review_completed: bool = False
    legal_review_completed: bool = False
    human_oversight: str = ""
    support_responsibility: str = ""
    ending_reason: str = ""
    final_assessment: str = ""
    lessons_learned: str = ""
    data_and_access_handling: str = ""
    replacement_solution: str = ""
    governance: GovernanceTemplate | None = None
    reviews: list[ReviewTemplate] = field(default_factory=list)


DEMO_USE_CASES = [
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Interner Wissensassistent",
        business_unit=f"{DEMO_PREFIX} Daten & Plattformen",
        status=UseCase.Status.OPERATION,
        priority=UseCase.Priority.HIGH,
        next_review_offset=14,
        problem_statement="Fachwissen liegt verteilt in Handbuechern, Wikis und Prozessdokumenten.",
        affected_process="Wissensmanagement",
        target_users="Mitarbeitende in Fachbereichen und Supportfunktionen.",
        intended_users="Interne Mitarbeitende mit Zugriff auf freigegebene Wissensquellen.",
        intended_purpose="Recherche in internen, freigegebenen Wissensbestaenden beschleunigen.",
        expected_benefit="Schnellere Antworten, weniger Suchaufwand und bessere Wiederverwendung.",
        benefit_category="Zeitersparnis",
        baseline="Durchschnittlich 18 Minuten Recherchezeit pro komplexer Anfrage.",
        success_criterion=(
            "Antworten enthalten Quellenverweise und werden fachlich stichprobenartig geprueft."
        ),
        target_value="Recherchezeit um mindestens 30 Prozent reduzieren.",
        realized_result=(
            "Produktiv genutzt; erste Auswertung zeigt kuerzere Suchzeiten und weniger Rueckfragen."
        ),
        one_time_cost=Decimal("18000.00"),
        recurring_cost=Decimal("2200.00"),
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        solution_type=UseCase.SolutionType.ASSISTANT,
        hosting_type=UseCase.HostingType.HYBRID,
        provider="Beispielanbieter",
        product_name="Enterprise Search Demo",
        model_name="Retriever-Augmented Assistant",
        source_systems="Intranet, Wiki, Prozesshandbuch",
        data_sources="Freigegebene Dokumentbibliotheken ohne vertrauliche Personaldaten.",
        privacy_review_required=False,
        security_review_required=True,
        legal_review_required=False,
        security_review_completed=True,
        human_oversight="Antworten werden mit Quellen angezeigt; Nutzende bleiben verantwortlich.",
        support_responsibility="IT-Service und KI-Koordination pruefen Auffaelligkeiten monatlich.",
        governance=GovernanceTemplate(
            external_ai_or_cloud=True,
            security_review_required=True,
            result=GovernanceAssessment.Result.COMPLETED,
            rationale=(
                "Interne Dokumente, externe Modellkomponente, Sicherheitsreview abgeschlossen."
            ),
            evidence_url="https://example.invalid/evidence/demo-wissensassistent",
        ),
        reviews=[
            ReviewTemplate(
                -120,
                UseCase.Status.PILOT,
                UseCase.Status.OPERATION,
                Review.Decision.GO_LIVE,
                "Pilotziele erreicht, Betrieb mit Quellenpflicht freigegeben.",
                next_review_offset=14,
            )
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Automatische Rechnungspruefung",
        business_unit=f"{DEMO_PREFIX} Prozesse & Organisation",
        status=UseCase.Status.PILOT,
        priority=UseCase.Priority.HIGH,
        next_review_offset=-10,
        problem_statement=(
            "Rechnungen werden manuell gegen Bestellungen und Wareneingaenge geprueft."
        ),
        affected_process="Eingangsrechnungsverarbeitung",
        target_users="Sachbearbeitung in Einkauf und Buchhaltung.",
        intended_users="Fachliche Prueferinnen und Pruefer in der Rechnungsbearbeitung.",
        intended_purpose="Rechnungspositionen klassifizieren und Abweichungen markieren.",
        expected_benefit="Schnellere Vorpruefung und weniger manuelle Routinepruefungen.",
        benefit_category="Prozessqualitaet",
        baseline="Rund 11 Minuten manuelle Pruefzeit je Rechnung.",
        success_criterion="Mindestens 85 Prozent korrekte Markierung typischer Abweichungen.",
        target_value="Pruefzeit um 25 Prozent reduzieren.",
        realized_result=(
            "Pilot erkennt Standardabweichungen verlaesslich; Sonderfaelle benoetigen "
            "Regelanpassung."
        ),
        one_time_cost=Decimal("9500.00"),
        recurring_cost=Decimal("750.00"),
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        solution_type=UseCase.SolutionType.AUTOMATION,
        hosting_type=UseCase.HostingType.INTERNAL,
        provider="Interne Umsetzung",
        product_name="Invoice Check Demo",
        model_name="Dokumentenklassifikation",
        source_systems="ERP, Dokumentenmanagement",
        data_sources="Rechnungsbelege, Bestellungen, Wareneingangsdaten.",
        pilot_start_offset=-65,
        planned_pilot_end_offset=-5,
        privacy_review_required=False,
        security_review_required=True,
        security_review_completed=True,
        human_oversight=(
            "Automatische Hinweise sind Entscheidungsvorlagen; Freigabe bleibt manuell."
        ),
        governance=GovernanceTemplate(
            security_review_required=True,
            result=GovernanceAssessment.Result.COMPLETED,
            rationale="Finanzdaten werden intern verarbeitet; Berechtigungskonzept dokumentiert.",
            evidence_url="https://example.invalid/evidence/demo-rechnungspruefung",
        ),
        reviews=[
            ReviewTemplate(
                -70,
                UseCase.Status.REVIEW,
                UseCase.Status.PILOT,
                Review.Decision.START_PILOT,
                "Datenbasis und Kontrollprozess reichen fuer einen begrenzten Pilot.",
                "Abweichungsregeln nach vier Wochen nachschaerfen.",
                action_due_offset=-35,
                next_review_offset=-10,
            )
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Zusammenfassung von Besprechungen",
        business_unit=f"{DEMO_PREFIX} Kunden- & Serviceprozesse",
        status=UseCase.Status.REVIEW,
        priority=UseCase.Priority.NORMAL,
        next_review_offset=21,
        problem_statement=(
            "Besprechungsnotizen sind uneinheitlich und Nachverfolgung offener Punkte dauert lange."
        ),
        affected_process="Meeting-Nachbereitung",
        target_users="Projektteams und bereichsuebergreifende Arbeitsgruppen.",
        intended_users="Teilnehmende interner Besprechungen.",
        intended_purpose="Transkripte zusammenfassen und offene Punkte strukturiert vorschlagen.",
        expected_benefit="Einheitlichere Protokolle und schnellere Nachbereitung.",
        benefit_category="Zusammenarbeit",
        baseline="Nachbereitung dauert haeufig 20 bis 30 Minuten pro Termin.",
        success_criterion=(
            "Zusammenfassungen werden von Meeting-Leads als fachlich brauchbar bestaetigt."
        ),
        target_value="Nachbereitungszeit halbieren.",
        business_value=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.LOW,
        risk_complexity=UseCase.Level.HIGH,
        solution_type=UseCase.SolutionType.GENERATIVE,
        hosting_type=UseCase.HostingType.EXTERNAL,
        provider="Beispiel Cloud Service",
        product_name="Meeting Summary Demo",
        model_name="Generatives Sprachmodell",
        source_systems="Videokonferenzsystem, Kalender",
        data_sources="Audio-Transkripte und manuell hochgeladene Notizen.",
        privacy_review_required=True,
        security_review_required=True,
        legal_review_required=True,
        human_oversight="Meeting-Leads pruefen Zusammenfassungen vor Weitergabe.",
        governance=GovernanceTemplate(
            personal_data=True,
            employee_data=True,
            external_ai_or_cloud=True,
            generated_external_content=True,
            privacy_review_required=True,
            security_review_required=True,
            legal_review_required=True,
            result=GovernanceAssessment.Result.PRIVACY,
            rationale="Transkripte koennen personenbezogene und vertrauliche Inhalte enthalten.",
            evidence_url="https://example.invalid/evidence/demo-meeting-summary",
            next_assessment_offset=21,
        ),
        reviews=[
            ReviewTemplate(
                -18,
                UseCase.Status.IDEA,
                UseCase.Status.REVIEW,
                Review.Decision.START_REVIEW,
                "Personenbezogene Daten und Cloudverarbeitung muessen vor Pilot geklaert werden.",
                "Datenschutz- und Betriebsratsfragen klaeren.",
                action_due_offset=14,
                next_review_offset=21,
            )
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Klassifikation eingehender Dokumente",
        business_unit=f"{DEMO_PREFIX} Prozesse & Organisation",
        status=UseCase.Status.OPERATION,
        priority=UseCase.Priority.NORMAL,
        next_review_offset=-3,
        problem_statement="Eingehende Dokumente werden manuell an Fachbereiche verteilt.",
        affected_process="Posteingang und Dokumentenrouting",
        target_users="Zentrale Eingangsbearbeitung.",
        intended_users="Sachbearbeitung im Dokumenteneingang.",
        intended_purpose="Dokumentarten erkennen und passende Bearbeitungsschlange vorschlagen.",
        expected_benefit="Weniger Fehlleitungen und schnellere Bearbeitung.",
        benefit_category="Durchlaufzeit",
        baseline="Manuelle Vorsortierung bindet taeglich mehrere Stunden.",
        success_criterion="Mindestens 90 Prozent korrekte Vorschlaege bei Standarddokumenten.",
        target_value="Fehlleitungen um 40 Prozent reduzieren.",
        realized_result="Produktiv; Fehlleitungen in Stichprobe deutlich reduziert.",
        one_time_cost=Decimal("12500.00"),
        recurring_cost=Decimal("900.00"),
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.HIGH,
        risk_complexity=UseCase.Level.LOW,
        solution_type=UseCase.SolutionType.STANDARD,
        hosting_type=UseCase.HostingType.INTERNAL,
        provider="Beispielanbieter",
        product_name="Document Router Demo",
        model_name="Klassifikationsmodell",
        source_systems="Dokumentenmanagement, E-Mail-Postfach",
        data_sources="Historische Dokumenttypen und Routingentscheidungen.",
        security_review_required=True,
        security_review_completed=True,
        human_oversight="Unsichere Faelle werden manuell verteilt.",
        support_responsibility="Dokumentenmanagement-Team prueft Modellberichte quartalsweise.",
        governance=GovernanceTemplate(
            security_review_required=True,
            result=GovernanceAssessment.Result.COMPLETED,
            rationale="Verarbeitung erfolgt intern; Zugriff auf Dokumentklassen ist rollenbasiert.",
            evidence_url="https://example.invalid/evidence/demo-dokumentklassifikation",
        ),
        reviews=[
            ReviewTemplate(
                -95,
                UseCase.Status.PILOT,
                UseCase.Status.OPERATION,
                Review.Decision.GO_LIVE,
                "Qualitaetsziel erreicht, produktiver Betrieb freigegeben.",
                next_review_offset=-3,
            )
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Unterstuetzung bei Kundenanfragen",
        business_unit=f"{DEMO_PREFIX} Kunden- & Serviceprozesse",
        status=UseCase.Status.OPERATION,
        priority=UseCase.Priority.HIGH,
        next_review_offset=45,
        problem_statement=(
            "Antwortvorschlaege fuer wiederkehrende Anfragen werden haeufig neu formuliert."
        ),
        affected_process="Servicekommunikation",
        target_users="Service- und Supportteams.",
        intended_users="Mitarbeitende mit direktem Kundenkontakt.",
        intended_purpose=(
            "Antwortentwuerfe aus freigegebenen Textbausteinen und Wissensartikeln erzeugen."
        ),
        expected_benefit="Schnellere Reaktion und konsistentere Antworten.",
        benefit_category="Servicequalitaet",
        baseline="Durchschnittlich 16 Minuten Bearbeitungszeit je Standardanfrage.",
        success_criterion="Antwortentwuerfe werden in 70 Prozent der Standardfaelle genutzt.",
        target_value="Bearbeitungszeit um 20 Prozent reduzieren.",
        realized_result="Pilot laeuft; Nutzende melden hilfreiche Entwuerfe bei Standardfragen.",
        one_time_cost=Decimal("14500.00"),
        recurring_cost=Decimal("1600.00"),
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.HIGH,
        solution_type=UseCase.SolutionType.GENERATIVE,
        hosting_type=UseCase.HostingType.HYBRID,
        provider="Beispiel Cloud Service",
        product_name="Service Draft Demo",
        model_name="Generatives Sprachmodell",
        source_systems="CRM, Wissensdatenbank",
        data_sources="Kundenanfragen, Textbausteine und Wissensartikel mit Zugriffsbeschraenkung.",
        pilot_start_offset=-30,
        planned_pilot_end_offset=20,
        privacy_review_required=True,
        security_review_required=True,
        legal_review_required=True,
        privacy_review_completed=True,
        security_review_completed=True,
        legal_review_completed=True,
        human_oversight="Antworten werden vor Versand vollstaendig durch Mitarbeitende geprueft.",
        support_responsibility=(
            "Serviceleitung prueft Antwortqualitaet, IT-Support ueberwacht Betrieb."
        ),
        governance=GovernanceTemplate(
            personal_data=True,
            external_ai_or_cloud=True,
            generated_external_content=True,
            privacy_review_required=True,
            security_review_required=True,
            legal_review_required=True,
            result=GovernanceAssessment.Result.LEGAL,
            rationale="Kundenbezug, externe Verarbeitung und generierte externe Kommunikation.",
            evidence_url="https://example.invalid/evidence/demo-kundenanfragen",
            next_assessment_offset=7,
        ),
        reviews=[
            ReviewTemplate(
                -32,
                UseCase.Status.REVIEW,
                UseCase.Status.PILOT,
                Review.Decision.START_PILOT,
                "Pilot mit Vier-Augen-Prinzip und begrenztem Anfrageumfang genehmigt.",
                "Rechtliche Textfreigaben fuer Standardantworten abschliessen.",
                action_due_offset=7,
                next_review_offset=7,
            ),
            ReviewTemplate(
                -5,
                UseCase.Status.PILOT,
                UseCase.Status.OPERATION,
                Review.Decision.GO_LIVE,
                (
                    "Pilotziel wurde knapp verfehlt; produktiver Betrieb wird wegen stabiler "
                    "Entlastung, abgeschlossener Fachpruefungen und verpflichtender Nachmessung "
                    "ausdruecklich als Ausnahme freigegeben."
                ),
                "Nutzenmessung nach 60 Tagen erneut bewerten.",
                action_due_offset=60,
                next_review_offset=45,
                go_live_exception_confirmed=True,
            ),
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Absatz- oder Bedarfsprognose",
        business_unit=f"{DEMO_PREFIX} Daten & Plattformen",
        status=UseCase.Status.REVIEW,
        priority=UseCase.Priority.NORMAL,
        next_review_offset=None,
        problem_statement=(
            "Planungen beruhen stark auf manuellen Schaetzungen und verstreuten Tabellen."
        ),
        affected_process="Planung und Disposition",
        target_users="Planung, Einkauf und Controlling.",
        intended_users="Planungsverantwortliche in Fachbereichen.",
        intended_purpose="Vergangenheitsdaten und Saisonalitaet fuer Prognosevorschlaege nutzen.",
        expected_benefit="Bessere Planbarkeit und weniger kurzfristige Korrekturen.",
        benefit_category="Planungsqualitaet",
        baseline="Planabweichungen werden monatlich manuell analysiert.",
        success_criterion="Prognosefehler sinkt in Pilotdaten gegenueber Tabellenbaseline.",
        target_value="MAPE um 10 Prozentpunkte senken.",
        business_value=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.LOW,
        risk_complexity=UseCase.Level.MEDIUM,
        solution_type=UseCase.SolutionType.ANALYTICS,
        hosting_type=UseCase.HostingType.INTERNAL,
        provider="Interne Umsetzung",
        product_name="Forecast Demo",
        model_name="Zeitreihenmodell",
        source_systems="ERP, Planungstabellen",
        data_sources="Historische Mengen, Kalenderinformationen und aggregierte Planungsdaten.",
        governance=GovernanceTemplate(
            result=GovernanceAssessment.Result.CLARIFICATION,
            rationale=(
                "Datenqualitaet und Verantwortlichkeit fuer Prognosefehler muessen geklaert werden."
            ),
            evidence_url="https://example.invalid/evidence/demo-prognose",
            next_assessment_offset=45,
        ),
        reviews=[
            ReviewTemplate(
                -12,
                UseCase.Status.IDEA,
                UseCase.Status.REVIEW,
                Review.Decision.START_REVIEW,
                "Fachlicher Nutzen plausibel; Datenreife muss bewertet werden.",
                "Datenprofil fuer zwei Jahre erstellen.",
                action_due_offset=20,
            )
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Qualitaetspruefung von Texten",
        business_unit=f"{DEMO_PREFIX} Kunden- & Serviceprozesse",
        status=UseCase.Status.IDEA,
        priority=UseCase.Priority.LOW,
        next_review_offset=28,
        problem_statement=(
            "Fachtexte werden uneinheitlich auf Tonalitaet, Lesbarkeit und Pflichtangaben geprueft."
        ),
        affected_process="Dokumenten- und Kommunikationsfreigabe",
        target_users="Kommunikation, Fachbereiche und Qualitaetssicherung.",
        intended_users="Autorinnen und Autoren interner und externer Texte.",
        intended_purpose="Textqualitaet anhand definierter Kriterien bewerten und Hinweise geben.",
        expected_benefit="Weniger Korrekturschleifen und konsistentere Qualitaet.",
        benefit_category="Qualitaet",
        business_value=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.LOW,
        solution_type=UseCase.SolutionType.ASSISTANT,
        hosting_type=UseCase.HostingType.UNKNOWN,
        provider="Noch offen",
        product_name="Text Quality Demo",
        model_name="Regel- und Sprachmodellkombination",
        source_systems="Manueller Upload",
        data_sources="Beispieltexte und freigegebene Stilregeln.",
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Extraktion von Vertragsinformationen",
        business_unit=f"{DEMO_PREFIX} Prozesse & Organisation",
        status=UseCase.Status.REVIEW,
        priority=UseCase.Priority.CRITICAL,
        next_review_offset=-20,
        problem_statement="Vertragsdaten werden manuell aus umfangreichen Dokumenten uebertragen.",
        affected_process="Vertragsmanagement",
        target_users="Rechtsnahe Fachbereiche und Vertragsmanagement.",
        intended_users="Berechtigte Mitarbeitende im Vertragsmanagement.",
        intended_purpose="Laufzeiten, Fristen und Kernklauseln aus Vertragen vorschlagen.",
        expected_benefit="Fristen werden schneller erkannt und Uebertragungsfehler sinken.",
        benefit_category="Risikoreduktion",
        baseline="Manuelle Erfassung komplexer Vertraege dauert oft mehr als 45 Minuten.",
        success_criterion="Extraktion zentraler Felder erreicht hohe Trefferquote in Stichproben.",
        target_value="Erfassungszeit um 35 Prozent reduzieren.",
        business_value=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.HIGH,
        solution_type=UseCase.SolutionType.GENERATIVE,
        hosting_type=UseCase.HostingType.EXTERNAL,
        provider="Beispiel Cloud Service",
        product_name="Contract Extract Demo",
        model_name="Dokumentenextraktion",
        source_systems="Vertragsarchiv",
        data_sources="Vertraege mit vertraulichen Inhalten und moeglichen personenbezogenen Daten.",
        privacy_review_required=True,
        security_review_required=True,
        legal_review_required=True,
        human_oversight="Extrahierte Inhalte werden nie automatisch uebernommen.",
        governance=GovernanceTemplate(
            personal_data=True,
            external_ai_or_cloud=True,
            legal_review_required=True,
            privacy_review_required=True,
            security_review_required=True,
            result=GovernanceAssessment.Result.LEGAL,
            rationale=(
                "Vertrauliche Vertragsinhalte erfordern rechtliche, Datenschutz- und "
                "Sicherheitsklaerung."
            ),
            evidence_url="https://example.invalid/evidence/demo-vertragsextraktion",
            next_assessment_offset=-20,
        ),
        reviews=[
            ReviewTemplate(
                -40,
                UseCase.Status.IDEA,
                UseCase.Status.REVIEW,
                Review.Decision.START_REVIEW,
                "Potenzial hoch, Risikoanalyse vor Pilot zwingend.",
                "Anbieter- und Auftragsverarbeitungspruefung abschliessen.",
                action_due_offset=-15,
                next_review_offset=-20,
            )
        ],
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Priorisierung interner Anfragen",
        business_unit=f"{DEMO_PREFIX} Daten & Plattformen",
        status=UseCase.Status.IDEA,
        priority=UseCase.Priority.NORMAL,
        next_review_offset=None,
        problem_statement="Interne Anfragen werden uneinheitlich priorisiert und eskaliert.",
        affected_process="Interner Service Desk",
        target_users="Service Desk und interne Fachsupport-Teams.",
        intended_users="Mitarbeitende in internen Supportprozessen.",
        intended_purpose="Anfragen anhand Inhalt und Dringlichkeit vorsortieren.",
        expected_benefit="Schnellere Erstreaktion und transparentere Priorisierung.",
        benefit_category="Servicegeschwindigkeit",
        business_value=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        solution_type=UseCase.SolutionType.AUTOMATION,
        hosting_type=UseCase.HostingType.UNKNOWN,
        provider="Noch offen",
        product_name="Ticket Priority Demo",
        model_name="Klassifikationsmodell",
        source_systems="Ticketsystem",
        data_sources="Historische interne Tickets, Prioritaeten und Bearbeitungszeiten.",
    ),
    UseCaseTemplate(
        title=f"{DEMO_PREFIX} Vorsortierung von Bewerbungsunterlagen",
        business_unit=f"{DEMO_PREFIX} Prozesse & Organisation",
        status=UseCase.Status.ENDED,
        priority=UseCase.Priority.NORMAL,
        next_review_offset=None,
        problem_statement=(
            "Bewerbungsunterlagen sollten automatisch nach formalen Kriterien vorsortiert werden."
        ),
        affected_process="Recruiting",
        target_users="Personalbereich und fachliche Hiring Manager.",
        intended_users="Recruiting-Team.",
        intended_purpose="Bewerbungsunterlagen anhand formaler Kriterien vorsortieren.",
        expected_benefit="Schnellere Bearbeitung hoher Bewerbungsvolumina.",
        benefit_category="Effizienz",
        baseline="Manuelle Sichtung bindet stark schwankend Kapazitaet.",
        success_criterion="Keine Benachteiligung und transparente Kriterien nachweisbar.",
        target_value="Nicht umgesetzt.",
        realized_result="Pilot wurde nach Governance-Bewertung nicht fortgefuehrt.",
        one_time_cost=Decimal("4000.00"),
        recurring_cost=Decimal("0.00"),
        business_value=UseCase.Level.MEDIUM,
        technical_feasibility=UseCase.Level.MEDIUM,
        data_readiness=UseCase.Level.LOW,
        risk_complexity=UseCase.Level.HIGH,
        solution_type=UseCase.SolutionType.ANALYTICS,
        hosting_type=UseCase.HostingType.EXTERNAL,
        provider="Beispiel Cloud Service",
        product_name="Applicant Sorting Demo",
        model_name="Ranking-/Klassifikationsmodell",
        source_systems="Bewerbermanagementsystem",
        data_sources="Bewerbungsunterlagen, Lebenslaeufe und Kommunikationsdaten.",
        actual_end_offset=-25,
        privacy_review_required=True,
        security_review_required=True,
        legal_review_required=True,
        privacy_review_completed=False,
        security_review_completed=False,
        legal_review_completed=False,
        human_oversight="Automatisches Ranking wurde nicht produktiv genutzt.",
        ending_reason="Governance-Risiko fuer automatisierte Personenbewertung zu hoch.",
        final_assessment=(
            "Nicht fortfuehren; Nutzen rechtfertigt die Risiken und Nachweispflichten nicht."
        ),
        lessons_learned=(
            "Recruiting-Use-Cases mit Personenbewertung muessen sehr frueh rechtlich "
            "bewertet werden."
        ),
        data_and_access_handling=(
            "Pilotdaten wurden geloescht, Testzugriffe deaktiviert und Exportdateien entfernt."
        ),
        replacement_solution="Manuelle Checkliste fuer formale Vollstaendigkeit.",
        governance=GovernanceTemplate(
            personal_data=True,
            automated_person_assessment=True,
            influences_person_decisions=True,
            external_ai_or_cloud=True,
            privacy_review_required=True,
            security_review_required=True,
            legal_review_required=True,
            result=GovernanceAssessment.Result.LEGAL,
            rationale=(
                "Bewerbungsdaten und automatisierte Personenbewertung sind besonders risikoreich."
            ),
            evidence_url="https://example.invalid/evidence/demo-bewerbungen",
            next_assessment_offset=None,
        ),
        reviews=[
            ReviewTemplate(
                -55,
                UseCase.Status.REVIEW,
                UseCase.Status.ENDED,
                Review.Decision.END,
                "Automatisierte Personenbewertung wird nach Governance-Pruefung beendet.",
                "Zugaenge deaktivieren und Pilotdaten loeschen.",
                action_due_offset=-30,
                next_review_offset=None,
            )
        ],
    ),
]


def demo_use_case_titles() -> list[str]:
    return [template.title for template in DEMO_USE_CASES]


def demo_usernames() -> list[str]:
    return [user["username"] for user in DEMO_USERS]


def demo_business_unit_names() -> list[str]:
    return [unit["name"] for unit in DEMO_BUSINESS_UNITS]


def _date_from_offset(today, offset: int | None):
    if offset is None:
        return None
    return today + timedelta(days=offset)


@transaction.atomic
def seed_demo_data(*, demo_user_password: str) -> dict[str, int]:
    today = timezone.localdate()
    ensure_groups()

    business_units = {}
    for unit in DEMO_BUSINESS_UNITS:
        business_unit, _ = BusinessUnit.objects.update_or_create(
            name=unit["name"],
            defaults={"description": unit["description"], "is_active": True},
        )
        business_units[unit["name"]] = business_unit

    users = {}
    for user_data in DEMO_USERS:
        username = user_data["username"]
        existing = User.objects.filter(username=username).first()
        if existing and existing.is_superuser:
            users[username] = existing
            continue

        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "email": user_data["email"],
                "business_unit": business_units[user_data["business_unit"]],
                "job_function": user_data["job_function"],
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
                "external_identity_id": f"demo:{username}",
            },
        )
        if created or not user.has_usable_password() or demo_user_password:
            user.set_password(demo_user_password)
            user.save(update_fields=["password"])
        user.groups.set([Group.objects.get(name=user_data["group"])])
        users[username] = user

    coordinator = users["demo_ki_koordinator"]
    owner = users["demo_business_owner"]

    for template in DEMO_USE_CASES:
        use_case, _ = UseCase.objects.update_or_create(
            title=template.title,
            defaults={
                "summary": f"{DEMO_MARKER}: {template.expected_benefit}",
                "problem_statement": template.problem_statement,
                "business_unit": business_units[template.business_unit],
                "affected_process": template.affected_process,
                "target_users": template.target_users,
                "submitter": owner,
                "business_owner": owner,
                "coordinator": coordinator,
                "technical_owner": coordinator
                if template.status == UseCase.Status.OPERATION
                else None,
                "status": template.status,
                "priority": template.priority,
                "next_review_date": _date_from_offset(today, template.next_review_offset),
                "pilot_start": _date_from_offset(today, template.pilot_start_offset),
                "planned_pilot_end": _date_from_offset(today, template.planned_pilot_end_offset),
                "actual_end_date": _date_from_offset(today, template.actual_end_offset),
                "solution_type": template.solution_type,
                "hosting_type": template.hosting_type,
                "provider": template.provider,
                "product_name": template.product_name,
                "model_name": template.model_name,
                "source_systems": template.source_systems,
                "data_sources": template.data_sources,
                "interface_description": f"{DEMO_MARKER}: keine echte Integration.",
                "intended_users": template.intended_users,
                "intended_purpose": template.intended_purpose,
                "expected_benefit": template.expected_benefit,
                "benefit_category": template.benefit_category,
                "baseline": template.baseline,
                "success_criterion": template.success_criterion,
                "target_value": template.target_value,
                "realized_result": template.realized_result,
                "one_time_cost": template.one_time_cost,
                "recurring_cost": template.recurring_cost,
                "business_value": template.business_value,
                "technical_feasibility": template.technical_feasibility,
                "data_readiness": template.data_readiness,
                "risk_complexity": template.risk_complexity,
                "privacy_review_required": template.privacy_review_required,
                "security_review_required": template.security_review_required,
                "legal_review_required": template.legal_review_required,
                "privacy_review_completed": template.privacy_review_completed,
                "security_review_completed": template.security_review_completed,
                "legal_review_completed": template.legal_review_completed,
                "human_oversight": template.human_oversight,
                "support_responsibility": template.support_responsibility,
                "ending_reason": template.ending_reason,
                "final_assessment": template.final_assessment,
                "lessons_learned": template.lessons_learned,
                "data_and_access_handling": template.data_and_access_handling,
                "replacement_solution": template.replacement_solution,
                "is_archived": False,
            },
        )

        if template.governance:
            governance = template.governance
            assessment, _ = GovernanceAssessment.objects.update_or_create(
                use_case=use_case,
                basis_version="DEMO-2026-01",
                defaults={
                    "assessment_date": today - timedelta(days=30),
                    "reviewer": coordinator,
                    "personal_data": governance.personal_data,
                    "employee_data": governance.employee_data,
                    "automated_person_assessment": governance.automated_person_assessment,
                    "influences_person_decisions": governance.influences_person_decisions,
                    "external_ai_or_cloud": governance.external_ai_or_cloud,
                    "generated_external_content": governance.generated_external_content,
                    "human_oversight_planned": governance.human_oversight_planned,
                    "privacy_review_required": governance.privacy_review_required,
                    "security_review_required": governance.security_review_required,
                    "legal_review_required": governance.legal_review_required,
                    "result": governance.result,
                    "rationale": f"{DEMO_MARKER}: {governance.rationale}",
                    "evidence_url": governance.evidence_url,
                    "next_assessment_date": _date_from_offset(
                        today, governance.next_assessment_offset
                    ),
                },
            )
            review_states = (
                (
                    GovernanceReview.ReviewType.PRIVACY,
                    governance.privacy_review_required,
                    template.privacy_review_completed,
                    "Datenschutz",
                ),
                (
                    GovernanceReview.ReviewType.SECURITY,
                    governance.security_review_required,
                    template.security_review_completed,
                    "Informationssicherheit",
                ),
                (
                    GovernanceReview.ReviewType.LEGAL,
                    governance.legal_review_required,
                    template.legal_review_completed,
                    "Recht / Compliance",
                ),
            )
            for review_type, required, completed, responsible_role in review_states:
                status = (
                    GovernanceReview.Status.COMPLETED
                    if completed
                    else (
                        GovernanceReview.Status.OPEN
                        if required
                        else GovernanceReview.Status.NOT_RELEVANT
                    )
                )
                GovernanceReview.objects.update_or_create(
                    use_case=use_case,
                    screening=assessment,
                    review_type=review_type,
                    defaults={
                        "status": status,
                        "reviewed_at": assessment.assessment_date,
                        "reviewer": coordinator,
                        "responsible_role": responsible_role,
                        "result": GovernanceReview.Result.PASSED if completed else "",
                        "rationale": f"{DEMO_MARKER}: {governance.rationale}",
                        "evidence_url": governance.evidence_url if completed else "",
                    },
                )

        for review_template in template.reviews:
            review_date = _date_from_offset(today, review_template.offset)
            Review.objects.update_or_create(
                use_case=use_case,
                review_date=review_date,
                decision=review_template.decision,
                defaults={
                    "reviewer": coordinator,
                    "previous_status": review_template.previous_status,
                    "new_status": review_template.new_status,
                    "rationale": f"{DEMO_MARKER}: {review_template.rationale}",
                    "go_live_exception_confirmed": (review_template.go_live_exception_confirmed),
                    "open_actions": review_template.open_actions,
                    "action_owner": owner if review_template.open_actions else None,
                    "action_due_date": _date_from_offset(today, review_template.action_due_offset),
                    "next_review_date": _date_from_offset(
                        today, review_template.next_review_offset
                    ),
                },
            )

    return {
        "business_units": len(DEMO_BUSINESS_UNITS),
        "users": len(DEMO_USERS),
        "use_cases": len(DEMO_USE_CASES),
        "governance_assessments": GovernanceAssessment.objects.filter(
            use_case__title__in=demo_use_case_titles()
        ).count(),
        "reviews": Review.objects.filter(use_case__title__in=demo_use_case_titles()).count(),
    }


@transaction.atomic
def clear_demo_data() -> dict[str, int]:
    titles = demo_use_case_titles()
    usernames = demo_usernames()
    unit_names = demo_business_unit_names()

    use_cases = UseCase.objects.filter(title__in=titles)
    governance_count = GovernanceAssessment.objects.filter(use_case__in=use_cases).count()
    review_count = Review.objects.filter(use_case__in=use_cases).count()
    use_case_count = use_cases.count()
    use_cases.delete()

    users = User.objects.filter(username__in=usernames, is_superuser=False).exclude(
        owned_use_cases__isnull=False
    )
    user_count = users.count()
    users.delete()

    protected_relations = (
        Q(use_cases__isnull=False)
        | Q(user__isnull=False)
        | Q(use_cases__submitter__isnull=False)
        | Q(use_cases__business_owner__isnull=False)
        | Q(use_cases__coordinator__isnull=False)
        | Q(use_cases__technical_owner__isnull=False)
    )
    business_units = BusinessUnit.objects.filter(name__in=unit_names).exclude(protected_relations)
    business_unit_count = business_units.count()
    business_units.delete()

    return {
        "business_units": business_unit_count,
        "users": user_count,
        "use_cases": use_case_count,
        "governance_assessments": governance_count,
        "reviews": review_count,
    }
