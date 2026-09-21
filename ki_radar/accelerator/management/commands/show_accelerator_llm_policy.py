from django.conf import settings
from django.core.management.base import BaseCommand

from ki_radar.core.llm_policy import get_accelerator_llm_policy
from ki_radar.core.openrouter import max_response_bytes, reasoning_response_excluded


class Command(BaseCommand):
    help = "Zeigt die effektiv geladene Accelerator-LLM-Konfiguration ohne Secrets."

    def handle(self, *args, **options):
        policy = get_accelerator_llm_policy()
        api_key_configured = "yes" if settings.OPENROUTER_API_KEY else "no"
        model = settings.OPENROUTER_MODEL or "<provider-default>"

        self.stdout.write(f"timeout_seconds={policy.timeout_seconds}")
        self.stdout.write(f"max_input_chars={policy.max_input_chars}")
        self.stdout.write(f"shared_max_output_tokens={policy.max_output_tokens}")
        self.stdout.write(f"capture_max_output_tokens={policy.capture_max_output_tokens}")
        self.stdout.write(
            f"solution_generation_max_output_tokens={policy.solution_generation_max_output_tokens}"
        )
        self.stdout.write(
            "solution_generation_max_calls_per_context="
            f"{policy.solution_generation_max_calls_per_context}"
        )
        self.stdout.write(f"max_calls_per_user_day={policy.max_calls_per_user_day}")
        self.stdout.write(f"max_calls_global_day={policy.max_calls_global_day}")
        self.stdout.write(f"openrouter_api_key_configured={api_key_configured}")
        self.stdout.write(f"openrouter_model={model}")
        self.stdout.write(f"openrouter_api_url={settings.OPENROUTER_API_URL}")
        self.stdout.write(f"max_response_bytes={max_response_bytes()}")
        self.stdout.write(
            f"reasoning_response_excluded={'yes' if reasoning_response_excluded() else 'no'}"
        )
