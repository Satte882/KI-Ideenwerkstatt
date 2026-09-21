from django.urls import path

from .views import dashboard, outcome_workspace, portfolio

app_name = "reporting"
urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("portfolio/", portfolio, name="portfolio"),
    path("wirkung-betrieb/", outcome_workspace, name="outcome_workspace"),
]
