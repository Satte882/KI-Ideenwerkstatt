from django.contrib.auth.views import LoginView, LogoutView

from .forms import RadarAuthenticationForm


class RadarLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = RadarAuthenticationForm
    redirect_authenticated_user = True
    next_page = "demo-portal"


class RadarLogoutView(LogoutView):
    pass
