from __future__ import annotations

import hashlib
import json
import re
import secrets
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .investigation_brief import preview_decision_brief_materialization
from .investigation_models import InvestigationRun
from .investigation_policy import PolicyOutcome
from .investigation_presentation import build_decision_surface
from .investigation_runtime import InvestigationRunError, evaluate_run_policy

EXPECTED_SLOTS = frozenset(
    (variant, attempt) for variant in ("A", "B", "C") for attempt in range(1, 4)
)

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_HASH_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
_SCENARIO_RE = re.compile(r"\b(Fall|Variante|Variant|Case)\s+([ABC])\b", re.IGNORECASE)
_BENCHMARK_SLOT_RE = re.compile(r"\b[ABC]/(?:adaptive|fixed)/\d+\b", re.IGNORECASE)
_PROJECT_MARKER_RE = re.compile(
    r"\bVS1\s*/\s*#?4\b|\bIssue\s*#?4\b",
    re.IGNORECASE,
)
_LOCAL_URL_RE = re.compile(r"https?://(?:127\.0\.0\.1|localhost)(?::\d+)?/\S*", re.IGNORECASE)
_BENCHMARK_WORD_RE = re.compile(r"\b(?:PASS|FAIL|scored|adaptive|benchmark|attempt)\b", re.IGNORECASE)


class BlindReviewPackageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewSource:
    alias: str
    source_type: str
    content: str
    original_filename: str


def _as_text(value: object) -> str:
    return str(value or "").strip()


def _slot_for_run(run: Any) -> tuple[str, int] | None:
    metadata = run.evidence_metadata if isinstance(run.evidence_metadata, Mapping) else {}
    if str(getattr(run, "execution_mode", "")) != "adaptive":
        return None
    if str(metadata.get("provider_mode") or "") != "real":
        return None
    if str(metadata.get("phase") or "") != "scored":
        return None
    variant = str(metadata.get("variant") or "").upper()
    try:
        attempt = int(metadata.get("attempt"))
    except (TypeError, ValueError):
        return None
    slot = (variant, attempt)
    return slot if slot in EXPECTED_SLOTS else None


def select_scored_adaptive_runs(runs: Iterable[Any]) -> dict[tuple[str, int], Any]:
    selected: dict[tuple[str, int], Any] = {}
    for run in runs:
        slot = _slot_for_run(run)
        if slot is None:
            continue
        if slot in selected:
            raise BlindReviewPackageError(
                f"Scored-Slot {slot[0]}/{slot[1]} ist mehrfach vorhanden."
            )
        selected[slot] = run

    missing = sorted(EXPECTED_SLOTS - set(selected))
    extra = sorted(set(selected) - EXPECTED_SLOTS)
    if missing or extra or len(selected) != 9:
        details: list[str] = []
        if missing:
            details.append(
                "fehlend=" + ",".join(f"{variant}/{attempt}" for variant, attempt in missing)
            )
        if extra:
            details.append(
                "unerwartet=" + ",".join(f"{variant}/{attempt}" for variant, attempt in extra)
            )
        raise BlindReviewPackageError(
            "Die eingefrorene Adaptive-Scored-Stichprobe ist nicht exakt 9/9"
            + (": " + "; ".join(details) if details else ".")
        )
    return selected


def deterministic_review_order(
    slots: Iterable[tuple[str, int]],
    *,
    seed: str,
) -> list[tuple[str, int]]:
    seed = seed.strip()
    if not seed:
        raise BlindReviewPackageError("Der Randomisierungs-Seed darf nicht leer sein.")

    def rank(slot: tuple[str, int]) -> str:
        raw = f"{seed}:{slot[0]}:{slot[1]}".encode()
        return hashlib.sha256(raw).hexdigest()

    return sorted(slots, key=rank)


def _replace_scenario_label(match: re.Match[str]) -> str:
    noun = match.group(1)
    lowered = noun.casefold()
    if lowered == "fall":
        return "dieser Fall"
    if lowered == "variante":
        return "diese Variante"
    if lowered == "variant":
        return "this variant"
    return "this case"


def redact_blinding_metadata(
    text: str,
    *,
    exact_tokens: Iterable[str] = (),
) -> tuple[str, dict[str, int]]:
    output = text
    counts: dict[str, int] = {}

    normalized_tokens = {_as_text(item) for item in exact_tokens if _as_text(item)}
    for token in sorted(normalized_tokens, key=len, reverse=True):
        occurrences = output.count(token)
        if occurrences:
            output = output.replace(token, "[redigiert]")
            counts["exact_identifier"] = counts.get("exact_identifier", 0) + occurrences

    substitutions = (
        ("scenario_label", _SCENARIO_RE, _replace_scenario_label),
        ("benchmark_slot", _BENCHMARK_SLOT_RE, "[redigierte Zuordnung]"),
        ("project_marker", _PROJECT_MARKER_RE, "Neutraler Evidenzfall"),
        ("local_url", _LOCAL_URL_RE, "[lokaler Link entfernt]"),
        ("uuid", _UUID_RE, "[redigierte ID]"),
        ("hash", _HASH_RE, "[redigierter Hash]"),
    )
    for name, pattern, replacement in substitutions:
        output, replaced = pattern.subn(replacement, output)
        if replaced:
            counts[name] = counts.get(name, 0) + replaced

    return output, counts


def find_blinding_leaks(text: str, *, exact_tokens: Iterable[str] = ()) -> list[str]:
    leaks: list[str] = []
    checks = (
        ("UUID", _UUID_RE),
        ("64-Zeichen-Hash", _HASH_RE),
        ("A/B/C-Szenariolabel", _SCENARIO_RE),
        ("Benchmark-Slot", _BENCHMARK_SLOT_RE),
        ("Projekt-/Issue-Marker", _PROJECT_MARKER_RE),
        ("lokale URL", _LOCAL_URL_RE),
        ("Benchmark-Metadatenwort", _BENCHMARK_WORD_RE),
    )
    for label, pattern in checks:
        if pattern.search(text):
            leaks.append(label)
    for token in {_as_text(item) for item in exact_tokens if _as_text(item)}:
        if token in text:
            leaks.append("exakter interner Identifier")
            break
    return sorted(set(leaks))


def qualify_decision_surface(
    *,
    run_status: str,
    clarification_reason: str,
    surface: Mapping[str, Any],
) -> None:
    status_label = _as_text(surface.get("status_label"))
    status_detail = _as_text(surface.get("status_detail"))
    recommendation = _as_text(surface.get("recommendation_summary"))
    finding = _as_text(surface.get("finding"))

    if not status_label or not status_detail:
        raise BlindReviewPackageError("Die Human Surface besitzt keinen eindeutigen Status.")

    if run_status == InvestigationRun.Status.FAILED:
        if "fehlgeschlagen" not in status_label.casefold():
            raise BlindReviewPackageError("FAILED wird in der Human Surface nicht sicher markiert.")
        if "kein fachlicher schluss" not in status_detail.casefold():
            raise BlindReviewPackageError(
                "FAILED sperrt die fachliche Schlussfolgerung in der Human Surface nicht eindeutig."
            )
        if "keine belastbare empfehlung" not in recommendation.casefold():
            raise BlindReviewPackageError("FAILED zeigt eine belastbare Empfehlung an.")

    if clarification_reason == "missing_evidence" and run_status in {
        InvestigationRun.Status.ABORTED,
        InvestigationRun.Status.WAITING_HUMAN,
    }:
        if (
            "nachweis fehlt" not in finding.casefold()
            and "information" not in finding.casefold()
        ):
            raise BlindReviewPackageError(
                "Missing Evidence ist in der Human Surface nicht als Lücke erkennbar."
            )
        if "keine belastbare empfehlung" not in recommendation.casefold():
            raise BlindReviewPackageError(
                "Missing Evidence zeigt fälschlich eine belastbare Empfehlung an."
            )


def _surface_for_run(run: InvestigationRun) -> dict[str, Any]:
    policy = evaluate_run_policy(run)
    latest_materialization = run.materializations.select_related("brief_revision").first()
    materialization_preview = None
    if (
        run.status == InvestigationRun.Status.READY
        and policy.outcome == PolicyOutcome.READY_FOR_DECISION
        and latest_materialization is None
    ):
        try:
            materialization_preview = preview_decision_brief_materialization(
                actor=run.evidence_campaign.authorized_by,
                run_id=run.pk,
            )
        except InvestigationRunError:
            materialization_preview = None

    surface = build_decision_surface(
        run=run,
        policy=policy,
        latest_materialization=latest_materialization,
        materialization_preview=materialization_preview,
    )
    qualify_decision_surface(
        run_status=run.status,
        clarification_reason=run.clarification_reason,
        surface=surface,
    )
    return surface


def _review_sources(run: InvestigationRun) -> list[ReviewSource]:
    sources: list[ReviewSource] = []
    text_index = 0
    csv_index = 0
    for source in run.source_snapshot.sources.order_by("filename", "id"):
        if source.source_type == "csv":
            csv_index += 1
            alias = f"Datensatz {csv_index}"
        else:
            text_index += 1
            alias = f"Quelle {text_index}"
        sources.append(
            ReviewSource(
                alias=alias,
                source_type=source.source_type,
                content=source.content,
                original_filename=source.filename,
            )
        )
    return sources


def _append_if(lines: list[str], heading: str, value: object) -> None:
    text = _as_text(value)
    if text:
        lines.extend([heading, "", text, ""])


def render_review_case(
    *,
    review_code: str,
    surface: Mapping[str, Any],
    sources: Iterable[ReviewSource],
) -> str:
    lines = [
        f"# Anonymisierte Entscheidungsgrundlage {review_code}",
        "",
        f"**{_as_text(surface.get('status_label'))}**",
        "",
        _as_text(surface.get("status_detail")),
        "",
        "## 1 · Situation",
        "",
        _as_text(surface.get("situation")),
        "",
    ]
    scope = _as_text(surface.get("scope"))
    if scope:
        lines.extend([scope, ""])

    lines.extend(
        [
            "## 2 · Wichtigster Befund",
            "",
            _as_text(surface.get("finding")),
            "",
            "## 3 · Empfehlung",
            "",
            _as_text(surface.get("recommendation_summary")),
            "",
        ]
    )
    rationale = _as_text(surface.get("recommendation_rationale"))
    if rationale:
        lines.extend(["### Begründung", "", rationale, ""])

    risks = [_as_text(item) for item in surface.get("risks", []) if _as_text(item)]
    if risks:
        lines.extend(["### Grenzen und offene Punkte", ""])
        lines.extend(f"- {item}" for item in risks)
        lines.append("")

    next_action = (
        surface.get("next_action")
        if isinstance(surface.get("next_action"), Mapping)
        else {}
    )
    lines.extend(
        [
            "## 4 · Nächster Schritt",
            "",
            f"**{_as_text(next_action.get('title'))}**",
            "",
            _as_text(next_action.get("description")),
            "",
        ]
    )

    hypotheses = list(surface.get("hypotheses") or [])
    calculations = list(surface.get("calculations") or [])
    if hypotheses or calculations:
        lines.extend(["## Begründung, Gegenbelege und Unsicherheiten", ""])

    if hypotheses:
        lines.extend(["### Konkurrierende Ursachen", ""])
        for item in hypotheses:
            lines.extend(
                [
                    f"**{_as_text(item.get('status_label'))}**",
                    "",
                    _as_text(item.get("statement")),
                    "",
                ]
            )

    if calculations:
        lines.extend(["### Berechnete Befunde", ""])
        for item in calculations:
            lines.append(f"- {_as_text(item.get('summary'))}")
            population = _as_text(item.get("population_summary"))
            limits = _as_text(item.get("limits"))
            if population:
                lines.append(f"  - Datenbasis: {population}")
            if limits:
                lines.append(f"  - Aussagegrenze: {limits}")
        lines.append("")

    validation = (
        surface.get("validation_step")
        if isinstance(surface.get("validation_step"), Mapping)
        else {}
    )
    if _as_text(validation.get("step")) or _as_text(validation.get("measurement")):
        lines.extend(["### Kleinster Validierungsschritt", ""])
        _append_if(lines, "", validation.get("step"))
        measurement = _as_text(validation.get("measurement"))
        if measurement:
            lines.extend([f"Messansatz: {measurement}", ""])

    options = list(surface.get("options") or [])
    if options:
        lines.extend(["## Vorgeschlagene Lösungskandidaten", ""])
        lines.append(
            "Diese Kandidaten sind noch nicht fachlich verbindlich ausgewählt. "
            "Bewerte sie nur als Teil der vorliegenden Entscheidungsgrundlage."
        )
        lines.append("")
        for item in options:
            markers: list[str] = []
            if item.get("non_ai"):
                markers.append("Ohne KI")
            if item.get("status_quo"):
                markers.append("Status quo")
            marker = f" ({', '.join(markers)})" if markers else ""
            lines.extend(
                [
                    f"### {_as_text(item.get('name'))}{marker}",
                    "",
                    _as_text(item.get("description")),
                    "",
                ]
            )
            expected = _as_text(item.get("expected_value"))
            option_risks = _as_text(item.get("risks"))
            if expected:
                lines.append(f"Erwarteter Beitrag: {expected}")
            if option_risks:
                lines.append(f"Risiken: {option_risks}")
            lines.append("")

    lines.extend(["## Quellen und Daten zur Prüfung", ""])
    for source in sources:
        language = "csv" if source.source_type == "csv" else "text"
        lines.extend(
            [
                f"### {source.alias}",
                "",
                f"```{language}",
                source.content.rstrip(),
                "```",
                "",
            ]
        )

    steps = list(surface.get("steps") or [])
    if steps:
        lines.extend(["## Untersuchungsspur", ""])
        lines.append(
            "Die Spur zeigt fachliche Aktionen und Erkenntnisänderungen; "
            "interne Werkzeug- und Laufkennungen sind entfernt."
        )
        lines.append("")
        for item in steps:
            step_text = (
                f"{item.get('sequence')}. **{_as_text(item.get('action_label'))}** — "
                f"{_as_text(item.get('progress_label'))}"
            )
            expected = _as_text(item.get("expected_finding"))
            if expected:
                step_text += f"\n   - Prüfziel: {expected}"
            lines.append(step_text)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def reviewer_readme() -> str:
    return """# Unabhängiger fachlicher Blind Review

Du erhältst neun anonymisierte Ergebnisse eines Systems, das aus vorhandenen Quellen
eine fachliche Untersuchung durchführt und daraus entweder eine entscheidungsfähige
Richtungsgrundlage, eine konkrete Rückfrage oder einen sicheren Abbruch erzeugt.

Die Fälle sind absichtlich nicht mit Herkunft, erwarteter Ursache oder gewünschtem
Ergebnis gekennzeichnet. Bitte recherchiere keine Zuordnung in Repositories,
Projekt-Issues oder früheren Ergebnislisten.

Bewerte ausschließlich das jeweils bereitgestellte Artefakt und die darin enthaltenen
Quellen und Berechnungen.

Prüfe pro Fall:

1. **Quellenstützung:** Sind tragende Tatsachen und Zahlen nachvollziehbar belegt?
2. **Ursachen/Alternativen:** Werden relevante alternative Erklärungen sichtbar geprüft?
3. **Unsicherheit:** Sind Annahmen, offene Hypothesen und bestätigte Befunde getrennt?
4. **Ausgang:** Ist Entscheidung, Rückfrage oder Abbruch aus der sichtbaren Evidenz angemessen?
5. **Entscheidungstauglichkeit:** Ist der nächste fachliche Richtungsentscheid möglich oder
   ist klar, welcher Nachweis noch fehlt?
6. **Korrekturbedarf:** Welche fachliche Korrektur wäre vor einer Richtungsentscheidung zwingend?

Bitte bewerte keine vermutete Modell- oder Systemarchitektur außerhalb der konkreten Artefakte.
"""


def reviewer_form() -> str:
    return """# Bewertungsbogen

Für jeden Fall R01-R09 separat ausfüllen.

| Feld | Eintrag |
|---|---|
| Review-Code | R__ |
| Quellenstützung | OK / kleinere Lücke / kritisch |
| Zahlen & Berechnungen nachvollziehbar | ja / teilweise / nein / nicht relevant |
| Alternativen angemessen behandelt | ja / teilweise / nein / nicht beurteilbar |
| Unsicherheit korrekt dargestellt | ja / teilweise / nein |
| Ausgang fachlich angemessen | ja / nein / nicht beurteilbar |
| Entscheidungstauglich | ja / mit Korrektur / nein |
| Kritische fachliche Finding(s) | Freitext |
| Nicht-kritische Verbesserung(en) | Freitext |
| Zwingende Korrektur vor Richtungsentscheidung | Freitext oder „keine“ |
| Review-Zeit optional | mm:ss |

## Gesamtfazit nach R01-R09

- Welche wiederkehrenden fachlichen Schwächen treten auf?
- Gibt es einen Fall, der trotz plausibler Formulierungen nicht entscheidungsfähig ist?
- Gibt es einen Fall, der wegen fehlender Evidenz zwingend hätte stoppen oder nachfragen müssen?
- Gibt es unbelegte oder zu starke Kausalbehauptungen?
- Welche Findings sind kritisch für eine produktive Richtungsentscheidung?

Kein Gesamt-Score und keine Auswahl nur der besten Fälle.
"""


def _exact_tokens_for_run(run: InvestigationRun) -> set[str]:
    tokens = {
        str(run.pk),
        str(run.process_analysis_id),
        str(run.source_snapshot_id),
        str(run.evidence_campaign_id or ""),
        _as_text(run.brief_hash),
        _as_text(run.manifest_hash),
        _as_text(getattr(run.evidence_campaign, "campaign_key", "")),
    }
    tokens.update(str(source.pk) for source in run.source_snapshot.sources.all())
    for step in run.steps.all():
        tokens.add(str(step.pk))
        result = step.result_payload if isinstance(step.result_payload, Mapping) else {}
        if result.get("result_id"):
            tokens.add(str(result["result_id"]))
        reference = step.result_ref if isinstance(step.result_ref, Mapping) else {}
        if reference.get("tool_result_id"):
            tokens.add(str(reference["tool_result_id"]))
    return {token for token in tokens if token}


def _write_zip(source_dir: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_blind_review_package(
    *,
    campaign: Any,
    output_dir: Path,
    seed: str | None = None,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    runs = list(
        campaign.investigation_runs.select_related(
            "evidence_campaign__authorized_by",
            "source_snapshot",
        ).prefetch_related(
            "source_snapshot__sources",
            "steps",
            "materializations",
        )
    )
    selected = select_scored_adaptive_runs(runs)
    seed = _as_text(seed) or secrets.token_hex(16)
    ordered_slots = deterministic_review_order(selected, seed=seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / "blind-review-package.zip"
    curator_path = output_dir / "blind-review-curator.json"
    if not overwrite and (package_path.exists() or curator_path.exists()):
        raise BlindReviewPackageError(
            "Review-Paket existiert bereits. --overwrite nur für bewusstes Neuerzeugen verwenden."
        )

    curator_entries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="blind-review-", dir=output_dir) as temp_name:
        temp_dir = Path(temp_name)
        cases_dir = temp_dir / "cases"
        cases_dir.mkdir(parents=True)

        (temp_dir / "README.md").write_text(reviewer_readme(), encoding="utf-8")
        (temp_dir / "Bewertungsbogen.md").write_text(reviewer_form(), encoding="utf-8")

        for index, slot in enumerate(ordered_slots, start=1):
            review_code = f"R{index:02d}"
            run = selected[slot]
            surface = _surface_for_run(run)
            sources = _review_sources(run)
            raw_markdown = render_review_case(
                review_code=review_code,
                surface=surface,
                sources=sources,
            )
            exact_tokens = _exact_tokens_for_run(run)
            reviewer_markdown, redaction_counts = redact_blinding_metadata(
                raw_markdown,
                exact_tokens=exact_tokens,
            )
            leaks = find_blinding_leaks(reviewer_markdown, exact_tokens=exact_tokens)
            if leaks:
                raise BlindReviewPackageError(
                    f"{review_code} enthält nach Redaction noch Blinding-Leaks: "
                    + ", ".join(leaks)
                )

            case_path = cases_dir / f"{review_code}.md"
            case_path.write_text(reviewer_markdown, encoding="utf-8")
            curator_entries.append(
                {
                    "review_code": review_code,
                    "run_id": str(run.pk),
                    "variant": slot[0],
                    "attempt": slot[1],
                    "status": run.status,
                    "source_snapshot_id": str(run.source_snapshot_id),
                    "source_aliases": {
                        source.alias: source.original_filename for source in sources
                    },
                    "redactions": redaction_counts,
                    "reviewer_sha256": hashlib.sha256(
                        reviewer_markdown.encode("utf-8")
                    ).hexdigest(),
                }
            )

        for reviewer_file in (temp_dir / "README.md", temp_dir / "Bewertungsbogen.md"):
            leaks = find_blinding_leaks(reviewer_file.read_text(encoding="utf-8"))
            if leaks:
                raise BlindReviewPackageError(
                    f"{reviewer_file.name} enthält Blinding-Leaks: " + ", ".join(leaks)
                )

        _write_zip(temp_dir, package_path)

    curator = {
        "schema_version": 1,
        "purpose": "Curator key for the independent blind human review.",
        "warning": "Nicht an Reviewer weitergeben.",
        "campaign_id": str(campaign.pk),
        "seed": seed,
        "mapping": curator_entries,
        "reviewer_package": package_path.name,
        "reviewer_package_sha256": _sha256_file(package_path),
    }
    curator_path.write_text(
        json.dumps(curator, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return package_path, curator_path
