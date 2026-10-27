from django.urls import path

from . import views

app_name = "solo"
urlpatterns = [
    path("", views.panel, name="panel"),
    path("switch/", views.switch, name="switch"),
    path("discovery/<str:case>/", views.discovery, name="discovery"),
]
