from django.db import models


class SiteBanner(models.Model):
    """
    Global promotional banner displayed at the top of the K9 website.

    Only one banner record is intended to exist.
    """

    MODE_STATIC = "static"
    MODE_SCROLL = "scroll"
    MODE_FLASH = "flash"
    MODE_BOTH = "both"

    MODE_CHOICES = [
        (MODE_STATIC, "Static"),
        (MODE_SCROLL, "Scrolling"),
        (MODE_FLASH, "Flashing"),
        (MODE_BOTH, "Scrolling + Flashing"),
    ]

    enabled = models.BooleanField(
        default=False,
        help_text="Switch the website banner on or off.",
    )

    text = models.CharField(
        max_length=500,
        default="Welcome to K9 — handmade gifts, personalised creations and completely bespoke designs.",
        help_text="The message shown in the banner.",
    )

    display_mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default=MODE_SCROLL,
        help_text="Choose how the banner message is displayed.",
    )

    link_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional clickable text, for example: Shop Now.",
    )

    link_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional URL for the banner link.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Site Banner"
        verbose_name_plural = "Site Banner"

    def __str__(self):
        return "K9 Website Banner"
