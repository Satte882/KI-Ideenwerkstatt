from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import SystemJobRun


@require_GET
@never_cache
def liveness(request):
    return JsonResponse({"status": "ok", "version": settings.APP_VERSION})


@require_GET
@never_cache
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready", "version": settings.APP_VERSION})


def _authorized(request) -> bool:
    token = settings.MONITORING_TOKEN
    supplied = request.headers.get("X-Monitoring-Token", "")
    return bool(token) and supplied == token


@require_GET
@never_cache
def operational_health(request):
    if not _authorized(request):
        return JsonResponse({"detail": "not found"}, status=404)

    threshold = timezone.now() - timedelta(hours=settings.JOB_FRESHNESS_HOURS)
    required_jobs = ["database_backup", "review_scan"]
    jobs = {}
    healthy = True

    for job_name in required_jobs:
        runs = SystemJobRun.objects.filter(job_name=job_name)
        latest = runs.order_by("-started_at").first()
        last_success = (
            runs.filter(status=SystemJobRun.Status.SUCCESS).order_by("-finished_at").first()
        )
        is_fresh = bool(
            latest
            and latest.status == SystemJobRun.Status.SUCCESS
            and last_success
            and last_success.finished_at
            and last_success.finished_at >= threshold
        )
        jobs[job_name] = {
            "healthy": is_fresh,
            "last_run_status": latest.status if latest else None,
            "last_run_finished_at": latest.finished_at.isoformat()
            if latest and latest.finished_at
            else None,
            "last_success": last_success.finished_at.isoformat()
            if last_success and last_success.finished_at
            else None,
        }
        healthy = healthy and is_fresh

    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "jobs": jobs},
        status=200 if healthy else 503,
    )
