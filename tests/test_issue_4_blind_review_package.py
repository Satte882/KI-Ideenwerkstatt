from __future__ import annotations

import json
import zipfile
from types import SimpleNamespace

import pytest

from ki_radar.accelerator import issue4_blind_review as blind_review
from ki_radar.accelerator.issue4_blind_review import (
    BlindReviewPackageError,
    ReviewSource,
    deterministic_review_order,
    find_blinding_leaks,
    qualify_decision_surface,
    redact_blinding_metadata,
    render_review_case,
    select_scored_adaptive_runs,
)


def fake_run(variant: str, attempt: int, *, execution_mode: str = "adaptive"):
    return SimpleNamespace(
        execution_mode=execution_mode,
        evidence_metadata={
            "provider_mode": "real",
            "phase": "scored",
            "variant": variant,
            "attempt": attempt,
        },
        pk=f"{variant}-{attempt}",
        status="ready",
        source_snapshot_id=f"snapshot-{variant}-{attempt}",
    )


def full_sample():
    return [fake_run(variant, attempt) for variant in ("A", "B", "C") for attempt in range(1, 4)]


def minimal_surface():
    return {
        "status_label": "Entscheidungsgrundlage bereit",
        "status_detail": ("Die Evidenz ist geprüft; die fachliche Entscheidung ist noch offen."),
        "situation": "Die Freigabezeiten schwanken.",
        "scope": "Es wird nur der vorliegende Prozess betrachtet.",
        "finding": "Freigeberverfügbarkeit ist mit längeren Laufzeiten verbunden.",
        "recommendation_summary": "Eine organisatorische Verbesserung fachlich prüfen.",
        "recommendation_rationale": "Die vorliegende Evidenz stützt diese Richtung.",
        "risks": ["Kleine Stichprobe; keine Kausalitätsaussage."],
        "next_action": {
            "title": "Lösungsoptionen fachlich vergleichen",
            "description": "Kandidaten im bestehenden Lösungsraum vergleichen.",
        },
        "hypotheses": [
            {
                "status_label": "Durch aktuelle Evidenz gestützt",
                "statement": "Freigeberverfügbarkeit beeinflusst die Laufzeit.",
            }
        ],
        "calculations": [
            {
                "summary": "Mittlere Laufzeiten unterscheiden sich.",
                "population_summary": "4 Datensätze",
                "limits": "Kleine Stichprobe.",
            }
        ],
        "validation_step": {
            "step": "Vertretungsregel pilotieren.",
            "measurement": "Laufzeiten vor und nach dem Pilot vergleichen.",
        },
        "options": [
            {
                "name": "Vertretungsregel verbessern",
                "description": "Verfügbarkeit organisatorisch absichern.",
                "expected_value": "Wartezeiten reduzieren.",
                "risks": "Wirkung noch nicht gemessen.",
                "non_ai": True,
                "status_quo": False,
            }
        ],
        "steps": [
            {
                "sequence": 1,
                "action_label": "Quelle geprüft",
                "progress_label": "Weitere Evidenz abgedeckt",
                "expected_finding": "",
            }
        ],
    }


def test_select_scored_adaptive_runs_requires_exact_frozen_nine():
    selected = select_scored_adaptive_runs(full_sample())

    assert set(selected) == blind_review.EXPECTED_SLOTS
    assert len(selected) == 9


def test_select_scored_adaptive_runs_rejects_missing_or_duplicate_slots():
    with pytest.raises(BlindReviewPackageError, match="nicht exakt 9/9"):
        select_scored_adaptive_runs(full_sample()[:-1])

    sample = full_sample()
    sample.append(fake_run("A", 1))
    with pytest.raises(BlindReviewPackageError, match="mehrfach"):
        select_scored_adaptive_runs(sample)


def test_review_order_is_deterministic_without_exposing_variant_order():
    first = deterministic_review_order(blind_review.EXPECTED_SLOTS, seed="fixed-private-seed")
    second = deterministic_review_order(blind_review.EXPECTED_SLOTS, seed="fixed-private-seed")

    assert first == second
    assert set(first) == blind_review.EXPECTED_SLOTS
    assert len(first) == 9


def test_metadata_redaction_removes_public_lookup_keys_but_preserves_semantics():
    run_id = "aab16792-39aa-46be-935a-ba97248bcebd"
    raw = (
        "Im Fall A zeigen sich Freigabeverzögerungen. "
        "Die Durchlaufzeit von Fall C ähnelt Fall A. "
        "Gegenbeleg A, Berichtsstand B und Systemhinweis C. "
        "A-01 und C-04. Neutral Evidence Case. VS1/#4. "
        f"Run {run_id}. "
        "A/adaptive/2. "
        "http://127.0.0.1:8001/accelerator/investigations/"
        f"{run_id}/. " + "a" * 64
    )

    redacted, counts = redact_blinding_metadata(raw, exact_tokens={run_id})

    assert "Freigabeverzögerungen" in redacted
    assert "in diesem Fall" in redacted
    assert "dieses Falls ähnelt einem vergleichbaren Referenzfall" in redacted
    assert "Gegenbeleg A" not in redacted
    assert "Berichtsstand B" not in redacted
    assert "Systemhinweis C" not in redacted
    assert "A-01" not in redacted
    assert "C-04" not in redacted
    assert "case-01" in redacted
    assert "case-04" in redacted
    assert "Neutral Evidence Case" not in redacted
    assert counts
    assert not find_blinding_leaks(redacted, exact_tokens={run_id})


def test_source_filenames_are_replaced_by_neutral_aliases():
    text = (
        "Quellen: 01_case_note.md, 02_system_note.md und cases.csv. "
        "01_case_note.md wird erneut referenziert."
    )
    sources = [
        ReviewSource(
            alias="Quelle 1",
            source_type="md",
            content="A",
            original_filename="01_case_note.md",
        ),
        ReviewSource(
            alias="Quelle 2",
            source_type="md",
            content="B",
            original_filename="02_system_note.md",
        ),
        ReviewSource(
            alias="Datensatz 1",
            source_type="csv",
            content="x,y",
            original_filename="cases.csv",
        ),
    ]

    redacted, count = blind_review.replace_source_filenames(text, sources)

    assert count == 4
    assert redacted == (
        "Quellen: Quelle 1, Quelle 2 und Datensatz 1. "
        "Quelle 1 wird erneut referenziert."
    )


def test_neutral_provenance_keeps_source_traceability_without_internal_ids():
    source_id = "11111111-1111-4111-8111-111111111111"
    tool_result_id = "22222222-2222-4222-8222-222222222222"
    run = SimpleNamespace(
        brief_payload={
            "problem": {
                "references": [
                    {"source_id": source_id, "locator": {"line": 2}},
                ]
            },
            "hypotheses": [
                {
                    "references": [],
                    "counterevidence_refs": [
                        {"source_id": source_id, "locator": {"line": 4}},
                    ],
                }
            ],
            "calculations": [
                {"reference": {"tool_result_id": tool_result_id}},
            ],
            "recommendation": {
                "references": [{"source_id": source_id, "locator": {"line": 4}}],
            },
        },
        steps=SimpleNamespace(
            all=lambda: [
                SimpleNamespace(
                    result_ref={"tool_result_id": tool_result_id},
                    parameters={"source_id": source_id},
                )
            ]
        ),
    )
    sources = [
        ReviewSource(
            alias="Quelle 1",
            source_type="md",
            content="Fachlicher Inhalt",
            original_filename="01_case_note.md",
            source_id=source_id,
        )
    ]

    entries = blind_review._neutral_provenance_entries(run, sources)

    assert "Problem -> Quelle 1 (Zeile 2)" in entries
    assert "Gegenbeleg zu Ursachenhypothese 1 -> Quelle 1 (Zeile 4)" in entries
    assert "Berechnung 1 -> Reproduzierbare Analyse zu Quelle 1" in entries
    assert "Empfehlung -> Quelle 1 (Zeile 4)" in entries
    combined = "\n".join(entries)
    assert source_id not in combined
    assert tool_result_id not in combined


def test_failed_surface_must_block_fachliche_conclusion_and_recommendation():
    qualify_decision_surface(
        run_status="failed",
        clarification_reason="",
        surface={
            "status_label": "Technische Prüfung fehlgeschlagen",
            "status_detail": (
                "Der Lauf ist technisch fehlgeschlagen. "
                "Aus diesem Stand darf kein fachlicher Schluss abgeleitet werden."
            ),
            "recommendation_summary": ("Noch keine belastbare Empfehlung aus diesem Lauf."),
            "finding": "Zwischenbefund",
        },
    )

    with pytest.raises(BlindReviewPackageError, match="belastbare Empfehlung"):
        qualify_decision_surface(
            run_status="failed",
            clarification_reason="",
            surface={
                "status_label": "Technische Prüfung fehlgeschlagen",
                "status_detail": (
                    "Der Lauf ist technisch fehlgeschlagen. "
                    "Aus diesem Stand darf kein fachlicher Schluss abgeleitet werden."
                ),
                "recommendation_summary": "Vertretungsregel sofort umsetzen.",
                "finding": "Zwischenbefund",
            },
        )


def test_render_review_case_uses_neutral_source_alias_without_original_filename():
    markdown = render_review_case(
        review_code="R01",
        surface=minimal_surface(),
        sources=[
            ReviewSource(
                alias="Quelle 1",
                source_type="md",
                content="Die Freigabezeiten schwanken.",
                original_filename="01_case_note.md",
            )
        ],
    )

    assert "# Anonymisierte Entscheidungsgrundlage R01" in markdown
    assert "Quelle 1" in markdown
    assert "01_case_note.md" not in markdown
    assert "Freigabezeiten schwanken" in markdown


class FakeRunCollection:
    def __init__(self, runs):
        self.runs = list(runs)

    def select_related(self, *_args):
        return self

    def prefetch_related(self, *_args):
        return self

    def __iter__(self):
        return iter(self.runs)


def test_build_package_keeps_curator_mapping_outside_reviewer_zip(tmp_path, monkeypatch):
    runs = full_sample()
    for run in runs:
        run.process_analysis_id = f"process-{run.pk}"
        run.evidence_campaign_id = "campaign-private"
        run.brief_hash = ""
        run.manifest_hash = ""
        run.clarification_reason = ""
        run.evidence_campaign = SimpleNamespace(campaign_key="private-campaign")
        run.source_snapshot = SimpleNamespace()
        run.brief_payload = {}
        run.steps = SimpleNamespace(all=lambda: [])

    campaign = SimpleNamespace(
        pk="campaign-private",
        investigation_runs=FakeRunCollection(runs),
    )

    monkeypatch.setattr(
        blind_review,
        "_surface_for_run",
        lambda _run: minimal_surface(),
    )
    monkeypatch.setattr(
        blind_review,
        "_review_sources",
        lambda run: [
            ReviewSource(
                alias="Quelle 1",
                source_type="md",
                content=(f"Fall {run.evidence_metadata['variant']} mit fachlicher Evidenz."),
                original_filename=f"{run.evidence_metadata['variant']}_source.md",
            )
        ],
    )
    monkeypatch.setattr(
        blind_review,
        "_exact_tokens_for_run",
        lambda run: {str(run.pk), str(run.evidence_campaign_id)},
    )

    package_path, curator_path = blind_review.build_blind_review_package(
        campaign=campaign,
        output_dir=tmp_path,
        seed="private-seed",
    )

    assert package_path.name == "blind-review-package.zip"
    assert curator_path.name == "blind-review-curator.json"

    curator = json.loads(curator_path.read_text(encoding="utf-8"))
    assert len(curator["mapping"]) == 9
    assert curator["seed"] == "private-seed"

    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        assert "README.md" in names
        assert "Bewertungsbogen.md" in names
        assert {f"cases/R{index:02d}.md" for index in range(1, 10)} <= names
        assert all("curator" not in name.casefold() for name in names)
        combined = "\n".join(
            archive.read(name).decode("utf-8") for name in names if name.endswith(".md")
        )
        for entry in curator["mapping"]:
            payload = archive.read(f"cases/{entry['review_code']}.md")
            assert blind_review.hashlib.sha256(payload).hexdigest() == entry["reviewer_sha256"]

    assert "campaign-private" not in combined
    assert not find_blinding_leaks(combined)
