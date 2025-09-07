import os
import django  # <-- import django before using django.setup()

from django.core.mail import send_mail
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hairsalon.settings')
django.setup()  # Initialize Django

from django.core.mail import send_mail

send_mail(
    'Test Email',
    'This is a test email from Django + SendGrid.',
    'ayambaisaac2@gmail.com',
    ['ndeogtieisaac@gmail.com'],
    fail_silently=False,
)
