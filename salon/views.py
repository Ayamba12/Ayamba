from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import date, timedelta
from django.contrib.auth import get_user_model
import logging
from .forms import UserRegisterForm
from django.db import transaction
from .models import Service, HairStyle, Wig, Appointment, WigOrder, SubService, ProductOrder
from .utils import (
    send_appointment_request_notification, 
    send_appointment_request_acknowledgement,
    send_appointment_confirmation_to_customer,
    send_order_confirmation_to_customer,
    send_order_cancellation_email,
    send_appointment_cancellation_email,
    send_appointment_cancellation_notification_to_admin,
    send_appointment_cancellation_confirmation,
    
)

logger = logging.getLogger(__name__)

# Utility functions for views
def process_payment_method(request):
    """Handle payment method processing consistently"""
    payment_method = request.POST.get('payment_method', 'cash')
    payment_status = 'paid' if payment_method == 'momo' else 'pending'
    return payment_method, payment_status

def validate_appointment_time(appointment_date):
    """Validate appointment time constraints"""
    if appointment_date < timezone.now():
        raise ValueError("You cannot book an appointment in the past.")
    if not (8 <= appointment_date.hour < 22):
        raise ValueError("Appointments can only be booked between 8:00 AM and 10:00 PM.")

def calculate_duration(subservice=None, estimated_duration=None):
    """Calculate duration consistently"""
    if subservice and subservice.duration:
        return subservice.duration
    elif estimated_duration:
        return estimated_duration
    return timedelta(minutes=60)

def check_time_conflicts(service, start_time, duration, exclude_appointment=None):
    """Check for time conflicts - reusable function"""
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

def extract_appointment_data(request):
    """Extract and validate appointment form data"""
    return {
        'customer_name': request.POST.get('customer_name'),
        'customer_phone': request.POST.get('customer_phone'),
        'customer_email': request.POST.get('customer_email'),
        'appointment_date': parse_datetime(request.POST.get('appointment_date')),
        'notes': request.POST.get('notes', ''),
        'subservice_id': request.POST.get('subservice'),
    }

def create_appointment_instance(service, form_data, user, payment_method, payment_status):
    """Create appointment instance with consistent logic"""
    subservice = None
    if form_data['subservice_id']:
        try:
            subservice = SubService.objects.get(
                id=form_data['subservice_id'], 
                service=service, 
                is_active=True
            )
        except SubService.DoesNotExist:
            pass
    
    return Appointment(
        user=user,
        customer_name=form_data['customer_name'],
        customer_phone=form_data['customer_phone'],
        customer_email=form_data['customer_email'],
        service=service,
        subservice=subservice,
        appointment_date=form_data['appointment_date'],
        notes=form_data['notes'],
        status='pending',
        payment_method=payment_method,
        payment_status=payment_status
    )

# Authentication Views
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('salon:index')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegisterForm()
    
    return render(request, 'register.html', {'form': form})

# Main Pages
def index(request):
    services = Service.objects.filter(is_active=True)
    booking_services = services.filter(service_type='booking')
    order_services = services.filter(service_type='order')
    
    return render(request, 'index.html', {
        'booking_services': booking_services,
        'order_services': order_services,
    })

def service_detail(request, service_id):
    service = get_object_or_404(Service, id=service_id, is_active=True)
    subservices = service.subservices.filter(is_active=True)

    if service.service_type == 'order':
        return render(request, 'order_service.html', {
            'service': service,
            'subservices': subservices
        })
    elif service.service_type == 'booking':
        hairstyles = service.hairstyles.filter(is_active=True)
        
        if hairstyles.exists():
            return render(request, 'hairstyles.html', {
                'service': service,
                'hairstyles': hairstyles,
                'subservices': subservices
            })
        elif service.name.lower() == 'wigs':
            wigs = Wig.objects.filter(is_active=True)
            return render(request, 'wigs.html', {
                'service': service,
                'wigs': wigs,
                'subservices': subservices
            })
    
    return render(request, 'service_detail.html', {
        'service': service,
        'subservices': subservices
    })

def service_list(request):
    services = Service.objects.filter(is_active=True)
    booking_services = services.filter(service_type='booking')
    product_services = services.filter(service_type='order')
    
    return render(request, 'service_list.html', {
        'booking_services': booking_services,
        'product_services': product_services,
        'all_services': services,
    })

# Appointment Views
@login_required
def book_appointment(request, service_id):
    service = get_object_or_404(Service, id=service_id, is_active=True)
    

    if request.method == 'POST':
        try:
            form_data = extract_appointment_data(request)
            if not form_data['appointment_date']:
                messages.error(request, "Invalid date and time.")
                return redirect('salon:book_appointment', service_id=service.id)
            
            form_data['appointment_date'] = timezone.make_aware(
                form_data['appointment_date'], timezone.get_current_timezone()
            )
            
            validate_appointment_time(form_data['appointment_date'])
            
            payment_method, payment_status = process_payment_method(request)
            
            subservice = None
            duration = calculate_duration()
            if form_data['subservice_id']:
                subservice = SubService.objects.get(
                    id=form_data['subservice_id'], service=service, is_active=True
                )
                duration = calculate_duration(subservice)

            # --- Atomic transaction to avoid race conditions ---
            with transaction.atomic():
                conflict_result = check_time_conflicts(
                    service, form_data['appointment_date'], duration
                )
                
                if conflict_result['conflict']:
                    available_slots = Appointment.objects.get_available_slots(
                        service, form_data['appointment_date'].date(), subservice
                    )
                    formatted_slots = [slot.strftime("%Y-%m-%d %H:%M") for slot in available_slots[:5]]
                    
                    msg = "Sorry, this slot conflicts with an existing booking. "
                    msg += "Here are some available times: " + ", ".join(formatted_slots) if formatted_slots else "No alternative slots available today."
                    messages.error(request, msg)
                    return redirect('salon:book_appointment', service_id=service.id)
                
                # Create the appointment safely
                appointment = create_appointment_instance(
                    service, form_data, request.user, payment_method, payment_status
                )
                appointment.save()

            # Send notifications outside the transaction
            send_appointment_request_notification(appointment)
            send_appointment_request_acknowledgement(appointment)
            messages.success(request, 'Your appointment has been requested. We will confirm shortly.')
            return redirect('salon:index')

        except (ValueError, SubService.DoesNotExist) as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f"Error booking appointment: {str(e)}")
            messages.error(request, "An error occurred. Please try again.")
    
    subservices = service.subservices.filter(is_active=True)
    return render(request, 'appointment.html', {
        'service': service,
        'subservices': subservices,
    })

def check_availability(request, service_id):
    service = get_object_or_404(Service, pk=service_id)
    today = date.today()
    available_slots = {}
    
    for sub in service.subservices.filter(is_active=True):
        slots = Appointment.objects.get_available_slots(service, today, sub)
        available_slots[sub.name] = [slot.strftime("%Y-%m-%d %H:%M") for slot in slots]
    
    return JsonResponse({"available_slots": available_slots})

@login_required
def appointment_list(request):
    if request.user.is_staff:
        appointments = Appointment.objects.all()
    else:
        appointments = Appointment.objects.filter(user=request.user)
    
    appointments = appointments.order_by('-appointment_date')
    return render(request, 'appointment_list.html', {'appointments': appointments})

@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointments = Appointment.objects.filter(user=request.user).order_by('-appointment_date')
    return render(request, 'salon/my_appointments.html', {'appointments': appointments})
    
    if not request.user.is_staff and appointment.user != request.user:
        messages.error(request, 'You can only view your own appointments.')
        return redirect('salon:appointment_list')
    
    return render(request, 'appointment_detail.html', {'appointment': appointment})

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from .models import Appointment
from .utils import send_appointment_confirmation_to_customer, send_order_confirmation_to_customer, send_payment_confirmation_to_customer


@require_POST
def confirm_appointment(request, appointment_id):
    """Confirm only the appointment (not payment)."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = 'confirmed'

    # Attach user if matched by email
    if not appointment.user:
        try:
            User = get_user_model()
            user = User.objects.get(email=appointment.customer_email)
            appointment.user = user
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            pass

    appointment.save()
    send_appointment_confirmation_to_customer(appointment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Appointment confirmed'})

    return redirect('salon:admin_dashboard')


# In your views.py - WRONG (causing the error)

@require_POST
def confirm_appointment_payment(request, appointment_id):
    """Confirm payment for an appointment"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.payment_status = 'paid'
    appointment.save()
    
    send_payment_confirmation_to_customer(appointment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Appointment payment confirmed'})

    return redirect('salon:admin_dashboard')

@require_POST
def confirm_product_payment(request, order_type, order_id):
    """Confirm payment for product orders"""
    try:
        if order_type == 'wig':
            order = get_object_or_404(WigOrder, id=order_id)
        else:
            order = get_object_or_404(ProductOrder, id=order_id)
        
        order.payment_status = 'paid'
        order.payment_confirmed = True
        order.save()

        send_order_confirmation_to_customer(order, order_type)

        return JsonResponse({'success': True, 'message': f'{order_type} order payment confirmed'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def cancel_appointment_common(request, appointment_id, is_admin_cancellation=False):
    """Common cancellation logic for both admin and client"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Cancellation reason is required'})
            messages.error(request, 'Please provide a cancellation reason.')
            template = 'cancel_appointment.html' if is_admin_cancellation else 'cancel_appointment_client.html'
            return render(request, template, {'appointment': appointment})
        
        appointment.status = 'cancelled'
        appointment.cancellation_reason = reason
        appointment.cancelled_by = 'admin' if is_admin_cancellation else 'client'
        appointment.cancelled_at = timezone.now()
        appointment.save()
        
        if is_admin_cancellation:
            send_appointment_cancellation_email(appointment, reason)
        else:
            send_appointment_cancellation_notification_to_admin(appointment, reason)
            send_appointment_cancellation_confirmation(appointment, reason)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Appointment cancelled'})
        
        messages.success(request, 'Appointment cancelled successfully.')
        return redirect('salon:admin_dashboard' if is_admin_cancellation else 'salon:appointment_list')
    
    template = 'cancel_appointment.html' if is_admin_cancellation else 'cancel_appointment_client.html'
    return render(request, template, {'appointment': appointment})

@login_required
def cancel_appointment(request, appointment_id):
    """
    Original cancel_appointment function for admin cancellation
    This is kept for URL compatibility
    """
    return cancel_appointment_common(request, appointment_id, is_admin_cancellation=True)

@require_POST
def cancel_appointment_admin(request, appointment_id):
    return cancel_appointment_common(request, appointment_id, is_admin_cancellation=True)

@login_required
def cancel_appointment_client(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if not request.user.is_staff and appointment.customer_email != request.user.email:
        messages.error(request, 'You can only cancel your own appointments.')
        return redirect('salon:appointment_list')
    
    return cancel_appointment_common(request, appointment_id, is_admin_cancellation=False)

@login_required
def order_product(request, service_id, subservice_id):
    try:
        service = get_object_or_404(Service, id=service_id, is_active=True)
        subservice = get_object_or_404(SubService, id=subservice_id, service=service, is_active=True)
        
        if service.service_type != 'order':
            messages.error(request, "This service does not support product ordering.")
            return redirect('salon:service_detail', service_id=service_id)
        
        if not subservice.in_stock:
            messages.error(request, f"Sorry, {subservice.name} is out of stock.")
            return redirect('salon:service_detail', service_id=service_id)
        
        if request.method == 'POST':
            quantity = int(request.POST.get('quantity', 1))
            
            if quantity <= 0:
                messages.error(request, "Please enter a valid quantity.")
            elif quantity > subservice.stock:
                messages.error(request, f"Sorry, only {subservice.stock} units available in stock.")
            else:
                total_price = quantity * subservice.price
                payment_method, payment_status = process_payment_method(request)
                
                order = ProductOrder.objects.create(
                    user=request.user,  # <-- link to logged-in user
                    subservice=subservice,
                    customer_name=request.POST.get('customer_name'),
                    customer_email=request.POST.get('customer_email'),
                    customer_phone=request.POST.get('customer_phone'),
                    customer_address=request.POST.get('customer_address'),
                    quantity=quantity,
                    total_price=total_price,
                    notes=request.POST.get('notes', ''),
                    payment_method=payment_method,
                    payment_status=payment_status
                )
                
                subservice.stock -= quantity
                subservice.save()
                
                messages.success(request, f'Order placed for {quantity} x {subservice.name}. Total: ${total_price:.2f}')
                return redirect('salon:index')
        
        return render(request, 'order_product.html', {
            'service': service,
            'subservice': subservice
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in order_product: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect('salon:index')

@login_required
def order_wig(request, wig_id):
    wig = get_object_or_404(Wig, id=wig_id, is_active=True)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity <= 0:
            messages.error(request, 'Please enter a valid quantity.')
        elif quantity > wig.stock:
            messages.error(request, f'Sorry, only {wig.stock} units available in stock.')
        else:
            payment_method, payment_status = process_payment_method(request)
            
            order = WigOrder(
                user=request.user,  # <-- link to logged-in user
                wig=wig,
                customer_name=request.POST.get('customer_name'),
                customer_phone=request.POST.get('customer_phone'),
                customer_email=request.POST.get('customer_email'),
                customer_address=request.POST.get('customer_address'),
                quantity=quantity,
                total_price=wig.price * quantity,
                status='pending',
                payment_method=payment_method,
                payment_status=payment_status
            )
            order.save()
            
            messages.success(request, 'Your order has been placed. You will receive payment instructions shortly.')
            return redirect('salon:index')
    
    return render(request, 'order_wig.html', {'wig': wig})

def view_order(request, order_id):
    order = get_object_or_404(ProductOrder, id=order_id)
    return render(request, 'view_order.html', {'order': order})

def view_wig_order(request, order_id):
    order = get_object_or_404(WigOrder, id=order_id)
    return render(request, 'view_wig_order.html', {'order': order})

def order_action_common(request, order_id, order_type, action):
    """Common logic for order actions (confirm/cancel)"""
    if order_type == 'product':
        order = get_object_or_404(ProductOrder, id=order_id)
    elif order_type == 'wig':
        order = get_object_or_404(WigOrder, id=order_id)
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Invalid order type'}, status=400)
        messages.error(request, 'Invalid order type.')
        return redirect('salon:admin_dashboard')
    
    if action == 'confirm':
        order.payment_confirmed = True
        order.status = 'confirmed'
        order.save()
        send_order_confirmation_to_customer(order, order_type)
        message = f'{order_type.title()} order confirmed'
    elif action == 'cancel':
        order.status = 'cancelled'
        order.save()
        send_order_cancellation_email(order, order_type)
        message = f'{order_type.title()} order cancelled'
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Invalid action'}, status=400)
        messages.error(request, 'Invalid action.')
        return redirect('salon:admin_dashboard')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': message})
    
    messages.success(request, message)
    return redirect('salon:admin_dashboard')

@require_POST
def confirm_product_order(request, order_id):
    return order_action_common(request, order_id, 'product', 'confirm')

@require_POST
def confirm_wig_order(request, order_id):
    return order_action_common(request, order_id, 'wig', 'confirm')

@require_POST
def cancel_product_order(request, order_id):
    return order_action_common(request, order_id, 'product', 'cancel')

@require_POST
def cancel_wig_order(request, order_id):
    return order_action_common(request, order_id, 'wig', 'cancel')

def confirm_payment(request, order_type, order_id):
    if request.method == "POST":
        return order_action_common(request, order_id, order_type, 'confirm')
    return JsonResponse({'error': 'Invalid request'}, status=400)

from django.db.models import Case, When, IntegerField
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def admin_dashboard(request):
    services = Service.objects.filter(is_active=True)
    service_data = []

    for service in services:
        if service.service_type == "booking":
            # Custom ordering: pending -> confirmed -> completed -> cancelled
            items = Appointment.objects.filter(service=service).order_by(
                Case(
                    When(status='pending', then=0),
                    When(status='confirmed', then=1),
                    When(status='completed', then=2),
                    When(status='cancelled', then=3),
                    output_field=IntegerField(),
                ),
                '-appointment_date'  # newest first
            )

        elif service.service_type == "order":
            # For Wig orders
            wigs_items = WigOrder.objects.filter(wig__service=service).order_by(
                Case(
                    When(status='pending', then=0),
                    When(status='confirmed', then=1),
                    When(status='shipped', then=2),
                    When(status='delivered', then=3),
                    When(status='cancelled', then=4),
                    output_field=IntegerField(),
                ),
                '-order_date'  # newest first
            )

            # For Product orders
            products_items = ProductOrder.objects.filter(subservice__service=service).order_by(
                Case(
                    When(payment_status='pending', then=0),
                    When(payment_status='paid', then=1),
                    output_field=IntegerField(),
                ),
                '-order_date'  # newest first
            )

            # Combine both types of orders
            items = list(wigs_items) + list(products_items)

        else:
            items = []

        service_data.append({
            "service": service,
            "items": items
        })

    context = {
        "user": request.user,
        "service_data": service_data,
    }

    return render(request, "admin_dashboard.html", context)


def delete_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == "POST":
        service.delete()
        messages.success(request, f"Service '{service.name}' deleted successfully.")
        return redirect('salon:admin_dashboard')
    return redirect('salon:admin_dashboard')

# Email function (kept for backward compatibility)
def send_appointment_confirmation(appointment):
    subject = f'Appointment Confirmation - {appointment.service.name}'
    message = f'''
    Hi {appointment.customer_name},
    
    Your appointment for {appointment.service.name} has been confirmed.
    Date: {appointment.appointment_date}
    
    Thank you for choosing Awinso Hair Care!
    '''
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [appointment.customer_email])

@login_required
def my_orders(request):
    product_orders = ProductOrder.objects.filter(user=request.user)
    wig_orders = WigOrder.objects.filter(user=request.user)

    orders = sorted(
        list(product_orders) + list(wig_orders),
        key=lambda o: o.created_at,
        reverse=True
    )

    return render(request, 'my_orders.html', {'orders': orders})

from django.contrib.auth.views import PasswordResetView
from .forms import CustomPasswordResetForm
from django.urls import reverse_lazy

class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'registration/password_reset.html'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('salon:password_reset_done')