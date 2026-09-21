from django.contrib import admin
from django.urls import include, path

from ki_radar.core import health, portal

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("ki_radar.accounts.urls")),
    path("start/", portal.demo_portal, name="demo-portal"),
    path("cases/angebotsvergleich-einkauf/", portal.procurement_case, name="case-procurement"),
    path(
        "cases/sales-conversation-intelligence/",
        portal.sales_conversation_case,
        name="case-sales-conversation",
    ),
    path("accelerator/", include("ki_radar.accelerator.urls")),
    path("architecture/", include("ki_radar.architecture.urls")),
    path("use-cases/", include("ki_radar.use_cases.urls")),
    path("governance/", include("ki_radar.governance.urls")),
    path("reviews/", include("ki_radar.reviews.urls")),
    path("evidence/", include("ki_radar.notifications.urls")),
    path("delivery/", include("ki_radar.delivery.urls")),
    path("review-export/", include("ki_radar.review_export_urls")),
    path("", include("ki_radar.reporting.urls")),
    path("health/live", health.liveness, name="health-live"),
    path("health/ready", health.readiness, name="health-ready"),
    path("health/operations", health.operational_health, name="health-operations"),
]
