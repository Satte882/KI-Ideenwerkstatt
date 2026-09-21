import os
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ki_radar.core.demo_architecture_data import (
    DOCUMENT_USE_CASE_KEY,
    INVOICE_USE_CASE_KEY,
    seed_demo_architecture_data,
)
from ki_radar.core.demo_data import seed_demo_data
from ki_radar.core.demo_decision_data import enrich_demo_metrics
from ki_radar.core.demo_identity import assign_demo_identities, prepare_demo_identities
from ki_radar.core.golden_path_demo import seed_supplier_golden_path_demo
from ki_radar.delivery.services import current_handed_over_package
from ki_radar.use_cases.models import UseCase


class Command(BaseCommand):
    help = "Create or restore the reproducible KI-Radar demo dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            dest="demo_user_password",
            help="Password for all demo users. Defaults to DEMO_USER_PASSWORD or a random value.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo_data is only allowed with DEBUG=True. "
                "Do not create demo users in staging or production."
            )

        password = options["demo_user_password"] or os.getenv("DEMO_USER_PASSWORD")
        generated_password = password is None
        if generated_password:
            password = secrets.token_urlsafe(18)
        elif not password.strip():
            raise CommandError("Demo user password must not be empty.")

        prepare_demo_identities()
        counts = seed_demo_data(demo_user_password=password)
        metric_count = enrich_demo_metrics()
        architecture_counts = seed_demo_architecture_data()
        golden_counts = seed_supplier_golden_path_demo()
        assign_demo_identities()

        today = timezone.localdate()
        invoice = UseCase.objects.get(demo_key=INVOICE_USE_CASE_KEY)
        invoice.status = UseCase.Status.REVIEW
        invoice.pilot_start = None
        invoice.planned_pilot_end = today + timedelta(days=30)
        invoice.next_review_date = today + timedelta(days=14)
        invoice.realized_result = ""
        invoice.save(
            update_fields=[
                "status",
                "pilot_start",
                "planned_pilot_end",
                "next_review_date",
                "realized_result",
                "updated_at",
            ]
        )

        document = UseCase.objects.get(demo_key=DOCUMENT_USE_CASE_KEY)
        document_package = current_handed_over_package(document)
        if document_package is None:
            raise CommandError("The document routing demo requires a handed-over Delivery Package.")
        document.status = UseCase.Status.PILOT
        document.pilot_start = timezone.localdate(document_package.handed_over_at)
        document.planned_pilot_end = today + timedelta(days=30)
        document.next_review_date = today - timedelta(days=3)
        document.save(
            update_fields=[
                "status",
                "pilot_start",
                "planned_pilot_end",
                "next_review_date",
                "updated_at",
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo-Daten eingespielt: "
                f"{counts['business_units']} Organisationseinheiten, "
                f"{counts['users']} Benutzer, "
                f"{counts['use_cases'] + golden_counts['use_cases']} Use Cases, "
                f"{counts['governance_assessments']} Governance-Screenings, "
                f"{counts['reviews']} Reviews, "
                f"{metric_count} strukturierte Erfolgsmetriken, "
                f"{architecture_counts['value_streams'] + golden_counts['value_streams']} "
                "Value Streams, "
                f"{architecture_counts['process_analyses'] + 1} Prozessanalysen, "
                f"{architecture_counts['solution_options'] + 1} Lösungsoptionen und "
                f"{architecture_counts['delivery_packages'] + golden_counts['delivery_packages']} "
                "Delivery Packages."
            )
        )
        if generated_password:
            self.stdout.write(
                self.style.WARNING("Zufaelliges Demo-Passwort fuer alle Demo-Benutzer: " + password)
            )
        else:
            self.stdout.write("Demo-Benutzerpasswort aus Option oder DEMO_USER_PASSWORD gesetzt.")
