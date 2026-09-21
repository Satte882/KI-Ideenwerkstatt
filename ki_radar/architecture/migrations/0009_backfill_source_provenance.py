from django.db import migrations


def _iso(value):
    return value.isoformat() if value else ""


def _source(*, kind, label, obj, field, value):
    return {
        "kind": kind,
        "label": label,
        "id": str(obj.pk),
        "field": field,
        "value": "" if value is None else str(value),
        "updated_at": _iso(getattr(obj, "updated_at", None)),
        "captured_via": "migration_backfill",
    }


def _process_snapshot(process):
    stage = process.stage
    value_stream = stage.value_stream
    return {
        "name": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="name",
            value=stage.name,
        ),
        "trigger": _source(
            kind="value_stream",
            label="Value Stream",
            obj=value_stream,
            field="trigger",
            value=value_stream.trigger,
        ),
        "outcome": _source(
            kind="value_stream_stage" if stage.description else "value_stream",
            label="Value-Stream-Phase" if stage.description else "Value Stream",
            obj=stage if stage.description else value_stream,
            field="description" if stage.description else "outcome",
            value=stage.description or value_stream.outcome,
        ),
        "roles": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="actors",
            value=stage.actors,
        ),
        "systems": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="systems",
            value=stage.systems,
        ),
        "data_objects": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="documents",
            value=stage.documents,
        ),
        "bottlenecks": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="pain_points",
            value=stage.pain_points,
        ),
        "baseline_metrics": _source(
            kind="value_stream_stage",
            label="Value-Stream-Phase",
            obj=stage,
            field="baseline_metrics",
            value=stage.baseline_metrics,
        ),
    }


def _origin_snapshot(origin):
    stage = origin.stage
    process = origin.process_analysis
    option = origin.solution_option
    if process is None:
        return {
            "title": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="name",
                value=stage.name,
            ),
            "affected_process": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="name",
                value=stage.name,
            ),
            "summary": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="description",
                value=stage.description,
            ),
            "target_users": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="actors",
                value=stage.actors,
            ),
            "source_systems": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="systems",
                value=stage.systems,
            ),
            "problem_statement": _source(
                kind="value_stream_stage",
                label="Value-Stream-Phase",
                obj=stage,
                field="pain_points",
                value=stage.pain_points,
            ),
        }

    snapshot = {
        "affected_process": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process,
            field="name",
            value=process.name,
        ),
        "summary": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process,
            field="current_flow",
            value=process.current_flow,
        ),
        "problem_statement": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process,
            field="bottlenecks",
            value=process.bottlenecks,
        ),
        "target_users": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process,
            field="roles",
            value=process.roles,
        ),
        "source_systems": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process,
            field="systems",
            value=process.systems,
        ),
        "intended_users": _source(
            kind="process_analysis",
            label="Prozessanalyse",
            obj=process,
            field="roles",
            value=process.roles,
        ),
    }
    if option is not None:
        snapshot.update(
            {
                "title": _source(
                    kind="solution_option",
                    label="Lösungsoption",
                    obj=option,
                    field="name",
                    value=option.name,
                ),
                "intended_purpose": _source(
                    kind="solution_option",
                    label="Lösungsoption",
                    obj=option,
                    field="description",
                    value=option.description,
                ),
                "expected_benefit": _source(
                    kind="solution_option",
                    label="Lösungsoption",
                    obj=option,
                    field="expected_value",
                    value=option.expected_value,
                ),
                "data_sources": _source(
                    kind="solution_option" if option.data_requirements else "process_analysis",
                    label="Lösungsoption" if option.data_requirements else "Prozessanalyse",
                    obj=option if option.data_requirements else process,
                    field="data_requirements" if option.data_requirements else "data_objects",
                    value=option.data_requirements or process.data_objects,
                ),
            }
        )
    return snapshot


def backfill_source_snapshots(apps, schema_editor):
    ProcessAnalysis = apps.get_model("architecture", "ProcessAnalysis")
    UseCaseOrigin = apps.get_model("architecture", "UseCaseOrigin")

    processes = ProcessAnalysis.objects.select_related("stage__value_stream").filter(
        source_snapshot={}
    )
    for process in processes.iterator():
        process.source_snapshot = _process_snapshot(process)
        process.save(update_fields=["source_snapshot"])

    origins = UseCaseOrigin.objects.select_related(
        "stage", "process_analysis", "solution_option"
    ).filter(source_snapshot={})
    for origin in origins.iterator():
        origin.source_snapshot = _origin_snapshot(origin)
        origin.save(update_fields=["source_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0008_source_provenance"),
    ]

    operations = [
        migrations.RunPython(backfill_source_snapshots, migrations.RunPython.noop),
    ]
