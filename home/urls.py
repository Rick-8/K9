from django.urls import path

from . import views


urlpatterns = [

    # =====================================================
    # HOME
    # =====================================================

    path(
        "",
        views.home_view,
        name="home",
    ),

    # =====================================================
    # EMAIL VERIFICATION
    # =====================================================

    path(
        "resend-verification-email/",
        views.resend_verification_email,
        name="resend_verification_email",
    ),

    # =====================================================
    # WEBSITE MANAGEMENT
    # =====================================================

    path(
        "management/banner/",
        views.banner_control,
        name="banner_control",
    ),

]
