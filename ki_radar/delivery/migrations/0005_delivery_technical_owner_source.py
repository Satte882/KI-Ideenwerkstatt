import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _user_label(user):
    if user is None:
        return ""
    full_name = " ".join(
        value
        for value in [getattr(user, "first_name", ""), getattr(user, "last_name", "")]
        if value
    ).strip()
    return full_name or getattr(user, "username", "") or str(user.pk)


def backfill_package_technical_owner(apps, schema_editor):
    DeliveryPackage = apps.get_model("delivery", "DeliveryPackage")
    DeliverySectionReview = apps.get_model("delivery", "DeliverySectionReview")
    packages = DeliveryPackage.objects.select_related("use_case__technical_owner")
    for package in packages.iterator():
        use_case = package.use_case
        package.technical_owner_id = use_case.technical_owner_id
        package.save(update_fields=["technical_owner"])

        reviews = DeliverySectionReview.objects.filter(delivery_package_id=package.pk)
        for review in reviews.iterator():
            manifest = dict(review.source_manifest or {})
            role_sources = dict(manifest.get("role_sources") or {})
            role_sources["technical_owner"] = {
                "id": str(use_case.technical_owner_id or ""),
                "value": _user_label(use_case.technical_owner),
                "updated_at": use_case.updated_at.isoformat() if use_case.updated_at else "",
                "adoption": "copied",
            }
            manifest["role_sources"] = role_sources
            review.source_manifest = manifest
            review.save(update_fields=["source_manifest"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("delivery", "0004_delivery_confirmation_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliverypackage",
            name="technical_owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="technical_delivery_packages",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="DeliveryRoleSourceDecision",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role_key",
                    models.CharField(
                        choices=[("technical_owner", "Technical Owner")],
                        max_length=40,
                    ),
                ),
                ("old_value_id", models.CharField(blank=True, max_length=64)),
                ("old_value_label", models.CharField(blank=True, max_length=255)),
                ("new_value_id", models.CharField(blank=True, max_length=64)),
                ("new_value_label", models.CharField(blank=True, max_length=255)),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("adopt_source", "Neue Zuordnung übernehmen"),
                            ("keep_package", "Package-Zuordnung beibehalten"),
                        ],
                        max_length=30,
                    ),
                ),
                ("rationale", models.TextField()),
                (
                    "decided_at",
                    models.DateTimeField(default=django.utils.timezone.now, editable=False),
                ),
                ("source_updated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="delivery_role_source_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "delivery_package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_source_decisions",
                        to="delivery.deliverypackage",
                    ),
                ),
            ],
            options={"ordering": ["-decided_at", "-created_at"]},
        ),
        migrations.RunPython(backfill_package_technical_owner, migrations.RunPython.noop),
    ]
