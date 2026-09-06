from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('bespoke/', include('bespoke.urls')),
    path('orders/', include('orders.urls')),
    path('', include('home.urls')),
]
