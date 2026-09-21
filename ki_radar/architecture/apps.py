from django.apps import AppConfig


class ArchitectureConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ki_radar.architecture"
    verbose_name = "Discovery und Architektur"

    def ready(self):
        from . import (
            architecture_assessment_models,  # noqa: F401
            focus,  # noqa: F401
            retirement_models,  # noqa: F401
            stage_focus,  # noqa: F401
        )
