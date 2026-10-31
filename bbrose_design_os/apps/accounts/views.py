"""Non-admin login/logout (Milestone 11.1 / audit H2).

Before Phase 11 LOGIN_URL pointed at /admin/login/, which forced every
designer account to have is_staff (= full Django admin access). These views
give the team a real login page with zero staff requirement.
"""
from django.contrib.auth import views as auth_views


class BbroseLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class BbroseLogoutView(auth_views.LogoutView):
    # settings.LOGOUT_REDIRECT_URL sends the user back to the login page.
    # [the owner's answer to the UI directions of 2026-09-25: the one top bar carries no form — the read-only pages carry
    # no POST form, and their tests hold them to it — so "Sign out" opens this confirmation, and its one button POSTs
    # to this same door, which signs out exactly as before. A GET changes nothing.]
    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        from django.shortcuts import render
        return render(request, "accounts/logout_confirm.html")
