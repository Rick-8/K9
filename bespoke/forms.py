from django import forms
from .models import BespokeRequest


class BespokeRequestForm(forms.ModelForm):
    class Meta:
        model = BespokeRequest
        fields = ['name', 'email', 'phone', 'item_type', 'description', 'budget']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your.email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional phone number'}),
            'item_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Custom Pet Portrait'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tell us what you want made...'}),
            'budget': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., £50 - £100'}),
        }
