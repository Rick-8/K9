from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path(
        "resend-verification-email/",
        views.resend_verification_email,
        name="resend_verification_email",
    ),
]
