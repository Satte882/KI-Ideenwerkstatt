from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reviews", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="review",
            name="go_live_exception_confirmed",
            field=models.BooleanField(
                default=False,
                verbose_name="Go-live-Ausnahme ausdrücklich bestätigt",
            ),
        ),
        migrations.AddField(
            model_name="historicalreview",
            name="go_live_exception_confirmed",
            field=models.BooleanField(
                default=False,
                verbose_name="Go-live-Ausnahme ausdrücklich bestätigt",
            ),
        ),
    ]
