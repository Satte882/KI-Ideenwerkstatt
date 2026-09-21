from django.db import migrations, models


def set_active_scope_origin_mixed(apps, schema_editor):
    DeliverySectionReview = apps.get_model("delivery", "DeliverySectionReview")
    DeliverySectionReview.objects.filter(
        section_key="scope_and_users",
        delivery_package__status__in=("draft", "ready"),
    ).update(content_origin="mixed")


def restore_active_scope_origin_inherited(apps, schema_editor):
    DeliverySectionReview = apps.get_model("delivery", "DeliverySectionReview")
    DeliverySectionReview.objects.filter(
        section_key="scope_and_users",
        delivery_package__status__in=("draft", "ready"),
    ).update(content_origin="inherited")


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0006_harden_role_source_audit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="deliverypackage",
            name="mvp_scope",
            field=models.TextField(
                help_text=(
                    "Unverzichtbarer Mindestumfang für diese Delivery-Version "
                    "(MoSCoW: Must)."
                ),
                verbose_name="Must / MVP-Scope",
            ),
        ),
        migrations.AddField(
            model_name="deliverypackage",
            name="should_scope",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Wichtiger Umfang, der nach dem Must-Scope folgen soll, aber für den "
                    "Mindestnutzen nicht zwingend ist."
                ),
                verbose_name="Should",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="deliverypackage",
            name="could_scope",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Optionaler Umfang mit Nutzen, sofern Zeit und Kapazität verfügbar sind."
                ),
                verbose_name="Could",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="deliverypackage",
            name="wont_this_time",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Bewusst für diese Delivery-Version zurückgestellt. Anders als 'Nicht im "
                    "Scope' liegt dieser Umfang grundsätzlich innerhalb des möglichen "
                    "Lösungsrahmens."
                ),
                verbose_name="Won't this time",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            set_active_scope_origin_mixed,
            restore_active_scope_origin_inherited,
        ),
    ]
