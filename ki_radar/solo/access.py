import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.utils.crypto import constant_time_compare

from ki_radar.accounts.permissions import (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    GROUP_READER,
    GROUP_TECH_ADMIN,
)

logger = logging.getLogger(__name__)
MASTER = "solo_master"
UNIT = "[SOLO] Synthetischer Test-Service"
GRANT = "solo_master_grant"
DRAFTS = "solo_identity_drafts"
ROLES = {
    "owner": ("solo_owner", "Business Owner", GROUP_BUSINESS_OWNER),
    "coordination": ("solo_coordination", "KI-Koordination", GROUP_COORDINATOR),
    "review": ("solo_review", "Zweite KI-Koordination", GROUP_COORDINATOR),
    "technical": ("solo_technical", "Technischer Administrator", GROUP_TECH_ADMIN),
    "reader": ("solo_reader", "Leser", GROUP_READER),
}


def require_isolation():
    database = settings.DATABASES["default"]
    if not (
        getattr(settings, "SOLO_TEST_MODE", False)
        and settings.SETTINGS_MODULE == "config.settings.solo"
        and settings.DEBUG
        and database["ENGINE"] == "django.db.backends.postgresql"
        and str(database["NAME"]).startswith("ki_radar_solo")
        and database["HOST"] in {"127.0.0.1", "localhost", "::1"}
    ):
        raise PermissionDenied(
            "Solo-Testzugang ist nur in der isolierten lokalen Umgebung erlaubt."
        )


def master_for(request):
    require_isolation()
    if not request.user.is_authenticated:
        raise PermissionDenied
    token = request.session.get(GRANT)
    if token:
        try:
            claim = signing.loads(token, salt=GRANT, max_age=14400)
            master = get_user_model().objects.get(
                pk=claim["id"], username=MASTER, is_active=True, is_superuser=True
            )
            if not constant_time_compare(claim["hash"], master.get_session_auth_hash()):
                raise PermissionDenied
        except (signing.BadSignature, KeyError, get_user_model().DoesNotExist) as exc:
            raise PermissionDenied("Master-Anmeldung abgelaufen; bitte erneut anmelden.") from exc
        return master
    if request.user.username != MASTER or not request.user.is_superuser:
        raise PermissionDenied
    request.session[GRANT] = signing.dumps(
        {"id": request.user.pk, "hash": request.user.get_session_auth_hash()}, salt=GRANT
    )
    return request.user


def valid_target(target, group):
    return (
        target.is_active
        and not target.is_superuser
        and not target.is_staff
        and set(target.groups.values_list("name", flat=True)) == {group}
        and target.business_unit_id
        and target.business_unit.catalog_scope == "productive"
        and target.business_unit.name == UNIT
        and target.business_unit.is_active
    )


def switch_identity(request, role):
    from ki_radar.use_cases.intake_views import IDEA_CANDIDATE_SESSION_KEY, SESSION_KEY

    master = master_for(request)
    if role == "master":
        target = master
    else:
        if role not in ROLES:
            raise PermissionDenied
        username, _, group = ROLES[role]
        target = get_user_model().objects.filter(username=username, is_active=True).first()
        if not target or not valid_target(target, group):
            raise PermissionDenied("Testidentität wurde verändert; Einrichtung prüfen.")
    grant = request.session[GRANT]
    previous = request.user.pk
    # Django correctly flushes session state when the authenticated user changes.
    # Retain only the existing intake's two data keys, separately for each user;
    # never transfer auth, CSRF, messages or another identity's active draft.
    drafts = request.session.get(DRAFTS, {})
    drafts[str(previous)] = {
        key: request.session[key]
        for key in (SESSION_KEY, IDEA_CANDIDATE_SESSION_KEY)
        if key in request.session
    }
    login(request, target, backend="django.contrib.auth.backends.ModelBackend")
    request.session[GRANT] = grant
    request.session[DRAFTS] = drafts
    for key, value in drafts.get(str(target.pk), {}).items():
        request.session[key] = value
    logger.info(
        "solo_identity_switch master=%s previous=%s effective=%s", master.pk, previous, target.pk
    )


class LocalSoloMiddleware:
    def __init__(self, get_response):
        require_isolation()
        self.get_response = get_response

    def __call__(self, request):
        require_isolation()
        if request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"} or (
            urlsplit("//" + request.get_host()).hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            return HttpResponseForbidden(
                "Solo-Testzugang akzeptiert ausschließlich lokale Zugriffe."
            )
        if request.user.is_authenticated:
            try:
                master_for(request)
                if request.user.username != MASTER:
                    group = next(
                        (row[2] for row in ROLES.values() if row[0] == request.user.username), None
                    )
                    if not group or not valid_target(request.user, group):
                        raise PermissionDenied
            except PermissionDenied:
                logout(request)
                return HttpResponseForbidden("Bitte den lokalen Master erneut anmelden.")
            if (
                request.user.username == MASTER
                and request.method not in {"GET", "HEAD", "OPTIONS"}
                and request.path not in {"/solo/switch/", "/accounts/logout/"}
            ):
                return HttpResponseForbidden("Für Fachaktionen zuerst eine Testrolle wählen.")
        return self.get_response(request)


def context(request):
    if not getattr(settings, "SOLO_TEST_MODE", False):
        return {}
    return {"solo_mode": True}
