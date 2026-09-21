from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ki_radar.accelerator.block7_demo import run_block7_real_demo


class Command(BaseCommand):
    help = "Führt den reproduzierbaren [Real-DEMO]-Nachweis für Accelerator Block 7 aus."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=Path,
            help="Optionaler Pfad für den JSON-Abschlussnachweis.",
        )

    def handle(self, *args, **options):
        report = run_block7_real_demo()
        serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        output_path = options["output"]
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(f"{serialized}\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"[Real-DEMO] Block 7 abgeschlossen\n{serialized}"))
