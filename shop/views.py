from django.shortcuts import render


def shop_home(request):
    """
    Display the main shop landing page.
    """
    return render(request, "shop/shop_home.html")