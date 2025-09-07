from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.conf import settings

class Service(models.Model):
    SERVICE_TYPES = [
        ('booking', 'Booking Service (Appointments)'),
        ('order', 'Order Service (Products)'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField()
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES, default='booking')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.name

    @property
    def is_booking_service(self):
        return self.service_type == 'booking'
    
    @property
    def is_order_service(self):
        return self.service_type == 'order'


class SubService(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='subservices')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='subservices/', null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    # For appointment services
    duration = models.DurationField(blank=True, null=True)

    # For product services
    stock = models.PositiveIntegerField(default=0, blank=True)

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Sub Service"
        verbose_name_plural = "Sub Services"

    def __str__(self):
        return f"{self.service.name} - {self.name}"

    @property
    def in_stock(self):
        """For product services - check if stock is available"""
        return self.stock > 0

    @property
    def has_duration(self):
        """For appointment services - check if duration is set"""
        return self.duration is not None

    def clean(self):
        """Validate that duration is set for booking services"""
        if self.service.is_booking_service and not self.duration:
            raise ValidationError("Duration is required for booking services")


class HairStyle(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="hairstyles", limit_choices_to={'service_type': 'booking'})                            
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='hairstyles/')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Hair Style"
        verbose_name_plural = "Hair Styles"

    def __str__(self):
        return self.name


class Wig(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        limit_choices_to={'service_type': 'order'},
        related_name="wigs"
    )
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='wigs/')
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Wig"
        verbose_name_plural = "Wigs"

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0

    def reduce_stock(self, quantity):
        """Reduce stock by given quantity"""
        if quantity > self.stock:
            raise ValidationError(f"Not enough stock. Only {self.stock} available.")
        self.stock -= quantity
        self.save()


class AppointmentManager(models.Manager):
    def get_available_slots(self, service, date, subservice=None):
        from .utils import calculate_duration  # Import here to avoid circular imports
        
        start_of_day = datetime.combine(date, datetime.min.time()).replace(hour=8)
        end_of_day = datetime.combine(date, datetime.min.time()).replace(hour=20)

        duration = calculate_duration(subservice)
        buffer_time = timedelta(minutes=10)

        slots = []
        current = start_of_day
        while current + duration <= end_of_day:
            slot_end = current + duration + buffer_time

            overlap = Appointment.objects.filter(
                service=service,
                status__in=["pending", "confirmed"],
                appointment_date__lt=slot_end,
            ).exclude(
                appointment_date__gte=current + duration
            ).exists()

            if not overlap:
                slots.append(current)

            current += timedelta(minutes=15)

        return slots


class Appointment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash on Delivery'),
        ('momo', 'Mobile Money'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    CANCELLED_BY_CHOICES = [
        ('client', 'Client'),
        ('admin', 'Admin'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='appointments'
    )

    phone_validator = RegexValidator(
        regex=r'^\+?\d{9,15}$',
        message="Phone number must be entered in the format: '0123456789'. Up to 15 digits allowed."
    )

    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15, validators=[phone_validator])
    customer_email = models.EmailField()
    service = models.ForeignKey(Service, on_delete=models.CASCADE, limit_choices_to={'service_type': 'booking'})
    subservice = models.ForeignKey(SubService, on_delete=models.SET_NULL, null=True, blank=True)
    hairstyle = models.ForeignKey(HairStyle, on_delete=models.SET_NULL, null=True, blank=True)
    custom_hairstyle = models.CharField(max_length=100, blank=True)
    appointment_date = models.DateTimeField()
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    estimated_duration = models.DurationField(null=True, blank=True)
    confirmed_time = models.DateTimeField(null=True, blank=True)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )

    cancelled_by = models.CharField(
        max_length=20, 
        choices=CANCELLED_BY_CHOICES,
        blank=True, 
        null=True
    )
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    objects = AppointmentManager()

    class Meta:
        ordering = ['-appointment_date']
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"

    def __str__(self):
        return f"{self.customer_name} - {self.service.name} - {self.appointment_date}"

 
    @property
    def price(self):
        if self.subservice:
            return self.subservice.price
        return None
    @property
    def is_upcoming(self):
        """Check if appointment is in the future"""
        return self.appointment_date > timezone.now()

    @property
    def is_cancellable(self):
        """Check if appointment can be cancelled"""
        return self.status in ['pending', 'confirmed'] and self.is_upcoming

    def get_duration(self):
        """Get the duration of the appointment"""
        from .utils import calculate_duration
        return calculate_duration(self.subservice, self.estimated_duration)

    def clean(self):
        """Validate appointment data"""
        from .utils import validate_appointment_time, check_time_conflict        
        if self.appointment_date:
            try:
                validate_appointment_time(self.appointment_date)
            except ValidationError as e:
                raise ValidationError({"appointment_date": str(e)})

        if (self.appointment_date and self.service and 
            self.service.is_booking_service and 
            self.status in ["pending", "confirmed"]):
            
            duration = self.get_duration()
            conflict_result = check_time_conflict(
                self.service, 
                self.appointment_date, 
                duration, 
                self if self.pk else None
            )
            
            if conflict_result['conflict']:
                conflict_start = conflict_result['conflict_start'].strftime('%Y-%m-%d %H:%M')
                conflict_end = conflict_result['conflict_end'].strftime('%H:%M')
                raise ValidationError(
                    f"Time slot conflict: {conflict_start} to {conflict_end} is already booked. "
                    f"Please choose another time."
                )

    def cancel(self, cancelled_by, reason=""):
        """Cancel appointment with reason"""
        self.status = 'cancelled'
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save()

    def confirm_appointment(self):
        """Confirm the booking/appointment"""
        self.status = 'confirmed'
        self.confirmed_time = timezone.now()
        self.save()

    def confirm_payment(self):
        """Confirm payment only"""
        self.payment_status = 'paid'
        self.save()

    def complete(self):
        """Mark appointment as completed"""
        self.status = 'completed'
        self.save()


class WigOrder(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash on Delivery'),
        ('momo', 'Mobile Money'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'), 
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    phone_validator = RegexValidator(
        regex=r'^\+?\d{9,15}$',
        message="Phone number must be entered in the format: '+233123456789'. Up to 15 digits allowed."
    )

    wig = models.ForeignKey(Wig, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15, validators=[phone_validator])
    customer_email = models.EmailField()
    customer_address = models.TextField()
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    payment_confirmed = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    order_date = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='wig_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-order_date']
        verbose_name = "Wig Order"
        verbose_name_plural = "Wig Orders"

    def __str__(self):
        return f"{self.customer_name} - {self.wig.name} - {self.quantity}"

    def save(self, *args, **kwargs):
        self.total_price = self.wig.price * self.quantity
        super().save(*args, **kwargs)

    @property
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'confirmed']

    def cancel(self):
        """Cancel the order"""
        if self.can_be_cancelled:
            self.status = 'cancelled'
            self.save()
        else:
            raise ValidationError("Order cannot be cancelled in its current status")

    def confirm(self):
        """Confirm the order"""
        self.status = 'confirmed'
        self.payment_confirmed = True
        self.save()


class ProductOrder(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash on Delivery'),
        ('momo', 'Mobile Money'),
    ]

    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True, null=True)
    customer_address = models.TextField(blank=True, null=True)

    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    notes = models.TextField(blank=True, null=True)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=[('pending', 'Pending'), ('paid', 'Paid')],
        default='pending'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='product_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)  # if not already present


    order_date = models.DateTimeField(auto_now_add=True)
    subservice = models.ForeignKey(SubService, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-order_date']
        verbose_name = "Product Order"
        verbose_name_plural = "Product Orders"

    def __str__(self):
        return f"{self.customer_name} - {self.product_name} ({self.quantity})"

    @property
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.payment_status == 'pending'

    def cancel(self):
        """Cancel the order and restore stock"""
        if self.can_be_cancelled:
            self.payment_status = 'cancelled'
            if self.subservice:
                self.subservice.stock += self.quantity
                self.subservice.save()
            self.save()
        else:
            raise ValidationError("Order cannot be cancelled after payment is confirmed")