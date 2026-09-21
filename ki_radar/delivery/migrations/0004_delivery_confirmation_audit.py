from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0003_delivery_readiness_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliverysectionreview",
            name="business_confirmation_role",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="deliverysectionreview",
            name="technical_confirmation_role",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="deliverysectionreview",
            name="role_collapse_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="deliverysectionreview",
            name="admin_override_confirmed",
            field=models.BooleanField(default=False),
        ),
    ]
