from django.db import migrations


def backfill_value_stream_focus(apps, schema_editor):
    value_stream_model = apps.get_model("architecture", "ValueStream")
    focus_model = apps.get_model("architecture", "ValueStreamFocus")
    for value_stream in value_stream_model.objects.all().iterator():
        focus_model.objects.get_or_create(
            value_stream=value_stream,
            defaults={
                "business_domain": "other",
                "status": "not_screened",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0004_value_stream_focus"),
    ]

    operations = [
        migrations.RunPython(
            backfill_value_stream_focus,
            migrations.RunPython.noop,
        ),
    ]
