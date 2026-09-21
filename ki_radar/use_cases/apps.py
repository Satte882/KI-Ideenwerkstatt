from django.apps import AppConfig


class UseCasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ki_radar.use_cases"

    def import_models(self):
        super().import_models()
        from . import idea_models  # noqa: F401

    def ready(self):
        from . import classification  # noqa: F401
        from .governance_journey import install as install_governance_journey
        from .lean_journey import install as install_lean_journey
        from .lean_outcome import install as install_lean_outcome
        from .primary_actions import install as install_primary_actions
        from .value_stream_journey import install as install_value_stream_journey
        from .workflow import install

        install()
        install_value_stream_journey()
        install_governance_journey()
        install_primary_actions()
        install_lean_journey()
        install_lean_outcome()
