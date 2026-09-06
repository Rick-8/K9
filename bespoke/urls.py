from django.urls import path
from . import views

urlpatterns = [
    path('', views.bespoke_request_view, name='bespoke_request'),
]
