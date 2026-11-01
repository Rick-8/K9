from django import forms

from .models import SiteBanner


class SiteBannerForm(forms.ModelForm):

    class Meta:
        model = SiteBanner

        fields = [
            "enabled",
            "text",
            "display_mode",
            "link_text",
            "link_url",
        ]

        widgets = {
            "enabled": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                    "role": "switch",
                }
            ),

            "text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Enter the promotional message "
                        "to display across the website..."
                    ),
                }
            ),

            "display_mode": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "link_text": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Shop Now",
                }
            ),

            "link_url": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. /shop/",
                }
            ),
        }
