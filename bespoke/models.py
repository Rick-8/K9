from django.db import models


class BespokeRequest(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    item_type = models.CharField(max_length=150, help_text="e.g., Custom Engraved Plaque, Pet Memorial, Custom Gift Box")
    description = models.TextField(help_text="Describe your custom vision, dimensions, or specific requirements.")
    budget = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bespoke Request by {self.name} - {self.item_type}"
