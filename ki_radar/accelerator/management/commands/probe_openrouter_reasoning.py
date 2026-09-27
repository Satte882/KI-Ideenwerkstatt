from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.investigation_runtime import (
    ENDPOINT_CAPABILITY,
    ISSUE4_INVESTIGATION_PROVIDER_POLICY,
)
from ki_radar.core.openrouter import (
    OpenRouterUnavailable,
    probe_openrouter_stream,
)

PROBE_VERSION = "issue86-reasoning-probe-v1"

PROBE_MESSAGES = [
    {
        "role": "system",
        "content": (
            "Du vergleichst drei Lösungsrichtungen anhand einer kleinen, vollständig "
            "gegebenen Faktenbasis. Nutze nur die gelieferten Fakten und antworte "
            "ausschließlich im vorgegebenen JSON-Schema."
        ),
    },
    {
        "role": "user",
        "content": (
            "120 Anfragen: 71 sind strukturiert und direkt regelbasiert klassifizierbar, "
            "33 enthalten mehrdeutigen Freitext, 16 sind unvollständig und benötigen "
            "Rückfragen. Bei 25 getesteten mehrdeutigen Fällen klassifizierte ein LLM "
            "21 korrekt, 3 plausibel aber suboptimal und 1 klar falsch. Es darf keine "
            "automatische Ablehnung geben; unsichere Fälle gehen an Menschen. "
            "Bewerte für einen kontrollierten Pilot die Richtungen rules_only, "
            "llm_only und hybrid. Gib genau eine Empfehlung und genau drei knappe Gründe."
        ),
    },
]

PROBE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "issue86_reasoning_probe",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "recommendation": {
                    "type": "string",
                    "enum": ["rules_only", "llm_only", "hybrid"],
                },
                "reason_1": {"type": "string"},
                "reason_2": {"type": "string"},
                "reason_3": {"type": "string"},
                "human_escalation_required": {"type": "boolean"},
                "tested_llm_correct": {"type": "integer"},
                "tested_llm_total": {"type": "integer"},
            },
            "required": [
                "recommendation",
                "reason_1",
                "reason_2",
                "reason_3",
                "human_escalation_required",
                "tested_llm_correct",
                "tested_llm_total",
            ],
            "additionalProperties": False,
        },
    },
}


def _validate_probe_content(content: str) -> dict:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CommandError("Probe lieferte kein gültiges JSON.") from exc
    if not isinstance(payload, dict):
        raise CommandError("Probe lieferte kein JSON-Objekt.")
    if payload.get("recommendation") not in {"rules_only", "llm_only", "hybrid"}:
        raise CommandError("Probe-Empfehlung verletzt das Schema.")
    for field in ("reason_1", "reason_2", "reason_3"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise CommandError("Probe-Gründe verletzen das Schema.")
    return payload


class Command(BaseCommand):
    help = (
        "Isolierter OpenRouter/DeepInfra-Probe für medium vs. low Reasoning. "
        "Ändert keinen Investigation-Run und persistiert keine fachlichen Inhalte."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--efforts",
            default="medium,low",
            help="Kommagetrennte Reasoning-Efforts, Standard: medium,low.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=210,
            help="Wall-Clock-Limit je Probe in Sekunden, Standard: 210.",
        )
        parser.add_argument(
            "--max-tokens",
            type=int,
            default=8192,
            help="Maximale Completion-Tokens je Probe, Standard: 8192.",
        )

    def handle(self, *args, **options):
        efforts = [item.strip() for item in str(options["efforts"]).split(",") if item.strip()]
        if not efforts:
            raise CommandError("Mindestens ein Reasoning-Effort ist erforderlich.")
        if options["timeout"] < 30:
            raise CommandError("--timeout muss mindestens 30 Sekunden betragen.")
        if options["max_tokens"] < 1024:
            raise CommandError("--max-tokens muss mindestens 1024 betragen.")

        configured_model = str(settings.OPENROUTER_MODEL or "")
        if configured_model != ENDPOINT_CAPABILITY["model"]:
            raise CommandError(
                "Der Probe darf nur gegen den fixierten Investigation-Modellslug laufen: "
                f"{ENDPOINT_CAPABILITY['model']} (konfiguriert: {configured_model or '-'})"
            )

        self.stdout.write(f"probe_version={PROBE_VERSION}")
        self.stdout.write(f"model={configured_model}")
        self.stdout.write(f"provider={ENDPOINT_CAPABILITY['provider']}")
        self.stdout.write(
            "provider_fallbacks="
            f"{'yes' if ISSUE4_INVESTIGATION_PROVIDER_POLICY['allow_fallbacks'] else 'no'}"
        )
        self.stdout.write("structured_output=json_schema")
        self.stdout.write("stream=yes")
        self.stdout.write(f"timeout_seconds={options['timeout']}")
        self.stdout.write(f"max_tokens={options['max_tokens']}")
        self.stdout.write("")

        for effort in efforts:
            self.stdout.write(f"## effort={effort}")
            try:
                result = probe_openrouter_stream(
                    messages=PROBE_MESSAGES,
                    max_tokens=options["max_tokens"],
                    timeout_seconds=options["timeout"],
                    response_format=PROBE_RESPONSE_FORMAT,
                    provider=dict(ISSUE4_INVESTIGATION_PROVIDER_POLICY),
                    reasoning_effort=effort,
                    temperature=0.1,
                )
            except OpenRouterUnavailable as exc:
                self.stdout.write("status=failed")
                self.stdout.write(f"error_code={exc.code}")
                for key, value in sorted(exc.diagnostics.items()):
                    self.stdout.write(f"{key}={value}")
                self.stdout.write("")
                continue

            self.stdout.write("transport_status=success")
            self.stdout.write(f"returned_model={result.model}")
            self.stdout.write(f"duration_seconds={result.duration_seconds}")
            self.stdout.write(f"headers_seconds={result.headers_seconds}")
            self.stdout.write(f"first_event_seconds={result.first_event_seconds}")
            self.stdout.write(f"first_content_seconds={result.first_content_seconds}")
            self.stdout.write(f"event_count={result.event_count}")
            self.stdout.write(f"bytes_received={result.bytes_received}")
            self.stdout.write(f"finish_reason={result.finish_reason}")
            self.stdout.write(f"generation_id={result.generation_id or '-'}")
            self.stdout.write(f"request_id={result.request_id or '-'}")
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "reasoning_tokens",
                "cost",
            ):
                self.stdout.write(f"{key}={result.usage.get(key, '-')}")

            try:
                payload = _validate_probe_content(result.content)
            except CommandError as exc:
                preview = " ".join(result.content[:500].split())
                tail = " ".join(result.content[-300:].split())
                self.stdout.write("schema_valid=no")
                self.stdout.write(f"schema_error={exc}")
                self.stdout.write(f"content_chars={len(result.content)}")
                self.stdout.write(f"content_preview={preview}")
                self.stdout.write(f"content_tail={tail}")
                self.stdout.write("")
                continue

            self.stdout.write("schema_valid=yes")
            self.stdout.write(
                "schema_result="
                + json.dumps(
                    {
                        "recommendation": payload.get("recommendation"),
                        "reason_count": sum(
                            1
                            for field in ("reason_1", "reason_2", "reason_3")
                            if payload.get(field)
                        ),
                        "human_escalation_required": payload.get("human_escalation_required"),
                        "tested_llm_correct": payload.get("tested_llm_correct"),
                        "tested_llm_total": payload.get("tested_llm_total"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            self.stdout.write("")
