import django.db.models.deletion
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


def reconstruct_package_owners(apps, schema_editor):
    DeliveryPackage = apps.get_model("delivery", "DeliveryPackage")
    DeliverySectionReview = apps.get_model("delivery", "DeliverySectionReview")
    HistoricalUseCase = apps.get_model("use_cases", "HistoricalUseCase")
    UseCase = apps.get_model("use_cases", "UseCase")
    User = apps.get_model("accounts", "User")

    packages = DeliveryPackage.objects.select_related("use_case").all()
    for package in packages.iterator():
        historical = (
            HistoricalUseCase.objects.filter(
                id=package.use_case_id,
                history_date__lte=package.created_at,
            )
            .order_by("-history_date", "-history_id")
            .first()
        )
        if historical is not None:
            owner_id = historical.technical_owner_id
            source_time = historical.history_date
            adoption = "historical_backfill"
        else:
            current_use_case = UseCase.objects.get(pk=package.use_case_id)
            owner_id = current_use_case.technical_owner_id
            source_time = current_use_case.updated_at
            adoption = "migration_current_fallback"

        package.technical_owner_id = owner_id
        package.save(update_fields=["technical_owner"])
        owner = User.objects.filter(pk=owner_id).first() if owner_id else None
        source = {
            "id": str(owner_id or ""),
            "value": _user_label(owner),
            "updated_at": source_time.isoformat() if source_time else "",
            "adoption": adoption,
        }
        reviews = DeliverySectionReview.objects.filter(delivery_package_id=package.pk)
        for review in reviews.iterator():
            manifest = dict(review.source_manifest or {})
            role_sources = dict(manifest.get("role_sources") or {})
            role_sources["technical_owner"] = source
            manifest["role_sources"] = role_sources
            review.source_manifest = manifest
            review.save(update_fields=["source_manifest"])


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0005_delivery_technical_owner_source"),
        ("use_cases", "0006_guided_second_approval"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deliveryrolesourcedecision",
            name="delivery_package",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="role_source_decisions",
                to="delivery.deliverypackage",
            ),
        ),
        migrations.RunPython(reconstruct_package_owners, migrations.RunPython.noop),
    ]
