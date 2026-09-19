from django.urls import path

from . import views


urlpatterns = [

    # -----------------------------------------------------
    # BESPOKE WIZARD
    # -----------------------------------------------------

    # Keep the old URL name so any existing navbar links
    # using {% url 'bespoke_request' %} continue to work.
    path(
        "",
        views.bespoke_start,
        name="bespoke_request",
    ),

    # Individual wizard steps
    path(
        "step/<int:step>/",
        views.bespoke_step,
        name="bespoke_step",
    ),

    # -----------------------------------------------------
    # SUBMISSION COMPLETE
    # -----------------------------------------------------

    path(
        "success/<str:reference>/",
        views.bespoke_success,
        name="bespoke_success",
    ),

    # -----------------------------------------------------
    # OPTIONAL ACCOUNT CREATION AFTER SUBMISSION
    # -----------------------------------------------------

    path(
        "success/<str:reference>/register/",
        views.bespoke_register,
        name="bespoke_register",
    ),

    path(
        "success/<str:reference>/login/",
        views.bespoke_login,
        name="bespoke_login",
    ),

    # -----------------------------------------------------
    # LINK GUEST REQUEST TO ACCOUNT
    # -----------------------------------------------------

    path(
        "claim/",
        views.bespoke_claim,
        name="bespoke_claim",
    ),
]
