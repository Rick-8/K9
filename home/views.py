from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from allauth.account.models import EmailAddress

from .forms import SiteBannerForm
from .models import SiteBanner


# =========================================================
# HOME
# =========================================================

def home_view(request):
    return render(request, "home/index.html")


# =========================================================
# EMAIL VERIFICATION
# =========================================================

@require_POST
def resend_verification_email(request):
    """
    Resend an email verification link for an unverified account.

    The response deliberately does not confirm whether the email
    address exists in the database, helping prevent account
    enumeration.
    """

    email = request.POST.get("email", "").strip().lower()

    if email:
        email_address = (
            EmailAddress.objects
            .select_related("user")
            .filter(
                email__iexact=email,
                verified=False,
            )
            .first()
        )

        if email_address:
            email_address.send_confirmation(
                request,
                signup=True,
            )

    messages.success(
        request,
        (
            "If that email address is awaiting verification, "
            "a new verification email has been sent. "
            "Please check your inbox and your spam or junk folder."
        ),
        extra_tags="verification_resend",
    )

    return redirect("account_email_verification_sent")


# =========================================================
# SUPERUSER CHECK
# =========================================================

def superuser_required(view_func):
    """
    Restrict a view to authenticated superusers only.
    """

    return user_passes_test(
        lambda user: user.is_authenticated and user.is_superuser
    )(view_func)


# =========================================================
# WEBSITE BANNER CONTROL
# =========================================================

@superuser_required
def banner_control(request):
    """
    Allow a superuser to control the global website banner.
    """

    banner, created = SiteBanner.objects.get_or_create(
        pk=1,
        defaults={
            "enabled": False,
            "text": (
                "Welcome to K9 — handmade gifts, personalised "
                "creations and completely bespoke designs."
            ),
            "display_mode": SiteBanner.MODE_SCROLL,
        },
    )

    if request.method == "POST":

        form = SiteBannerForm(
            request.POST,
            instance=banner,
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Website banner settings have been updated.",
            )

            return redirect("banner_control")

    else:

        form = SiteBannerForm(
            instance=banner,
        )

    context = {
        "form": form,
        "banner": banner,
    }

    return render(
        request,
        "home/banner_control.html",
        context,
    )
