import json

from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator import benchmark_measurement as measurement
from ki_radar.accelerator.models import CaptureSession


class Command(BaseCommand):
    help = "Append one frozen Block-9 benchmark run to a raw JSONL file."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--path", required=True)
        parser.add_argument("--case", dest="case_key", required=True)
        parser.add_argument(
            "--benchmark-version",
            default=measurement.BENCHMARK_VERSION,
            choices=sorted(measurement.SUPPORTED_BENCHMARK_VERSIONS),
        )
        parser.add_argument("--status", default="completed")
        parser.add_argument("--quality-json", default="{}")
        parser.add_argument("--capture-session")
        parser.add_argument("--delivery-json", default="")
        parser.add_argument("--notes", default="")
        for key in measurement.TIME_KEYS:
            parser.add_argument(f"--{key.replace('_', '-')}", type=float, default=0)

    def handle(self, *args, **options):
        try:
            quality = json.loads(options["quality_json"])
            delivery = json.loads(options["delivery_json"]) if options["delivery_json"] else None
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON argument: {exc}") from exc
        unknown_quality = set(quality) - set(measurement.QUALITY_KEYS)
        if unknown_quality:
            raise CommandError(f"Unknown quality keys: {sorted(unknown_quality)}")

        session = None
        session_id = options["capture_session"]
        if session_id:
            try:
                session = CaptureSession.objects.get(pk=session_id)
            except (CaptureSession.DoesNotExist, ValueError) as exc:
                raise CommandError(f"Unknown capture session: {session_id}") from exc

        times = {key: options[key] for key in measurement.TIME_KEYS}
        try:
            record = measurement.build_raw_record(
                benchmark_version=options["benchmark_version"],
                run_id=options["run_id"],
                path=options["path"],
                case_key=options["case_key"],
                status=options["status"],
                times=times,
                quality=quality,
                capture_session=session,
                delivery=delivery,
                notes=options["notes"],
            )
            measurement.append_raw_record(options["output"], record)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Recorded {options['run_id']}"))
