from pathlib import Path

import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from psycopg import sql

from ki_radar.accounts.models import BusinessUnit
from ki_radar.solo import access
from ki_radar.solo.access import MASTER, ROLES, UNIT


class Command(BaseCommand):
    help = "Prepare only the dedicated local solo DB; preserve existing practice data."

    def add_arguments(self, parser):
        parser.add_argument("--password-file", required=True)
        parser.add_argument("--create-database", action="store_true")

    def handle(self, *args, **options):
        access.require_isolation()
        password = Path(options["password_file"]).read_text(encoding="utf-8").strip()
        if len(password) < 16:
            raise CommandError("Master password must contain at least 16 characters.")
        if options["create_database"]:
            database = settings.DATABASES["default"]
            with psycopg.connect(
                dbname="postgres",
                user=database["USER"],
                password=database["PASSWORD"],
                host=database["HOST"],
                port=database["PORT"],
                autocommit=True,
            ) as connection:
                if not connection.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", [database["NAME"]]
                ).fetchone():
                    connection.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database["NAME"]))
                    )
        call_command("migrate", interactive=False, verbosity=0)
        with transaction.atomic():
            unit, _ = BusinessUnit.objects.get_or_create(
                name=UNIT,
                defaults={"catalog_scope": "productive", "is_active": True},
            )
            if unit.catalog_scope not in {"demo_test", "productive"} or not unit.is_active:
                raise CommandError("Existing solo unit differs from the expected configuration.")
            # The regular discovery catalog accepts only active organizational units.
            # In this dedicated synthetic DB the normal catalog classification is kept;
            # no domain permission or production data is changed.
            if unit.catalog_scope == "demo_test":
                unit.catalog_scope = "productive"
                unit.save(update_fields=["catalog_scope", "updated_at"])
            master, made = get_user_model().objects.get_or_create(
                username=MASTER,
                defaults={"is_staff": True, "is_superuser": True, "business_unit": unit},
            )
            if made:
                master.set_password(password)
                master.save()
            elif (
                not master.is_superuser
                or not master.is_active
                or not master.check_password(password)
            ):
                raise CommandError(
                    "Existing master differs; no password or rights were overwritten."
                )
            for username, label, group in ROLES.values():
                user, made = get_user_model().objects.get_or_create(
                    username=username,
                    defaults={"first_name": label, "business_unit": unit},
                )
                if made:
                    user.set_unusable_password()
                    user.save()
                    role, _ = Group.objects.get_or_create(name=group)
                    user.groups.add(role)
                elif (
                    user.is_staff
                    or user.is_superuser
                    or not user.is_active
                    or user.business_unit_id != unit.pk
                    or set(user.groups.values_list("name", flat=True)) != {group}
                ):
                    raise CommandError("Existing test identity differs; no roles were overwritten.")
        self.stdout.write(
            "Solo database ready. Login: solo_master. Existing practice data preserved."
        )
