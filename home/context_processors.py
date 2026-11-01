from .models import SiteBanner


def site_banner(request):
    """
    Make the global K9 promotional banner available
    to every template.
    """

    banner = (
        SiteBanner.objects
        .filter(pk=1)
        .first()
    )

    return {
        "site_banner": banner,
    }
