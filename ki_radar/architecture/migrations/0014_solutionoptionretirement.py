import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("architecture", "0013_solutionoption_not_assessed"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolutionOptionRetirement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "retired_at",
                    models.DateTimeField(default=django.utils.timezone.now, editable=False),
                ),
                (
                    "option",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retirement",
                        to="architecture.solutionoption",
                    ),
                ),
                (
                    "retired_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="retired_solution_options",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-retired_at"]},
        ),
    ]
