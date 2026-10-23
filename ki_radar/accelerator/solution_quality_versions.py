QUALITY_CONTRACT_VERSION = "1.2"
CRITIC_PROMPT_VERSION = "2.1"
CRITIC_SCHEMA_VERSION = "1.0"
REPAIR_PROMPT_VERSION = "1.5"
REPAIR_SCHEMA_VERSION = "1.0"


def quality_versions(source_context):
    from .solution_generation_sources import LEGACY_SOURCE_SCHEMA_VERSION

    if source_context.source_schema_version == LEGACY_SOURCE_SCHEMA_VERSION:
        return "1.1", "2.0", "1.4"
    return QUALITY_CONTRACT_VERSION, CRITIC_PROMPT_VERSION, REPAIR_PROMPT_VERSION


STRATEGIC_QUALITY_RULE = (
    "\nFür den menschlich dokumentierten strategischen Discovery-Pfad prüfe bottleneck_fit "
    "als bedingte Abdeckung des begründeten Potenzials und seines Validierungsschritts. "
    "Potenzial ist keine Ursache und kein beobachteter Engpass. Fehlende Ursache oder "
    "Baseline allein ist kein Fehler eines Entwurfs. Erfinde keine Diagnose oder Messwerte."
)
