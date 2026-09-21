from importlib import import_module

from django.apps import AppConfig


class AcceleratorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ki_radar.accelerator"

    def ready(self):
        import_module("ki_radar.accelerator.structured_models")
        import_module("ki_radar.accelerator.solution_quality_signals")
