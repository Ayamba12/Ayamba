from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import datetime, timedelta


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


class HairStyle(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="hairstyles",
                                limit_choices_to={'service_type': 'booking'})
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

from datetime import datetime, timedelta

class AppointmentManager(models.Manager):
    def get_available_slots(self, service, date, subservice=None):
        start_of_day = datetime.combine(date, datetime.min.time()).replace(hour=8)
        end_of_day = datetime.combine(date, datetime.min.time()).replace(hour=20)

        duration = timedelta(minutes=30)
        if subservice and subservice.duration:
            duration = subservice.duration

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

            current += timedelta(minutes=15)  # stepping

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


    phone_validator = RegexValidator(
        regex=r'^\+?\d{9,15}$',
        message="Phone number must be entered in the format: '+233123456789'. Up to 15 digits allowed."
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

    objects = AppointmentManager()   # ✅ add here

    class Meta:
        ordering = ['-appointment_date']
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"

    def __str__(self):
        return f"{self.customer_name} - {self.service.name}"


    def clean(self):
        if self.appointment_date and self.appointment_date < timezone.now():
            raise ValidationError("Appointment date cannot be in the past")

        if self.appointment_date and self.service and self.status in ["pending", "confirmed"]:
            start = self.appointment_date

            # ✅ Determine duration
            if self.subservice and self.subservice.duration:
                duration = self.subservice.duration
            elif self.estimated_duration:
                duration = self.estimated_duration
            else:
                duration = timedelta(minutes=30)

            end = start + duration
            end_with_buffer = end + timedelta(minutes=10)

            # Get all existing confirmed/pending bookings for this service
            existing = Appointment.objects.filter(
                service=self.service,
                status__in=["pending", "confirmed"]
            ).exclude(pk=self.pk)

            for other in existing:
                other_start = other.appointment_date

                if other.subservice and other.subservice.duration:
                    other_duration = other.subservice.duration
                elif other.estimated_duration:
                    other_duration = other.estimated_duration
                else:
                    other_duration = timedelta(minutes=30)

                other_end = other_start + other_duration
                other_end_with_buffer = other_end + timedelta(minutes=10)

                # Overlap check
                if start < other_end_with_buffer and other_start < end_with_buffer:
                    raise ValidationError(
                        f"Sorry, {other_start.strftime('%Y-%m-%d %H:%M')} "
                        f"to {other_end_with_buffer.strftime('%H:%M')} is already booked. "
                        f"Please choose another time."
                    )



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

    class Meta:
        ordering = ['-order_date']
        verbose_name = "Wig Order"
        verbose_name_plural = "Wig Orders"

    def __str__(self):
        return f"{self.customer_name} - {self.wig.name}"

    def save(self, *args, **kwargs):
        # Automatically calculate total price
        self.total_price = self.wig.price * self.quantity
        super().save(*args, **kwargs)

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

    order_date = models.DateTimeField(auto_now_add=True)

    subservice = models.ForeignKey(SubService, on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f"{self.customer_name} - {self.product_name} ({self.quantity})"

