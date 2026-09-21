from types import SimpleNamespace

from ki_radar.architecture.provenance import source_differences


def test_source_differences_reports_only_changed_source_values():
    value_stream = SimpleNamespace(pk="vs-1", trigger="Aktueller Auslöser")
    stage = SimpleNamespace(
        pk="stage-1",
        value_stream=value_stream,
        name="Prüfung",
        actors="Fachrolle",
    )
    snapshot = {
        "trigger": {
            "kind": "value_stream",
            "label": "Value Stream",
            "field": "trigger",
            "value": "Alter Auslöser",
        },
        "target_users": {
            "kind": "value_stream_stage",
            "label": "Value-Stream-Phase",
            "field": "actors",
            "value": "Fachrolle",
        },
    }

    assert source_differences(snapshot, stage=stage) == [
        {
            "target_field": "trigger",
            "source_label": "Value Stream",
            "source_field": "trigger",
            "previous": "Alter Auslöser",
            "current": "Aktueller Auslöser",
        }
    ]


def test_source_differences_keeps_unchanged_sources_out_of_review():
    value_stream = SimpleNamespace(pk="vs-1", trigger="Bestellung eingegangen")
    stage = SimpleNamespace(pk="stage-1", value_stream=value_stream)
    snapshot = {
        "trigger": {
            "kind": "value_stream",
            "label": "Value Stream",
            "field": "trigger",
            "value": "Bestellung eingegangen",
        }
    }

    assert source_differences(snapshot, stage=stage) == []


def test_source_differences_ignores_unavailable_optional_source_artifacts():
    value_stream = SimpleNamespace(pk="vs-1")
    stage = SimpleNamespace(pk="stage-1", value_stream=value_stream)
    snapshot = {
        "expected_benefit": {
            "kind": "solution_option",
            "label": "Lösungsoption",
            "field": "expected_value",
            "value": "Zeitersparnis",
        }
    }

    assert source_differences(snapshot, stage=stage, solution_option=None) == []
