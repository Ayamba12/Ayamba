from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Service, HairStyle, Wig, Appointment, WigOrder
from .models import Appointment
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.core.mail import send_mail
from django.conf import settings
from .utils import send_appointment_request_notification, send_appointment_request_acknowledgement
from .utils import send_appointment_confirmation_to_customer
# salon/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.decorators import method_decorator
from .models import  Service, HairStyle, Wig, Appointment, WigOrder, SubService,ProductOrder
from datetime import date
from django.http import JsonResponse
from .models import Service, Appointment
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required





# Add this function to your views
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in after registration
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('salon:index')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    return render(request, 'register.html', {'form': form})

# salon/views.py
def index(request):
    # Get all active services
    services = Service.objects.filter(is_active=True)
    
    # Separate services by type
    booking_services = services.filter(service_type='booking')
    order_services = services.filter(service_type='order')
    
    print(f"Booking services: {booking_services.count()}")
    print(f"Order services: {order_services.count()}")
    
    return render(request, 'index.html', {
        'booking_services': booking_services,
        'order_services': order_services,
    })

# salon/views.py
def service_detail(request, service_id):
    from .models import SubService
    
    service = get_object_or_404(Service, id=service_id, is_active=True)
    
    # Get all active subservices for this service
    subservices = service.subservices.filter(is_active=True)

    # DEBUG: Print service type
    print(f"DEBUG: Service '{service.name}' - Type: {service.service_type}")

    # Check service type FIRST - this is the most important logic
    if service.service_type == 'order':
        print("DEBUG: Rendering order_service.html (Order type service)")
        return render(request, 'order_service.html', {
            'service': service,
            'subservices': subservices
        })

    # For booking-type services, check if they have special handling
    elif service.service_type == 'booking':
        # Fetch hairstyles related to this service
        hairstyles = service.hairstyles.filter(is_active=True)
        
        if hairstyles.exists():
            print("DEBUG: Rendering hairstyles.html (Booking type with hairstyles)")
            return render(request, 'hairstyles.html', {
                'service': service,
                'hairstyles': hairstyles,
                'subservices': subservices
            })
        elif service.name.lower() == 'wigs':
            wigs = Wig.objects.filter(is_active=True)
            print("DEBUG: Rendering wigs.html (Booking type - wigs)")
            return render(request, 'wigs.html', {
                'service': service,
                'wigs': wigs,
                'subservices': subservices
            })
        else:
            print("DEBUG: Rendering service_detail.html (Regular booking service)")
            return render(request, 'service_detail.html', {
                'service': service,
                'subservices': subservices
            })

    # Default fallback (shouldn't happen if all services have a type)
    print("DEBUG: Rendering service_detail.html (Fallback)")
    return render(request, 'service_detail.html', {
        'service': service,
        'subservices': subservices
    })

from django.utils.dateparse import parse_datetime
from django.utils import timezone

import logging
logger = logging.getLogger(__name__)
@login_required
def book_appointment(request, service_id):
    service = get_object_or_404(Service, id=service_id, is_active=True)

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        customer_email = request.POST.get('customer_email')
        appointment_date = parse_datetime(request.POST.get('appointment_date'))
        notes = request.POST.get('notes')

        if not appointment_date:
            messages.error(request, "Invalid date and time.")
            return redirect('salon:book_appointment', service_id=service.id)

        appointment_date = timezone.make_aware(appointment_date, timezone.get_current_timezone())

        # not past
        if appointment_date < timezone.now():
            messages.error(request, "You cannot book an appointment in the past.")
            return redirect('salon:book_appointment', service.id)

        # working hours
        if not (8 <= appointment_date.hour < 20):
            messages.error(request, "Appointments can only be booked between 8:00 AM and 8:00 PM.")
            return redirect('salon:book_appointment', service.id)

        # 🔹 Get subservice + duration
        subservice_id = request.POST.get('subservice')
        subservice = None
        duration = timedelta(minutes=30)

        if subservice_id:
            try:
                subservice = SubService.objects.get(id=subservice_id, service=service, is_active=True)
                duration = subservice.duration or duration
            except SubService.DoesNotExist:
                pass

        start = appointment_date
        end = start + duration
        end_with_buffer = end + timedelta(minutes=10)

        # 🔹 Overlap check
        existing = Appointment.objects.filter(
            service=service,
            status__in=["pending", "confirmed"]
        )

        conflict = False
        for other in existing:
            other_start = other.appointment_date

            # check other duration
            other_duration = timedelta(minutes=30)
            if other.subservice and other.subservice.duration:
                other_duration = other.subservice.duration
            elif other.estimated_duration:
                other_duration = other.estimated_duration

            other_end = other_start + other_duration
            other_end_with_buffer = other_end + timedelta(minutes=10)

            if start < other_end_with_buffer and other_start < end_with_buffer:
                conflict = True
                conflict_start = other_start.strftime("%Y-%m-%d %H:%M")
                conflict_end = other_end_with_buffer.strftime("%H:%M")
                break

        if conflict:
            # 🔹 Suggest alternative slots for THIS subservice
            available_slots = Appointment.objects.get_available_slots(service, appointment_date.date(), subservice)

            formatted_slots = [slot.strftime("%Y-%m-%d %H:%M") for slot in available_slots[:5]]

            msg = f"Sorry, this slot conflicts with an existing booking ({conflict_start} - {conflict_end}). "
            if formatted_slots:
                msg += "Here are some available times you can choose: " + ", ".join(formatted_slots)
            else:
                msg += "No alternative slots are available today."

            messages.error(request, msg)
            return redirect('salon:book_appointment', service_id=service.id)
        
        payment_method = request.POST.get('payment_method') or 'cash'  # fallback to cash
        payment_status = 'pending'

        if payment_method == 'momo':
            # here you can integrate real payment API later
            payment_status = 'paid'

        # 🔹 If free → save appointment
        appointment = Appointment.objects.create(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            service=service,
            subservice=subservice,
            appointment_date=start,
            notes=notes,
            status='pending',
            payment_method=payment_method,
            payment_status=payment_status
        )

        send_appointment_request_notification(appointment)
        send_appointment_request_acknowledgement(appointment)
        messages.success(request, 'Your appointment has been requested. We will confirm shortly.')
        return redirect('salon:index')

    subservices = service.subservices.filter(is_active=True)
    return render(request, 'appointment.html', {
        'service': service,
        'subservices': subservices,
    })


# ✅ Availability checker
def check_availability(request, service_id):
    service = get_object_or_404(Service, pk=service_id)
    today = date.today()

    # return slots for each subservice
    available_slots = {}
    for sub in service.subservices.filter(is_active=True):
        slots = Appointment.objects.get_available_slots(service, today, sub)
        available_slots[sub.name] = [slot.strftime("%Y-%m-%d %H:%M") for slot in slots]

    return JsonResponse({"available_slots": available_slots})

def confirm_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = "confirmed"
    appointment.save()
    
    # Send confirmation email to customer ONLY when admin confirms
    send_appointment_confirmation_to_customer(appointment)
    
    messages.success(request, f"Appointment confirmed for {appointment.customer_name}")
    return redirect('salon:admin_dashboard')

def send_appointment_confirmation(appointment):
    subject = f'Appointment Confirmation - {appointment.service.name}'
    message = f'''
    Hi {appointment.customer_name},
    
    Your appointment for {appointment.service.name} has been confirmed.
    Date: {appointment.appointment_date}
    
    Thank you for choosing Awinso Hair Care!
    '''
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [appointment.customer_email])

def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = "cancelled"
    appointment.save()
    messages.warning(request, f"Appointment cancelled for {appointment.customer_name}")
    return redirect('salon:admin_dashboard')

def delete_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == "POST":
        service.delete()
        messages.success(request, f"Service '{service.name}' deleted successfully.")
        return redirect('salon:admin_dashboard')
    return redirect('salon:admin_dashboard')

# salon/views.py
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
            try:
                quantity = int(request.POST.get('quantity', 1))
                
                if quantity <= 0:
                    messages.error(request, "Please enter a valid quantity.")
                    return render(request, 'order_product.html', {
                        'service': service,
                        'subservice': subservice
                    })
                
                if quantity > subservice.stock:
                    messages.error(request, f"Sorry, only {subservice.stock} units available in stock.")
                    return render(request, 'order_product.html', {
                        'service': service,
                        'subservice': subservice
                    })
                
                total_price = quantity * subservice.price

                # Create the order
                from .models import ProductOrder
                order = ProductOrder.objects.create(
                    subservice=subservice,
                    customer_name=request.POST.get('customer_name'),
                    customer_email=request.POST.get('customer_email'),
                    customer_phone=request.POST.get('customer_phone'),
                    customer_address=request.POST.get('customer_address'),
                    quantity=quantity,
                    total_price=total_price,
                    notes=request.POST.get('notes', ''),
                    payment_method=request.POST.get('payment_method', 'mobile_money')
                )

                # FIX: Reduce stock after successful order creation
                subservice.stock -= quantity
                subservice.save()
                
                messages.success(request, f'Order placed for {quantity} x {subservice.name}. Total: ${total_price:.2f}')
                return redirect('salon:index')
                
            except Exception as e:
                logger.error(f"Error processing product order: {str(e)}")
                messages.error(request, "Error processing your order. Please try again.")
                return render(request, 'order_product.html', {
                    'service': service,
                    'subservice': subservice
                })
        
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
        
        # Stock validation
        if quantity > wig.stock:
            messages.error(request, f'Sorry, only {wig.stock} units available in stock.')
            return render(request, 'order_wig.html', {'wig': wig})
        
        if quantity <= 0:
            messages.error(request, 'Please enter a valid quantity.')
            return render(request, 'order_wig.html', {'wig': wig})
    
    if request.method == 'POST':
        # Simplified form handling for now
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        customer_email = request.POST.get('customer_email')
        customer_address = request.POST.get('customer_address')
        quantity = int(request.POST.get('quantity', 1))
        
        # Create order
        order = WigOrder(
            wig=wig,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            customer_address=customer_address,
            quantity=quantity,
            total_price=wig.price * quantity,
            status='pending',
            payment_method='Mobile Money',
            payment_confirmed=False
        )
        
        order.save()
        messages.success(request, 'Your order has been placed. You will receive payment instructions shortly.')
        return redirect('salon:index')
    
    return render(request, 'order_wig.html', {
        'wig': wig
    })

    pass

def is_admin(user):
    return user.is_staff
@staff_member_required
def admin_dashboard(request):
    services = Service.objects.filter(is_active=True)
    service_data = []

    for service in services:
        if service.service_type == "booking":
            items = Appointment.objects.filter(service=service)
        elif service.service_type == "order":
            wigs_items = WigOrder.objects.filter(wig__service=service)
            products_items = ProductOrder.objects.filter(subservice__service=service)
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

    # Make sure to return an HttpResponse!
    return render(request, "admin_dashboard.html", context)


def view_order(request, order_id):
    # You can fetch a product order or wig order
    order = get_object_or_404(ProductOrder, id=order_id)
    return render(request, 'view_order.html', {'order': order})



# salon/views.py
@login_required
def appointment_list(request):
    # For now, show all appointments. Later you can filter by user
    appointments = Appointment.objects.all().order_by('-appointment_date')
    return render(request, 'appointment_list.html', {
        'appointments': appointments
    })
    pass

@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    return render(request, 'appointment_detail.html', {
        'appointment': appointment
    })

@login_required
def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if request.method == 'POST':
        appointment.status = 'cancelled'
        appointment.save()
        messages.success(request, 'Appointment cancelled successfully.')
        return redirect('salon:appointment_list')
    
    return render(request, 'cancel_appointment.html', {
        'appointment': appointment
    })

# salon/views.py
@login_required
def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    if request.method == 'POST':
        appointment.status = 'cancelled'
        # You could store the cancellation reason if you add a field for it
        reason = request.POST.get('reason', '')
        appointment.save()
        
        messages.success(request, 'Appointment cancelled successfully.')
        return redirect('salon:appointment_list')
    
    return render(request, 'cancel_appointment.html', {
        'appointment': appointment
    })

def confirm_payment(request, order_type, order_id):
    if request.method == "POST":
        if order_type == "product":
            order = get_object_or_404(ProductOrder, id=order_id)
        elif order_type == "wig":
            order = get_object_or_404(WigOrder, id=order_id)
        else:
            return JsonResponse({'error': 'Invalid order type'}, status=400)

        order.payment_confirmed = True
        order.payment_status = 'paid'
        order.save()

        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request'}, status=400)
