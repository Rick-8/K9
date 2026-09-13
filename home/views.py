from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from allauth.account.models import EmailAddress


def home_view(request):
    return render(request, "home/index.html")


@require_POST
def resend_verification_email(request):
    """
    Resend an email verification link for an unverified account.

    The response deliberately does not confirm whether the email address
    exists in the database, helping prevent account enumeration.
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
