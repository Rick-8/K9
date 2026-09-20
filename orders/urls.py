from django.urls import path

from . import customer_views
from . import payment_views
from . import quote_views
from . import staff_views
from . import views


urlpatterns = [

    # =====================================================
    # PUBLIC CUSTOMER DESIGN REVIEW
    # =====================================================

    path(
        "design-review/<uuid:token>/",
        customer_views.design_review,
        name="customer_design_review",
    ),


    # =====================================================
    # PUBLIC CUSTOMER QUOTE REVIEW / ACCEPTANCE
    # =====================================================

    path(
        "quote-review/<uuid:token>/",
        quote_views.quote_review,
        name="customer_quote_review",
    ),


    # =====================================================
    # STRIPE PAYMENT
    # =====================================================

    path(
        "payments/stripe/start/<uuid:token>/",
        payment_views.stripe_start,
        name="stripe_start",
    ),

    path(
        "payments/stripe/return/<uuid:token>/",
        payment_views.stripe_return,
        name="stripe_return",
    ),

    path(
        "payments/stripe/webhook/",
        payment_views.stripe_webhook,
        name="stripe_webhook",
    ),


    # =====================================================
    # PAYPAL PAYMENT
    # =====================================================

    path(
        "payments/paypal/start/<uuid:token>/",
        payment_views.paypal_start,
        name="paypal_start",
    ),

    path(
        "payments/paypal/return/<uuid:token>/",
        payment_views.paypal_return,
        name="paypal_return",
    ),


    # =====================================================
    # STAFF JOB WORKFLOW
    # =====================================================

    path(
        "staff/",
        staff_views.staff_jobs_dashboard,
        name="staff_jobs_dashboard",
    ),

    path(
        "staff/jobs/<str:reference_number>/<int:step>/",
        staff_views.bespoke_job_wizard,
        name="bespoke_job_wizard",
    ),

    path(
        "staff/quotes/<int:quote_id>/pdf/",
        staff_views.bespoke_quote_pdf,
        name="bespoke_quote_pdf",
    ),


    # =====================================================
    # MANAGEMENT
    # =====================================================

    path(
        "staff/bespoke/",
        views.bespoke_jobs_dashboard,
        name="bespoke_jobs_dashboard",
    ),

    path(
        "dashboard/",
        views.order_dashboard,
        name="order_dashboard",
    ),


    # =====================================================
    # ORDER DETAIL - KEEP LAST
    # =====================================================

    path(
        "<str:reference_number>/",
        views.order_detail,
        name="order_detail",
    ),

]
