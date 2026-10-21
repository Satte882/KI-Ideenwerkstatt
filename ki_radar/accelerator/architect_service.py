from __future__ import annotations

import hashlib
import json
import logging
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter
from ki_radar.use_cases.idea_discovery import idea_origin_id

from .analysis_service import (
    CaptureAnalysisQuotaExceeded,
    log_capture_analysis,
    mark_capture_analysis_failed,
    reserve_accelerator_quotas,
)
from .architect_contract import (
    DISCOVERY_PROMPT_VERSION,
    DISCOVERY_SCHEMA_VERSION,
    DiscoveryContractError,
    build_discovery_json_schema,
    build_discovery_verifier_schema,
    discovery_methodical_findings,
    discovery_modality_findings,
    enforce_discovery_methodology,
    enforce_discovery_readiness,
    validate_discovery_payload,
    validate_verifier_payload,
)
from .discovery_context import (
    discovery_business_unit_context,
    freeze_legacy_discovery_business_unit,
)
from .investigation_tools import get_discovery_source_snapshot
from .models import CaptureAnalysis, CaptureSession
from .services import get_owned_autonomous_capture_session

logger = logging.getLogger(__name__)
MAX_DISCOVERY_REPAIRS = 3

DISCOVERY_SYSTEM_PROMPT = """Du arbeitest als autonomer Business Architect.
Erzeuge ausschließlich aus dem bereitgestellten Problem, Geschäftskontext, Nutzerkorrekturen
und den autorisierten Quellen einen strukturierten Business-Discovery-Entwurf.
Setze schema_version exakt auf "ap1-discovery-v1".

Regeln:
- Erfinde keine Fakten, Messwerte, Rollen, Systeme oder Prozessschritte.
- Quellenreferenzen dürfen nur die gelieferten Handles U0, S1, S2 ... verwenden.
- U0 steht für Problem, Geschäftskontext und Nutzerkorrekturen. Ordne Aussagen aus
  diesen Eingaben U0 zu, nicht pauschal einer Quelldatei S1/S2. Bei einem Objekt,
  das Aussagen aus U0 und einer Datei kombiniert, nenne beide tragenden Handles.
- Trenne berichtete Fakten, Hypothesen, Unknowns, Clarifications und Widersprüche explizit.
- Ein Widerspruch ist nur zulässig, wenn mindestens zwei unterschiedliche Input-Handles
  einander widersprechende Aussagen tragen; evidence_refs muss dann mindestens diese beiden
  unterschiedlichen Handles enthalten. Mit nur einer tragenden Quelle ist es kein Widerspruch.
- Zahlen in Fakten und Baselines dürfen nur vorkommen, wenn sie im Input tatsächlich genannt sind.
- Der Value Stream ist End-to-End breiter als der vorgeschlagene Process Scope.
- value_stream.scope_in/scope_out beschreiben die Grenze des gesamten Value Streams,
  nicht die engere Process-Analysis-Grenze. Jede aufgeführte Value-Stream-Phase muss
  zur Value-Stream-Grenze und zu ihrem Trigger/Outcome passen.
- scope_out darf keine Tätigkeit nennen, die als Phase im Value Stream enthalten ist.
  Das Outcome endet beim letzten durch Quellen belegten Schritt: Die Vorbereitung
  einer Entscheidung ist nicht die getroffene Entscheidung oder Beauftragung.
  Ergänze nachgelagerte Schritte nur, wenn der autorisierte Input sie ausdrücklich nennt.
- Phasen bilden eine plausible lückenlose Reihenfolge; Unsicherheit bleibt sichtbar.
- Wenn process_analysis.current_flow Phasenschlüssel nennt, müssen diese exakt
  den Schlüsseln und Namen der erzeugten Phasen entsprechen.
- Bewerte für jede Phase Impact, Problemintensität, Verbesserungspotenzial,
  Datenzugänglichkeit und Veränderungsaufwand mit low/medium/high sowie Time-to-Value
  mit unknown/short/medium/long. Diese Werte sind Screening-Einschätzungen, keine Messwerte.
- evidence_basis bewertet die Beschreibung der jeweiligen Phase, nicht ihre
  Screening-Ratings: Direkt in einer autorisierten Quelle berichtete qualitative
  Phasentätigkeit ist indicative, auch ohne Messwert. Nur abgeleitete oder vermutete
  Tätigkeiten sind hypothesis. measured verlangt einen tatsächlichen Messbeleg.
- Die Fokusphase muss zum Problem und zum vollständigen Phasenvergleich passen.
- Lösungsoffen bleiben: keine KI-Lösung, Automatisierung oder Software vorwegnehmen.
- Eine Clarification ist nur blocking=true, wenn Scope/Fokus ohne die Antwort nicht
  verantwortbar entschieden werden kann.
- Leere Detailfelder sind zulässig, wenn der Input nichts Belastbares hergibt.
- Erkenntnisdisziplin gilt für ALLE Freitextfelder, insbesondere focus.rationale,
  bottlenecks, constraints, exceptions, strategische Ziele und Zusammenfassungen:
  Eine beobachtete Suche oder ein Widerspruch belegt keine Ursache, keinen primären
  Engpass und keine fehlende zentrale Plattform. Solche Erklärungen gehören als
  ausdrücklich unbestätigte Möglichkeiten in hypotheses/cause_hypotheses.
  In den übrigen Feldern nur berichtete Beobachtungen und Grenzen beschreiben.
  Auch qualitative Maßnahmenwirkungen wie 'sichert die Informationskette' sind
  ohne Beleg nur bedingte Erwartungen, keine feststehenden Wirkungen.
- Bewahre die Stärke und Modalität der Quelle: eingeschränkte Neueinstellungen
  sind kein Einstellungsverbot; nicht bekannte Kontaktdaten sind keine fehlenden
  Kontaktdaten. Unbekannte Erreichbarkeit ist kein nachgewiesener Bottleneck.
- Ein Zielvorschlag ist als Vorschlag zu kennzeichnen. Qualitative Ratings sind
  vorläufig; begründe keine hohe Relevanz durch erfundene Mengen oder gesicherte Ursachen.
- Process Scope und current_flow beschreiben nur die empfohlene Fokusphase und
  deren belegte Teilschritte, nicht erneut alle Value-Stream-Phasen. Ein unbekannter
  Ist-Ablauf darf als unbekannt stehen bleiben; ergänze stattdessen eine konkrete Frage.
- Ergebnisvorbereitung darf nicht als bereits erreichtes Kundenergebnis erscheinen.
  Bei Partnern explizit zwischen Information, Anfrage, Bestätigung und Vollmacht
  für verbindliche Änderung oder Mehrkosten unterscheiden; fehlende Vollmacht erfragen.
- Ohne tragfähigen Vergleich keine Ursache oder Fokusüberlegenheit behaupten.
  Auch plausible Begründungen wie 'dort entsteht der erste Kundenkontakt' brauchen
  einen berichteten Ablauf; sie folgen nicht aus dem bloßen Namen 'Verkauf'.
  Stelle eine blocking-Frage, wenn konkurrierende Untersuchungsbereiche ohne
  weitere Fakten nicht verantwortbar abgegrenzt werden können.
- Nicht durchgeführte Schritte dürfen nicht als Ist-Handoffs oder erreichte Ergebnisse
  erscheinen. Kennzeichne Vorschläge und mögliche Ausnahmen direkt im jeweiligen Feld,
  etwa 'Möglicher Ausnahmefall, nicht beobachtet'. Ungeprüfte Erreichbarkeit ist eine
  offene Voraussetzung, kein beobachteter Ausfall. Behaupte keinen 'einzigen Weg', wenn
  andere Wege lediglich unbekannt sind.
Gib ausschließlich das verlangte JSON-Objekt zurück."""

VERIFIER_SYSTEM_PROMPT = """Du bist ein unabhängiger Reviewer für einen Business-Discovery-Draft.
Prüfe gegen den vollständigen autorisierten Input und nicht gegen Plausibilität allein.
Setze schema_version exakt auf "ap1-discovery-verifier-v1".

Kritisch sind insbesondere:
- tragende Aussagen ohne Quelle;
- U0 ist der autorisierte Input-Handle für problem_statement, business_context
  und corrections. Diese Feldnamen selbst sind keine zulässigen Evidence-Refs.
- erfundene Zahlen oder Fakten;
- Value-Stream-Grenzen, die nur den Einzelprozess wiederholen;
- scope_out schließt eine aufgeführte Phase aus oder Outcome/Phasen reichen über
  den letzten ausdrücklich berichteten Quellenschritt hinaus;
- unplausible oder lückenhafte Phasenfolge;
- Fokusphase passt nicht zum Problem;
- Process Scope ist nicht enger als der Value Stream oder fachlich unklar;
- Hypothesen werden als Fakten behandelt;
- entscheidungsrelevante Unknowns fehlen;
- Widersprüche zwischen Quellen werden geglättet.
- Prüfe JEDE kausale Aussage auch in Fokusbegründung, Bottleneck, Constraint,
  Ausnahme, Ziel und Zusammenfassung. Eine Hypothesenliste heilt keine daneben
  als Tatsache behauptete Hauptursache. Quelle U0 ist keine pauschale Bestätigung.
  Prüfe auch qualitative Wirkungsversprechen in tradeoffs: 'sichert/gewährleistet'
  braucht einen Beleg oder eine ausdrückliche bedingte Erwartung im selben Satz.
- Prüfe Modalität: aus einem eingeschränkten Können darf kein vollständiges Verbot
  werden; aus nicht bekannten Kontaktdaten kein erwiesenes Fehlen. Bloße plausible
  Zentralisierungs-/Synchronisationsannahmen dürfen kein gesicherter Befund werden.
- Prüfe den konkreten Umfang des Ist-Ablaufs gegen die Fokusphase. Wenn current_flow
  wieder alle Wertstromphasen umfasst, ist scope_quality=false und Repair erforderlich.
- Auch eine plausible Fokusbegründung wie 'hier entsteht der erste Kundenkontakt'
  ist ohne berichteten Ablauf unbelegt. Ein Phasenname ist kein Ablaufbeleg. Bei
  konkurrierenden ungemessenen Bereichen nur einen vorläufigen Untersuchungsbereich
  benennen und die Vergleichsfrage offen halten, keine sachliche Überlegenheit erfinden.
- Prüfe Partner-Vollmacht und Verbindlichkeit von Änderungen als entscheidungsrelevante
  Unbekannte, sofern dazu keine autorisierte Grundlage vorliegt.
- Erstelle intern für JEDEN Satz außerhalb hypotheses/unknowns einen Quellenabgleich:
  berichtet, unbekannt oder bloß vorgeschlagen? Prüfe insbesondere exceptions, handoffs,
  bottlenecks und focus.rationale. Ein nie versuchter Telefonkontakt belegt keinen Ausfall;
  eine mögliche Ausnahme muss im selben Feld als Möglichkeit bezeichnet sein. Ein
  gewünschter Kontakt ist kein bereits ausgeführter Handoff. 'Einziger belegter Weg'
  verlangt den Beleg der Ausschließlichkeit, nicht nur einen bekannten möglichen Weg.
  Konkrete solche Quellüberschreitungen sind grounding-/hypothesis-Findings und zuerst
  zu reparieren, AUCH wenn der Draft außerdem korrekt auf waiting_human enden muss.
  Eine offene Entscheidung erlaubt keine unbelegten Nebenaussagen. Liste alle konkreten
  betroffenen Felder zusammen, damit die begrenzte Reparatur den Zusammenhang korrigiert.
- Die serverseitige Liste evidence_assertions ist die vollständige Prüfliste der
  Textfelder. Prüfe jeden Eintrag gegen den ORIGINAL-Input, einschließlich Nebensätze
  und Voraussetzungen. Melde ALLE unbelegten Aussagen gemeinsam, nicht nur das erste
  auffällige Finding. Ein Quellenhandle oder plausible Touristikpraxis ist kein Beleg.
  Nominale Erklärungen wie Verzögerung durch Mitarbeiterverfügbarkeit sind ebenfalls
  Kausalbehauptungen. Ein gewünschtes strategisches Ziel ist nur ein Zielvorschlag.
  Ein fehlender Ursachenbeleg darf nicht als vorhandener Engpass umgedeutet werden.

Kalibrierung der Checks:
- Fordere keine eigene Phase für bloßes Warten oder einen nur implizierten Übergang,
  wenn die Quellen dort keine fachliche Tätigkeit beschreiben. Erfinde keine Phase,
  um eine formal lückenlose Sequenz zu erzwingen.
- Low/medium/high in Phasenvergleich und Fokus sind vorläufige Screening-Einschätzungen,
  keine gemessenen Fakten. Verlange dafür keine Einzelquelle; prüfe stattdessen, ob
  ihre Begründung zum Problem passt und relevante Unsicherheit sichtbar bleibt.
- Unknowns müssen entscheidungsrelevante Lücken abdecken, nicht jede denkbare
  Detailfrage. Ein vorhandener Unknown ist nicht allein deshalb unzureichend,
  weil sich noch weitere Fragen formulieren ließen.
- Eine direkt durch eine Quelle berichtete Phasenbeschreibung ist qualitativ
  belegt (indicative), auch wenn für die Phase keine Messwerte vorliegen.
- Ein Feld darf einen Vorschlag oder möglichen Ausnahmefall enthalten, wenn die
  Nichtdurchführung bzw. Unsicherheit DIREKT IM FELD unmissverständlich steht.
  'Geplante Kontaktaufnahme (noch nicht durchgeführt)' behauptet keinen vollzogenen
  Handoff und ist kein Grounding-Fehler. Verlange dafür keine neue Fachinformation
  und keine rein redaktionelle weitere Reparatur. Gleiches gilt für ein als möglich
  und nicht beobachtet markiertes Ausfallszenario. Prüfe die Aussage, nicht nur
  ihren Feldnamen; eine korrekte Qualifikation muss nach Repair anerkannt werden.
- Eine ausdrücklich als 'mögliche, unbestätigte Hypothese' bezeichnete Kausalität
  ist kein gesicherter Ursachenbefund und benötigt keinen Beweis als Tatsache.
  Beanstande nicht allein das Vorhandensein kausaler Wörter. 'Ein Engpass ist nicht
  nachgewiesen' behauptet ebenfalls keinen Engpass. Ein Handoff muss nicht formal
  geregelt sein: Eine berichtete gelegentliche Nachfrage belegt einen informellen
  Informationsübergang. Verlange dafür keine zusätzliche formale Prozessvorschrift.
- Markiere nur Findings als kritisch, die Scope, Fokus, Quellenwahrheit oder
  Materialisierung tatsächlich beeinträchtigen. Repair-Anweisungen müssen sich
  auf diese konkreten Findings beschränken.

Status:
- approved: alle sieben Checks sind true und es gibt kein kritisches Finding.
- repair: Draft kann ohne neue menschliche Information gezielt korrigiert werden.
- waiting_human: eine entscheidungskritische Information fehlt; stelle genau die präzise
  fachliche Frage, die Scope/Fokus entscheidet.
- Bei unbelegten Aussagen zuerst repair: entferne oder relativiere sie mit konkreten
  Feldzielen. Fehlen danach erforderliche Fakten, bleibt der reparierte Entwurf offen
  mit gezielter blocking-Clarification und waiting_human. Kein approved bei blocking=true.
Gib ausschließlich das verlangte JSON-Objekt zurück."""

REPAIR_SYSTEM_PROMPT = """Du reparierst einen Business-Discovery-Draft anhand eines unabhängigen
Verifier-Findings oder einer deterministischen serverseitigen Contract-Verletzung. Verwende nur
den ursprünglichen autorisierten Input. Erfinde keine fehlende Information. Setze
schema_version exakt auf "ap1-discovery-v1". Wenn etwas nicht belegt ist, verschiebe es in
Hypothesen/Unknowns oder lasse ein Detailfeld leer. Bei einem Widerspruch müssen mindestens
zwei unterschiedliche Input-Handles die gegensätzlichen Aussagen
tragen; andernfalls entferne den Widerspruch oder ordne die Aussage korrekt als Hypothese/Unknown
ein. U0 ist der autorisierte Handle für problem_statement, business_context und corrections;
die Feldnamen selbst sind keine gültigen Evidence-Refs. Falls ein Verifier-Finding das anders
behauptet, behalte U0 und korrigiere nur die tatsächlich fehlerhafte Quellenzuordnung.
scope_out darf keine aufgeführte Phase ausschließen. Outcome und Phasen dürfen nur bis
zum letzten belegten Quellenschritt reichen; Entscheidungsvorbereitung ist keine
getroffene Entscheidung oder Beauftragung.
Für evidence_basis gilt: direkt berichtete qualitative Phasentätigkeit = indicative;
nur abgeleitete Tätigkeit = hypothesis; measured nur mit Messbeleg. Die Einschätzung
bezieht sich auf die Phasenbeschreibung, nicht auf low/medium/high-Screening-Ratings.
Repariere den gesamten fachlich betroffenen Zusammenhang: eine unbelegte Kausalität
aus Fakten, Fokusbegründung, Bottleneck, Constraints und Empfehlungen entfernen;
nur als unbestätigte Hypothese erhalten. Erfinde keine Bestätigung. Bewahre Modalität
und Quellenwidersprüche. Grenze current_flow auf die Fokusphase ein. Fehlende Fakten
als konkrete Clarification mit blocking=true führen, wenn sie Scope/Fokus verhindern.
Ohne neue Fakten ist eine begründete offene Entscheidung das korrekte Ergebnis.
Prüfe nach der Korrektur auch exceptions, handoffs und focus.rationale: mögliche Ausfälle
als nicht beobachtete Möglichkeiten, geplante Kontakte als Vorschläge formulieren. Keine
Exklusivität eines Klärweges ohne Beleg. Ungeprüfte Voraussetzungen bleiben unbekannt.
Prüfe zusätzlich jedes Textfeld selbst erneut am ORIGINAL-Input, auch wenn das Finding
nur ein anderes Feld nennt. Entferne plausible, aber nicht berichtete Arbeitsschritte,
Nacharbeiten und Personalvorgaben. Ersetze erfundene Ist-Details durch 'Unbekannt' und
eine konkrete Frage; vermutete Phasen als hypothesis kennzeichnen. Zielvorschläge
ausdrücklich benennen. Eine zweite begrenzte Korrektur darf keine neuen Tatsachen einführen.
Der bisherige Draft ist keine Evidenz. Im ersten Repair werden nur Gliederung
und Findings mitgegeben; im späteren gezielten Repair dient edit_base lediglich
als unveränderliche Bearbeitungsbasis, nicht als Quelle. Rekonstruiere Fakten aus input und
den dort berichteten Tätigkeiten. Die Findings erklären, welche Fehlschlüsse zu
vermeiden sind. Prüfe auch nicht beanstandete Felder neu: Ziele als Zielvorschlag,
vermutete Tätigkeit als hypothesis, fehlende Abläufe als unbekannt und noch nicht
berichtete Ausnahmefälle nur ausdrücklich als möglich. Trade-offs dürfen keine
unbelegte mangelhafte Dokumentation oder andere Ursache voraussetzen.
untrusted_proposal_outline enthält nur bisherige Phasennamen und die Fokusreferenz,
keine fachlichen Fakten. Bewahre diese Gliederung bei einer reinen Text-/Evidenzkorrektur,
wenn die Quellen sie tragen. Insbesondere darf eine reparierte enge Fokusphase nicht
versehentlich wieder mit dem ganzen Wertstrom verschmelzen. Bei einem Scope-Finding
darfst du die Gliederung quellengebunden korrigieren; erfundene Tätigkeiten bleiben
auch dort unzulässig. Wiederhole nie den ganzen Wertstrom als fokussierten Ist-Prozess.
Wenn edit_base und allowed_field_paths vorliegen, ändere ausschließlich diese
Textfelder. Alle übrigen Werte bleiben exakt erhalten. previous_findings sind
bereits erkannte Fehler: Führe diese beim Beheben eines anderen Felds nie wieder ein.
Gib den vollständigen korrigierten Draft im verlangten JSON-Schema zurück."""


class DiscoveryAnalysisError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _usage_int(result: OpenRouterResult, key: str) -> int:
    value = result.usage.get(key)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _usage_cost(result: OpenRouterResult) -> Decimal:
    value = result.usage.get("cost")
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _source_document(*, session: CaptureSession, snapshot) -> tuple[dict[str, Any], set[str], str]:
    problem = str(session.answers.get("problem_statement") or "").strip()
    business_context = str(session.answers.get("business_context") or "").strip()
    corrections = [
        str(item.get("text") or "").strip()
        for item in list(session.answers.get("corrections") or [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    sources = []
    allowed_refs = {"U0"}
    evidence_parts = [problem, business_context, *corrections]
    origin = session.answers.get("origin") or {}
    has_idea_origin = idea_origin_id(session.answers) is not None
    for source in snapshot.sources.order_by("filename", "id"):
        # The managed idea source freezes U0; it is not independent corroboration.
        if (
            has_idea_origin
            and source.filename == origin.get("origin_source_filename")
            and source.content_sha256 == origin.get("origin_source_sha256")
        ):
            continue
        ref = f"S{len(sources) + 1}"
        allowed_refs.add(ref)
        evidence_parts.append(source.content)
        sources.append(
            {
                "ref": ref,
                "filename": source.filename,
                "source_type": source.source_type,
                "content_sha256": source.content_sha256,
                "row_count": source.row_count,
                "columns": list(source.columns),
                "content": source.content,
            }
        )
    document = {
        "input_ref": "U0",
        "capture_session_id": str(session.pk),
        "capture_revision": session.revision,
        "business_unit": discovery_business_unit_context(session)["name"],
        "problem_statement": problem,
        "business_context": business_context,
        "corrections": corrections,
        "sources": sources,
    }
    return document, allowed_refs, "\n".join(evidence_parts)


def _decode_json(result: OpenRouterResult, *, code: str) -> dict[str, Any]:
    if result.finish_reason == "length":
        raise DiscoveryAnalysisError(
            "Die strukturierte Discovery-Antwort wurde am Ausgabelimit abgeschnitten.",
            code="output_truncated",
        )
    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        raise DiscoveryAnalysisError(
            "Der Provider lieferte kein gültiges JSON-Objekt.",
            code=code,
        ) from exc
    if not isinstance(payload, dict):
        raise DiscoveryAnalysisError(
            "Der Provider lieferte kein JSON-Objekt.",
            code=code,
        )
    return payload


def _provider_call(
    *,
    actor,
    session: CaptureSession,
    policy,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict[str, Any],
) -> OpenRouterResult:
    # A timed-out provider response has no usable draft. Investigation already
    # allows one transport retry; keep the same bounded rule for Discovery.
    for attempt in range(2):
        try:
            reserve_accelerator_quotas(
                actor=actor,
                session=session,
                policy=policy,
                include_context=False,
            )
            return request_openrouter(
                messages=messages,
                max_tokens=policy.capture_max_output_tokens,
                timeout_seconds=policy.timeout_seconds,
                temperature=policy.capture_temperature,
                reasoning_effort="high" if "verifier" in schema_name else "medium",
                model_override=settings.ACCELERATOR_DISCOVERY_MODEL or None,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
                provider={"require_parameters": True, "sort": "throughput"},
            )
        except OpenRouterUnavailable as exc:
            if exc.code == "timeout" and attempt == 0:
                logger.warning("discovery_provider_retry schema=%s code=timeout", schema_name)
                continue
            raise DiscoveryAnalysisError(str(exc), code=exc.code) from exc
        except CaptureAnalysisQuotaExceeded as exc:
            raise DiscoveryAnalysisError(str(exc), code=exc.code) from exc
    raise AssertionError("Discovery-Provider-Retry-Budget wurde unerwartet überschritten.")


def _prompt_payload(system_prompt: str, document: dict[str, Any]) -> list[dict[str, str]]:
    if system_prompt == REPAIR_SYSTEM_PROMPT:
        previous = document.get("draft") or {}
        phases = previous.get("stages") or []
        if not isinstance(phases, list):
            phases = []
        focus = previous.get("focus") or {}
        if not isinstance(focus, dict):
            focus = {}
        outline = {
            "stages": [
                {"key": stage.get("key"), "name": stage.get("name")}
                for stage in phases
                if isinstance(stage, dict)
            ],
            "recommended_stage_key": focus.get("recommended_stage_key"),
        }
        document = {key: value for key, value in document.items() if key != "draft"}
        document["untrusted_proposal_outline"] = outline
    if system_prompt == VERIFIER_SYSTEM_PROMPT and isinstance(document.get("draft"), dict):
        document = {
            **document,
            "evidence_assertions": _evidence_assertions(document["draft"]),
            "server_methodical_findings": (
                *discovery_methodical_findings(document["draft"]),
                *discovery_modality_findings(
                    document["draft"], json.dumps(document.get("input", {}), ensure_ascii=False)
                ),
            ),
        }
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _evidence_assertions(draft: dict) -> list[dict]:
    """Expose nested claims to the existing reviewer; never treat a handle as proof."""
    assertions = []

    def walk(value, path="", refs=()):
        if isinstance(value, dict):
            refs = value.get("evidence_refs", refs)
            for name, child in value.items():
                if name not in {"evidence_refs", "schema_version", "key"}:
                    walk(child, f"{path}.{name}" if path else name, refs)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", refs)
        elif isinstance(value, str):
            # Resolve the complete text in draft without duplicating long fields.
            assertions.append({"field": path, "evidence_refs": refs})

    walk(draft)
    return assertions


def _input_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(message["content"]) for message in messages)


def _repair_field_targets(draft: dict, verifier: dict) -> tuple[str, ...]:
    """Only patch fields explicitly named in every finding; never guess targets."""
    fields = [item["field"] for item in _evidence_assertions(draft)]
    targets = set()
    for finding in verifier.get("critical_findings", []):
        if not isinstance(finding, dict):
            return ()
        message = str(finding.get("message") or "")
        matched = {
            path for path in fields if re.search(rf"(?<![\w.]){re.escape(path)}(?![\w.])", message)
        }
        if not matched:
            return ()
        targets.update(matched)
    return tuple(sorted(targets))


def _apply_discovery_field_repair(base: dict, proposal: dict, targets: tuple[str, ...]) -> dict:
    revised = deepcopy(base)
    for path in targets:
        parts = re.findall(r"[^.\[\]]+", path)
        old, new = revised, proposal
        try:
            for part in parts[:-1]:
                old = old[int(part)] if isinstance(old, list) else old[part]
                new = new[int(part)] if isinstance(new, list) else new[part]
            key = int(parts[-1]) if isinstance(old, list) else parts[-1]
            value = new[key]
            if not isinstance(value, str):
                raise TypeError(path)
            old[key] = value
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DiscoveryContractError([f"{path}: Ziel des gezielten Repairs fehlt."]) from exc
    return revised


def _analysis_source_hash(snapshot, session: CaptureSession) -> str:
    return hashlib.sha256(f"{snapshot.manifest_hash}:{session.revision}".encode()).hexdigest()


def _store_terminal_analysis(
    *,
    analysis_id,
    status: str,
    draft: dict[str, Any],
    verifier: dict[str, Any],
    source_labels: dict[str, str],
    snapshot_id,
    results: list[OpenRouterResult],
    review_history: list | None = None,
) -> CaptureAnalysis:
    with transaction.atomic():
        analysis = CaptureAnalysis.objects.select_for_update().get(pk=analysis_id)
        if analysis.status != CaptureAnalysis.Status.RUNNING:
            raise DiscoveryAnalysisError(
                "Der Discovery-Lauf ist nicht mehr offen.",
                code="analysis_not_running",
            )
        finished_at = timezone.now()
        analysis.status = status
        analysis.finished_at = finished_at
        analysis.duration_ms = max(
            0,
            round((finished_at - analysis.started_at).total_seconds() * 1000),
        )
        analysis.model_name = results[-1].model if results else ""
        analysis.output_chars = sum(result.output_chars for result in results)
        analysis.prompt_tokens = sum(_usage_int(result, "prompt_tokens") for result in results)
        analysis.completion_tokens = sum(
            _usage_int(result, "completion_tokens") for result in results
        )
        analysis.total_tokens = sum(_usage_int(result, "total_tokens") for result in results)
        analysis.cost = sum((_usage_cost(result) for result in results), Decimal("0"))
        analysis.open_questions = list(draft.get("clarifications") or [])
        analysis.contradictions = list(draft.get("contradictions") or [])
        analysis.result_payload = {
            "draft": draft,
            "review_history": review_history or [],
            "source_labels": source_labels,
            "discovery_snapshot_id": str(snapshot_id),
        }
        analysis.verification_payload = verifier
        analysis.error_code = ""
        analysis.save(
            update_fields=[
                "status",
                "finished_at",
                "duration_ms",
                "model_name",
                "output_chars",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cost",
                "open_questions",
                "contradictions",
                "result_payload",
                "verification_payload",
                "error_code",
                "updated_at",
            ]
        )
    log_capture_analysis(analysis, purpose="autonomous_business_discovery")
    return analysis


def _store_failure_diagnostics(
    *,
    analysis_id,
    draft: dict[str, Any],
    verifier: dict[str, Any],
    snapshot_id,
    review_history: list | None = None,
) -> None:
    """Persist the last validated draft/reviewer finding before fail-closed termination."""
    with transaction.atomic():
        analysis = CaptureAnalysis.objects.select_for_update().get(pk=analysis_id)
        if analysis.status != CaptureAnalysis.Status.RUNNING:
            return
        analysis.open_questions = list(draft.get("clarifications") or [])
        analysis.contradictions = list(draft.get("contradictions") or [])
        analysis.result_payload = {
            "draft": draft,
            "review_history": review_history or [],
            "discovery_snapshot_id": str(snapshot_id),
        }
        analysis.verification_payload = verifier
        analysis.save(
            update_fields=[
                "open_questions",
                "contradictions",
                "result_payload",
                "verification_payload",
                "updated_at",
            ]
        )


@sensitive_variables(
    "document",
    "producer_messages",
    "repair_document",
    "messages",
    "draft",
    "producer_payload",
    "review_history",
    "contract_errors",
    "verifier",
)
def execute_autonomous_business_discovery(
    *,
    actor,
    session_id,
    snapshot_id,
) -> CaptureAnalysis:
    session = get_owned_autonomous_capture_session(actor=actor, session_id=session_id)
    if session.status != CaptureSession.Status.DRAFT:
        raise PermissionDenied("Die autonome Discovery ist nicht mehr bearbeitbar.")
    try:
        freeze_legacy_discovery_business_unit(session)
    except ValidationError as exc:
        raise DiscoveryAnalysisError(
            " ".join(exc.messages),
            code="missing_business_unit",
        ) from exc

    snapshot = get_discovery_source_snapshot(actor=actor, snapshot_id=snapshot_id)
    if snapshot.capture_session_id != session.pk:
        raise PermissionDenied("Der Discovery-Snapshot gehört nicht zu dieser Erfassung.")

    try:
        policy = get_accelerator_llm_policy()
    except LLMConfigurationError as exc:
        raise DiscoveryAnalysisError(str(exc), code="invalid_configuration") from exc

    document, allowed_refs, evidence_text = _source_document(session=session, snapshot=snapshot)
    producer_messages = _prompt_payload(DISCOVERY_SYSTEM_PROMPT, document)
    chars = _input_chars(producer_messages)
    if chars > policy.discovery_max_input_chars:
        raise DiscoveryAnalysisError(
            "Die autorisierten Quellen überschreiten das Discovery-Eingabelimit. "
            "Bitte den Quellenraum auf die entscheidungsrelevanten Dateien begrenzen.",
            code="source_pack_too_large",
        )

    source_hash = _analysis_source_hash(snapshot, session)
    try:
        analysis = CaptureAnalysis.objects.create(
            session=session,
            requested_by=actor,
            source_revision=session.revision,
            source_hash=source_hash,
            capture_type=session.capture_type,
            catalog_version=session.catalog_version,
            answer_schema_version=session.schema_version,
            prompt_version=DISCOVERY_PROMPT_VERSION,
            extraction_schema_version=DISCOVERY_SCHEMA_VERSION,
            input_chars=chars,
        )
    except IntegrityError as exc:
        raise DiscoveryAnalysisError(
            "Für diesen unveränderten Discovery-Stand läuft bereits eine Analyse.",
            code="analysis_already_running",
        ) from exc

    results: list[OpenRouterResult] = []
    last_result: OpenRouterResult | None = None
    try:
        producer = _provider_call(
            actor=actor,
            session=session,
            policy=policy,
            messages=producer_messages,
            schema_name="autonomous_business_discovery_v1",
            schema=build_discovery_json_schema(),
        )
        results.append(producer)
        last_result = producer
        producer_payload = _decode_json(producer, code="invalid_discovery_response")
        repair_count = 0
        review_history = []
        incoming_repair = None
        while True:
            contract_errors = []
            try:
                draft = validate_discovery_payload(
                    producer_payload, allowed_refs=allowed_refs, evidence_text=evidence_text
                )
            except DiscoveryContractError as exc:
                draft = producer_payload
                contract_errors = list(exc.errors)

            semantic_review = not contract_errors or bool(
                discovery_methodical_findings(draft)
                or discovery_modality_findings(draft, evidence_text)
            )
            if semantic_review:
                messages = _prompt_payload(
                    VERIFIER_SYSTEM_PROMPT, {"input": document, "draft": draft}
                )
                if _input_chars(messages) > policy.discovery_max_input_chars:
                    raise DiscoveryAnalysisError(
                        "Der Discovery-Draft überschreitet zusammen mit den Quellen "
                        "das Verifier-Limit.",
                        code="verifier_input_too_large",
                    )
                result = _provider_call(
                    actor=actor,
                    session=session,
                    policy=policy,
                    messages=messages,
                    schema_name="autonomous_business_discovery_verifier_v1",
                    schema=build_discovery_verifier_schema(),
                )
                results.append(result)
                last_result = result
                verifier = enforce_discovery_methodology(
                    draft,
                    validate_verifier_payload(
                        _decode_json(result, code="invalid_verifier_response")
                    ),
                )
            else:
                verifier = {
                    "schema_version": "ap1-discovery-verifier-v1",
                    "status": "repair",
                    "checks": {},
                    "critical_findings": [],
                    "repair_instructions": "",
                    "human_question": "",
                }
            if contract_errors:
                verifier = {
                    **verifier,
                    "status": "repair",
                    "human_question": "",
                    "critical_findings": verifier["critical_findings"]
                    + [
                        {"code": "discovery_contract", "message": error}
                        for error in contract_errors
                    ],
                    "repair_instructions": "\n".join(
                        [verifier["repair_instructions"], *contract_errors]
                    ),
                }
            review_history.append(
                {
                    "repair_count": repair_count,
                    "draft": draft,
                    "contract_errors": contract_errors,
                    "verifier": verifier,
                    "incoming_repair": incoming_repair,
                }
            )
            _store_failure_diagnostics(
                analysis_id=analysis.pk,
                draft=draft,
                verifier=verifier,
                snapshot_id=snapshot.pk,
                review_history=review_history,
            )
            if verifier["status"] != "repair":
                break
            if repair_count >= MAX_DISCOVERY_REPAIRS:
                raise DiscoveryAnalysisError(
                    "Der Discovery-Draft konvergiert nach den begrenzten Repairs nicht.",
                    code="verification_not_converged",
                )
            repair_document = {"input": document, "draft": draft, "verifier": verifier}
            repair_document["previous_findings"] = [
                finding
                for step in review_history
                for finding in step["verifier"]["critical_findings"]
            ]
            targets = _repair_field_targets(draft, verifier)
            if targets:
                repair_document["edit_base"] = draft
                repair_document["allowed_field_paths"] = targets
            if contract_errors:
                repair_document["contract_errors"] = contract_errors
            messages = _prompt_payload(REPAIR_SYSTEM_PROMPT, repair_document)
            if _input_chars(messages) > policy.discovery_max_input_chars:
                raise DiscoveryAnalysisError(
                    "Der gezielte Discovery-Repair überschreitet das Eingabelimit.",
                    code="repair_input_too_large",
                )
            result = _provider_call(
                actor=actor,
                session=session,
                policy=policy,
                messages=messages,
                schema_name="autonomous_business_discovery_repair_v1",
                schema=build_discovery_json_schema(),
            )
            results.append(result)
            last_result = result
            proposal = _decode_json(result, code="invalid_repair_response")
            producer_payload = (
                _apply_discovery_field_repair(draft, proposal, targets) if targets else proposal
            )
            incoming_repair = {"allowed_fields": targets, "raw_proposal": proposal}
            repair_count += 1

        verifier = enforce_discovery_readiness(draft, verifier)
        source_labels = {"U0": "Problem, Kontext und Nutzerkorrekturen"}
        for source in document["sources"]:
            source_labels[source["ref"]] = source["filename"]

        status = (
            CaptureAnalysis.Status.SUCCESS
            if verifier["status"] == "approved"
            else CaptureAnalysis.Status.WAITING_HUMAN
        )
        return _store_terminal_analysis(
            analysis_id=analysis.pk,
            status=status,
            draft=draft,
            verifier=verifier,
            source_labels=source_labels,
            snapshot_id=snapshot.pk,
            results=results,
            review_history=review_history,
        )
    except DiscoveryContractError as exc:
        mark_capture_analysis_failed(
            analysis_id=analysis.pk,
            error_code="invalid_discovery_contract",
            result=last_result,
        )
        raise DiscoveryAnalysisError(
            "Die Discovery-Antwort hat die serverseitige Vertragsprüfung nicht bestanden.",
            code="invalid_discovery_contract",
        ) from exc
    except DiscoveryAnalysisError as exc:
        mark_capture_analysis_failed(
            analysis_id=analysis.pk,
            error_code=exc.code,
            result=last_result,
        )
        raise
