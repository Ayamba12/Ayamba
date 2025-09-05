# salon/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_appointment_request_notification(appointment):
    """Send email to admin about NEW appointment request (pending)"""
    subject = f'New Appointment Request: {appointment.service.name}'
    
    html_message = render_to_string('emails/appointment_request_notification.html', {
        'appointment': appointment,
    })
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_appointment_confirmation_to_customer(appointment):
    """Send confirmation email to customer AFTER admin confirms"""
    subject = f'Appointment Confirmed - {appointment.service.name}'
    
    html_message = render_to_string('emails/appointment_confirmed.html', {
        'appointment': appointment,
    })
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[appointment.customer_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending confirmation email: {e}")
        return False

def send_appointment_request_acknowledgement(appointment):
    """Send acknowledgement to customer that request was received (not confirmed yet)"""
    subject = f'Appointment Request Received - {appointment.service.name}'
    
    html_message = render_to_string('emails/appointment_request_received.html', {
        'appointment': appointment,
    })
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[appointment.customer_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending acknowledgement email: {e}")
        return False