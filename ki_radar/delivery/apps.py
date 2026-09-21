from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ki_radar.delivery"
    verbose_name = "Delivery Handover"

    def ready(self):
        from . import architecture_artifacts  # noqa: F401
