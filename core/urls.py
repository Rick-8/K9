from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView


urlpatterns = [

    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "accounts/",
        include("allauth.urls"),
    ),

    path(
        "signup-complete/",
        TemplateView.as_view(
            template_name="account/signup_complete.html"
        ),
        name="signup_complete",
    ),

    path(
        "bespoke/",
        include("bespoke.urls"),
    ),

    path(
        "orders/",
        include("orders.urls"),
    ),

    path(
        "",
        include("home.urls"),
    ),

    path(
        "shop/",
        include("shop.urls"),
    ),

]
