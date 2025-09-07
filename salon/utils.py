from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import logging
from django.core.mail.backends.base import BaseEmailBackend
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, To, From, Subject, TrackingSettings, ClickTracking, OpenTracking
import json

logger = logging.getLogger(__name__)

# Create a SendGrid client instance
sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

# Email Functions using SendGrid directly
def send_sendgrid_email(to_email, subject, html_content, from_email=None):
    """Send email using SendGrid API directly"""
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    try:
        # Create Mail object with HTML content
        mail = Mail(
            from_email=From(from_email),
            to_emails=To(to_email),
            subject=Subject(subject),
            html_content=Content("text/html", html_content)
        )
        
        # Add tracking settings if configured
        if hasattr(settings, 'SENDGRID_TRACKING_SETTINGS'):
            tracking_settings = TrackingSettings()
            if settings.SENDGRID_TRACKING_SETTINGS.get('click_tracking', True):
                tracking_settings.click_tracking = ClickTracking(
                    enable=True,
                    enable_text=True
                )
            if settings.SENDGRID_TRACKING_SETTINGS.get('open_tracking', True):
                tracking_settings.open_tracking = OpenTracking(enable=True)
            mail.tracking_settings = tracking_settings
        
        # Send email
        response = sg.send(mail)
        
        if response.status_code in [200, 202]:
            logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            logger.error(f"SendGrid API error: {response.status_code} - {response.body}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending email via SendGrid: {e}")
        return False

def send_appointment_request_notification(appointment):
    """Send email to admin about NEW appointment request (pending)"""
    subject = f'New Appointment Request: {appointment.service.name}'
    
    html_message = render_to_string('emails/appointment_request_notification.html', {
        'appointment': appointment,
    })
    
    return send_sendgrid_email(settings.ADMIN_EMAIL, subject, html_message)

def send_appointment_request_acknowledgement(appointment):
    """Send acknowledgement to customer that request was received (not confirmed yet)"""
    subject = f'Appointment Request Received - {appointment.service.name}'
    
    html_message = render_to_string('emails/appointment_request_received.html', {
        'appointment': appointment,
    })
    
    return send_sendgrid_email(appointment.customer_email, subject, html_message)

def send_appointment_confirmation_to_customer(appointment):
    """Send confirmation email to customer AFTER admin confirms"""
    subject = f'Appointment Confirmed - {appointment.service.name}'
    
    try:
        html_message = render_to_string('emails/appointment_confirmed.html', {
            'appointment': appointment,
        })
        
        return send_sendgrid_email(appointment.customer_email, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending appointment confirmation email: {e}", exc_info=True)
        return False

def send_order_confirmation_to_customer(order, order_type):
    """Send confirmation email to customer after order is confirmed"""
    if order_type == 'wig':
        subject = f'Order Confirmed - Wig Purchase'
        template = 'emails/wig_order_confirmed.html'
    else:  # product order
        subject = f'Order Confirmed - Product Purchase'
        template = 'emails/product_order_confirmed.html'
    
    try:
        html_message = render_to_string(template, {
            'order': order,
            'order_type': order_type,
        })
        
        return send_sendgrid_email(order.customer_email, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending order confirmation email: {e}", exc_info=True)
        return False

def send_order_cancellation_email(order, order_type):
    """Send cancellation email to customer when order is cancelled"""
    if order_type == 'wig':
        subject = f'Order Cancelled - Wig Purchase'
        template = 'emails/wig_order_cancelled.html'
    else:  # product order
        subject = f'Order Cancelled - Product Purchase'
        template = 'emails/product_order_cancelled.html'
    
    try:
        html_message = render_to_string(template, {
            'order': order,
            'order_type': order_type,
        })
        
        return send_sendgrid_email(order.customer_email, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending order cancellation email: {e}", exc_info=True)
        return False

def send_appointment_cancellation_email(appointment, reason):
    """Send cancellation email to customer with reason"""
    subject = f'Appointment Cancelled - {appointment.service.name}'
    
    try:
        html_message = render_to_string('emails/appointment_cancelled.html', {
            'appointment': appointment,
            'reason': reason,
        })
        
        return send_sendgrid_email(appointment.customer_email, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending appointment cancellation email: {e}", exc_info=True)
        return False

def send_appointment_cancellation_notification_to_admin(appointment, reason):
    """Send notification to admin when client cancels"""
    subject = f'Client Cancellation: {appointment.service.name} - {appointment.customer_name}'
    
    try:
        html_message = render_to_string('emails/appointment_cancelled_admin.html', {
            'appointment': appointment,
            'reason': reason,
        })
        
        return send_sendgrid_email(settings.ADMIN_EMAIL, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending admin cancellation notification: {e}", exc_info=True)
        return False

def send_appointment_cancellation_confirmation(appointment, reason):
    """Send confirmation email to client when they cancel"""
    subject = f'Appointment Cancellation Confirmation - {appointment.service.name}'
    
    try:
        html_message = render_to_string('emails/appointment_cancelled_client.html', {
            'appointment': appointment,
            'reason': reason,
        })
        
        return send_sendgrid_email(appointment.customer_email, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending client cancellation confirmation: {e}", exc_info=True)
        return False

def send_payment_confirmation_to_customer(appointment):
    """Send payment confirmation email to customer"""
    subject = f'Payment Confirmed - {appointment.service.name}'
    
    try:
        html_message = render_to_string('emails/payment_confirmed.html', {
            'appointment': appointment,
        })
        
        return send_sendgrid_email(appointment.customer_email, subject, html_message)
    except Exception as e:
        logger.error(f"Error sending payment confirmation email: {e}", exc_info=True)
        return False

# Utility Functions (unchanged)
def process_payment_method(request):
    """Handle payment method processing consistently"""
    payment_method = request.POST.get('payment_method', 'cash')
    payment_status = 'paid' if payment_method == 'momo' else 'pending'
    return payment_method, payment_status

def validate_appointment_time(appointment_date):
    """Validate appointment time constraints"""
    if appointment_date < timezone.now():
        raise ValidationError("You cannot book an appointment in the past.")
    if not (8 <= appointment_date.hour < 22):
        raise ValidationError("Appointments can only be booked between 8:00 AM and 10:00 PM.")

def calculate_duration(subservice=None, estimated_duration=None):
    """Calculate duration consistently"""
    if subservice and subservice.duration:
        return subservice.duration
    elif estimated_duration:
        return estimated_duration
    return timedelta(minutes=60)

def check_time_conflict(service, start_time, duration, exclude_appointment=None):
    """Check for time conflicts - reusable function"""
    from .models import Appointment
    
    end_time = start_time + duration
    end_with_buffer = end_time + timedelta(minutes=10)
    
    existing = Appointment.objects.filter(
        service=service,
        status__in=["pending", "confirmed"]
    )
    
    if exclude_appointment:
        existing = existing.exclude(pk=exclude_appointment.pk)
    
    for other in existing:
        other_duration = calculate_duration(other.subservice, other.estimated_duration)
        other_start = other.appointment_date
        other_end = other_start + other_duration
        other_end_with_buffer = other_end + timedelta(minutes=10)
        
        if start_time < other_end_with_buffer and other_start < end_with_buffer:
            return {
                'conflict': True,
                'conflict_start': other_start,
                'conflict_end': other_end_with_buffer
            }
    
    return {'conflict': False}

# Enhanced SendGridEmailBackend
class SendGridEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        success_count = 0
        for email_message in email_messages:
            try:
                # Create Mail object with HTML content
                mail = Mail(
                    from_email=From(email_message.from_email or settings.DEFAULT_FROM_EMAIL),
                    to_emails=To(email_message.to),
                    subject=Subject(email_message.subject),
                    html_content=Content("text/html", email_message.body)
                )
                
                # Add tracking settings if configured
                if hasattr(settings, 'SENDGRID_TRACKING_SETTINGS'):
                    tracking_settings = TrackingSettings()
                    if settings.SENDGRID_TRACKING_SETTINGS.get('click_tracking', True):
                        tracking_settings.click_tracking = ClickTracking(
                            enable=True,
                            enable_text=True
                        )
                    if settings.SENDGRID_TRACKING_SETTINGS.get('open_tracking', True):
                        tracking_settings.open_tracking = OpenTracking(enable=True)
                    mail.tracking_settings = tracking_settings
                
                # Send email
                response = self.sg.send(mail)
                if response.status_code in [200, 202]:
                    success_count += 1
                    logger.info(f"Email sent successfully to {email_message.to}")
                else:
                    logger.error(f"SendGrid API error: {response.status_code} - {response.body}")
                    
            except Exception as e:
                logger.error(f"Error sending email via SendGrid: {e}")
                if not self.fail_silently:
                    raise
        
        return success_count