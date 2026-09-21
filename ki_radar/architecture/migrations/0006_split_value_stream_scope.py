from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("architecture", "0005_backfill_value_stream_focus"),
    ]

    operations = [
        migrations.RenameField(
            model_name="valuestream",
            old_name="scope",
            new_name="scope_in",
        ),
        migrations.AlterField(
            model_name="valuestream",
            name="scope_in",
            field=models.TextField(verbose_name="Im Scope"),
        ),
        migrations.AddField(
            model_name="valuestream",
            name="scope_out",
            field=models.TextField(blank=True, verbose_name="Nicht im Scope"),
        ),
    ]
