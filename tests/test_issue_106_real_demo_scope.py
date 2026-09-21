import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ki_radar.architecture.models import ValueStream

TARGET_NAME = "[Real-DEMO] Beschaffungsbedarf bis Bestellung"


def _value_stream(business_unit, *, name=TARGET_NAME, scope_in="Alt in", scope_out="Alt out"):
    return ValueStream.objects.create(
        name=name,
        description="Testdatensatz",
        business_unit=business_unit,
        trigger="Bedarf liegt vor",
        outcome="Bestellung ausgelöst",
        scope_in=scope_in,
        scope_out=scope_out,
        status=ValueStream.Status.ACTIVE,
    )


def _plan(target, reviewed_ids):
    return {
        "issue": 106,
        "environment": "test",
        "operator": "pytest",
        "backup_reference": "test-backup",
        "repository_check_reference": "test-repository-check",
        "target": {
            "id": str(target.pk),
            "name": TARGET_NAME,
            "expected_updated_at": target.updated_at.isoformat(),
            "expected_scope_in": target.scope_in,
            "expected_scope_out": target.scope_out,
            "new_scope_in": "Neuer eingeschlossener Umfang - exakt übernommen",
            "new_scope_out": "Neue ausdrückliche Abgrenzung - exakt übernommen",
        },
        "real_demo_review": {
            "reviewed_ids": [str(value) for value in reviewed_ids],
            "conclusion": "Alle aufgeführten Real-DEMO-Value-Streams wurden fachlich geprüft.",
        },
    }


def _write_plan(tmp_path, payload):
    path = tmp_path / "issue-106-plan.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.django_db
def test_inspect_outputs_exact_target_and_all_real_demo_streams(business_unit):
    target = _value_stream(
        business_unit,
        scope_in="Eingeschlossen. Nicht im Scope: Altbestand.",
        scope_out="",
    )
    other = _value_stream(
        business_unit,
        name="[Real-DEMO] Zweiter Prozess",
        scope_in="Zweiter In-Scope",
        scope_out="Zweiter Out-of-Scope",
    )
    stdout = StringIO()

    call_command("correct_real_demo_scope", inspect=True, stdout=stdout)

    payload = json.loads(stdout.getvalue())
    assert payload["mode"] == "inspection"
    assert payload["target"]["id"] == str(target.pk)
    assert payload["target"]["scope_in"] == target.scope_in
    assert {item["id"] for item in payload["real_demo_value_streams"]} == {
        str(target.pk),
        str(other.pk),
    }
    target.refresh_from_db()
    assert target.scope_in == "Eingeschlossen. Nicht im Scope: Altbestand."
    assert target.scope_out == ""


@pytest.mark.django_db
def test_plan_is_dry_run_without_apply(tmp_path, business_unit):
    target = _value_stream(business_unit)
    plan_path = _write_plan(tmp_path, _plan(target, [target.pk]))
    stdout = StringIO()

    call_command("correct_real_demo_scope", plan=plan_path, stdout=stdout)

    result = json.loads(stdout.getvalue())
    assert result["status"] == "validated_no_change"
    target.refresh_from_db()
    assert target.scope_in == "Alt in"
    assert target.scope_out == "Alt out"


@pytest.mark.django_db
def test_apply_uses_exact_values_and_writes_private_audit(tmp_path, business_unit):
    target = _value_stream(
        business_unit,
        scope_in="Im Scope. Nicht im Scope: Vertragsabschluss.",
        scope_out="",
    )
    plan = _plan(target, [target.pk])
    plan["target"]["new_scope_in"] = "Im Scope."
    plan["target"]["new_scope_out"] = "Vertragsabschluss."
    plan_path = _write_plan(tmp_path, plan)
    audit_path = tmp_path / "issue-106-audit.md"
    stdout = StringIO()

    call_command(
        "correct_real_demo_scope",
        plan=plan_path,
        apply=True,
        audit_path=audit_path,
        stdout=stdout,
    )

    target.refresh_from_db()
    assert target.scope_in == "Im Scope."
    assert target.scope_out == "Vertragsabschluss."
    result = json.loads(stdout.getvalue())
    assert result["status"] == "applied"
    assert result["changed_rows"] == 1
    assert len(result["audit_sha256"]) == 64
    audit = audit_path.read_text(encoding="utf-8")
    assert '"status": "APPLIED"' in audit
    assert '"changed_rows": 1' in audit
    assert '"scope_in": "Im Scope."' in audit
    assert '"scope_out": "Vertragsabschluss."' in audit


@pytest.mark.django_db
def test_apply_stops_on_optimistic_lock_mismatch(tmp_path, business_unit):
    target = _value_stream(business_unit)
    plan_path = _write_plan(tmp_path, _plan(target, [target.pk]))
    audit_path = tmp_path / "issue-106-audit.md"
    target.scope_in = "Zwischenzeitlich geändert"
    target.save(update_fields=["scope_in", "updated_at"])

    with pytest.raises(CommandError, match="Optimistic lock failed"):
        call_command(
            "correct_real_demo_scope",
            plan=plan_path,
            apply=True,
            audit_path=audit_path,
        )

    target.refresh_from_db()
    assert target.scope_in == "Zwischenzeitlich geändert"
    assert target.scope_out == "Alt out"
    assert not audit_path.exists()


@pytest.mark.django_db
def test_plan_must_cover_current_real_demo_inventory(tmp_path, business_unit):
    target = _value_stream(business_unit)
    other = _value_stream(business_unit, name="[Real-DEMO] Weiterer Prozess")
    plan_path = _write_plan(tmp_path, _plan(target, [target.pk]))

    with pytest.raises(CommandError, match="not fully reviewed"):
        call_command("correct_real_demo_scope", plan=plan_path)

    target.refresh_from_db()
    other.refresh_from_db()
    assert target.scope_in == "Alt in"
    assert other.scope_in == "Alt in"
