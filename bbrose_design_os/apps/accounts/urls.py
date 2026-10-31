from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.BbroseLoginView.as_view(), name="login"),
    path("logout/", views.BbroseLogoutView.as_view(), name="logout"),
]
