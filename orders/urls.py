from django.urls import path

from . import staff_views
from . import views


urlpatterns = [

    # =====================================================
    # STAFF WORKSPACE
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

    # =====================================================
    # SUPERUSER BESPOKE MANAGEMENT
    # =====================================================

    path(
        "staff/bespoke/",
        views.bespoke_jobs_dashboard,
        name="bespoke_jobs_dashboard",
    ),

    # =====================================================
    # MASTER ORDER MANAGEMENT
    # =====================================================

    path(
        "dashboard/",
        views.order_dashboard,
        name="order_dashboard",
    ),

    # =====================================================
    # ORDER DETAIL
    # KEEP LAST
    # =====================================================

    path(
        "<str:reference_number>/",
        views.order_detail,
        name="order_detail",
    ),
]
