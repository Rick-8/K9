import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from bespoke.models import BespokeRequest


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('sent', 'Sent / Complete'),
        ('cancelled', 'Cancelled'),
    ]

    ORDER_TYPE_CHOICES = [
        ('bespoke', 'Bespoke'),
        ('shop', 'Shop'),
    ]

    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='shop')

    bespoke_request = models.ForeignKey(BespokeRequest, on_delete=models.SET_NULL, null=True, blank=True)

    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)

    order_total = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = f"K9-{uuid.uuid4().hex[:8].upper()}"

        if self.status == 'sent' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'sent':
            self.completed_at = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_number} | {self.customer_name}"


class OrderNote(models.Model):
    NOTE_TYPE_CHOICES = [
        ('internal', 'Internal Staff Note'),
        ('system', 'System Update'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notes')
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='internal')
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_note_type_display()} | {self.order.reference_number}"
