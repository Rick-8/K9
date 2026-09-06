from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.order_dashboard, name='order_dashboard'),
    path('<str:reference_number>/', views.order_detail, name='order_detail'),
]
