from django.urls import path

from .views import RadarLoginView, RadarLogoutView

app_name = "accounts"
urlpatterns = [
    path("login/", RadarLoginView.as_view(), name="login"),
    path("logout/", RadarLogoutView.as_view(), name="logout"),
]
