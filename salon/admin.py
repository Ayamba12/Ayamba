# salon/admin.py
from django.contrib import admin
from django.db.models import Min, Max
from django.utils.safestring import mark_safe 
from .models import Service, SubService, HairStyle, Wig, Appointment, WigOrder


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_price_range', 'get_duration_range', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']

    
    def get_price_range(self, obj):
        # Get price range from subservices
        prices = obj.subservices.filter(is_active=True).aggregate(
            min_price=Min('price'),
            max_price=Max('price')
        )
        if prices['min_price'] is not None and prices['max_price'] is not None:
            if prices['min_price'] == prices['max_price']:
                return f"${prices['min_price']}"
            return f"${prices['min_price']} - ${prices['max_price']}"
        return "No pricing"
    get_price_range.short_description = 'Price Range'
    
    def get_duration_range(self, obj):
        durations = obj.subservices.filter(is_active=True).aggregate(
            min_duration=Min('duration'),
            max_duration=Max('duration')
        )
        if durations['min_duration'] is not None and durations['max_duration'] is not None:
            if durations['min_duration'] == durations['max_duration']:
                return f"{durations['min_duration']}"
            return f"{durations['min_duration']} - {durations['max_duration']}"
        return "No duration"
    get_duration_range.short_description = 'Duration Range'

@admin.register(SubService)
class SubServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'service', 'price', 'get_duration', 'get_stock', 'is_active'] 
    list_filter = ['service', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['price', 'is_active'] 
    
    def get_duration(self, obj):
        return obj.duration if obj.duration else "—"
    get_duration.short_description = 'Duration'
    
    def get_stock(self, obj):
        if obj.stock is not None:
            return f"{obj.stock} in stock" if obj.stock > 0 else "Out of stock"
        return "—"
    get_stock.short_description = 'Stock'
    
    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" style="width: 50px; height: 50px; object-fit: cover;" />')
        return "No Image"
    image_preview.short_description = 'Image Preview'

@admin.register(HairStyle)
class HairStyleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(Wig)
class WigAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'stock', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'service', 'subservice', 'appointment_date', 'status', 'created_at')
    list_filter = ('status', 'service', 'appointment_date')
    search_fields = ('customer_name', 'customer_phone', 'customer_email')
    date_hierarchy = 'appointment_date'
    readonly_fields = ('created_at',)
    actions = ['confirm_selected', 'cancel_selected']
    
    def confirm_selected(self, request, queryset):
        queryset.update(status='confirmed')
    confirm_selected.short_description = "Confirm selected appointments"
    
    def cancel_selected(self, request, queryset):
        queryset.update(status='cancelled')
    cancel_selected.short_description = "Cancel selected appointments"

@admin.register(WigOrder)
class WigOrderAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'wig', 'quantity', 'total_price', 'status', 'payment_method', 'payment_confirmed')
    list_filter = ('status', 'payment_method', 'payment_confirmed', 'order_date')
    search_fields = ('customer_name', 'customer_phone', 'customer_email')
    readonly_fields = ('order_date', 'total_price')

