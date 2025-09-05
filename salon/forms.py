from django import forms
from .models import Appointment, WigOrder
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
import re

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['customer_name', 'customer_phone', 'customer_email', 
                 'hairstyle', 'custom_hairstyle', 'appointment_date', 'notes']
        widgets = {
            'appointment_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
    
    def clean_customer_phone(self):
        phone = self.cleaned_data.get('customer_phone')
        if not re.match(r'^\+?[0-9]{10,15}$', phone):
            raise ValidationError('Please enter a valid phone number')
        return phone

class WigOrderForm(forms.ModelForm):
    class Meta:
        model = WigOrder
        fields = ['customer_name', 'customer_phone', 'customer_email', 
                 'customer_address', 'quantity', 'payment_method']
        widgets = {
            'customer_address': forms.Textarea(attrs={'rows': 4}),
        }

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']