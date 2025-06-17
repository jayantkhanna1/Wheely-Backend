from django.contrib import admin
from .models import Location, User, Vehicle, VehiclePhoto, VehicleAvailability, Review

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('city', 'state', 'country', 'pincode', 'created_at')
    list_filter = ('state', 'country', 'created_at')
    search_fields = ('city', 'state', 'pincode', 'address')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'email', 'phone', 'email_verified', 'phone_verified', 'is_active', 'created_at')
    list_filter = ('email_verified', 'phone_verified', 'driving_license_verified', 'is_active', 'created_at')
    search_fields = ('id', 'first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('id', 'private_token', 'created_at', 'updated_at')
    fieldsets = (
        ('System Information', {
            'fields': ('id', 'private_token', 'is_active', 'created_at', 'updated_at')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'location')
        }),
        ('Verification', {
            'fields': ('email_verified', 'phone_verified', 'otp')
        }),
        ('Documents', {
            'fields': ('driving_license', 'driving_license_verified', 'profile_picture')
        }),
    )
    
    # Optional: Make the list more user-friendly
    list_display_links = ('id', 'first_name', 'last_name')
    list_per_page = 25
    
    # Optional: Add ordering
    ordering = ('-created_at',)

    
class VehiclePhotoInline(admin.TabularInline):
    model = VehiclePhoto
    extra = 1

class VehicleAvailabilityInline(admin.TabularInline):
    model = VehicleAvailability
    extra = 1

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_name', 'vehicle_brand', 'vehicle_model', 'vehicle_type', 'owner', 'price_per_hour', 'is_available', 'is_verified', 'rating')
    list_filter = ('vehicle_type', 'fuel_type', 'transmission_type', 'is_available', 'is_verified', 'created_at')
    search_fields = ('vehicle_name', 'vehicle_brand', 'vehicle_model', 'owner__first_name', 'owner__last_name')
    readonly_fields = ('rating', 'total_bookings', 'created_at', 'updated_at')
    inlines = [VehiclePhotoInline, VehicleAvailabilityInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('vehicle_name', 'vehicle_brand', 'vehicle_model', 'vehicle_color', 'vehicle_year', 'vehicle_type')
        }),
        ('Specifications', {
            'fields': ('transmission_type', 'fuel_type', 'seating_capacity', 'mileage')
        }),
        ('Pricing & Location', {
            'fields': ('price_per_hour', 'price_per_day', 'location', 'owner')
        }),
        ('Documents', {
            'fields': ('vehicle_rc', 'vehicle_insurance', 'vehicle_pollution_certificate')
        }),
        ('Status', {
            'fields': ('is_available', 'is_verified')
        }),
        ('Stats', {
            'fields': ('rating', 'total_bookings', 'created_at', 'updated_at')
        }),
    )

@admin.register(VehiclePhoto)
class VehiclePhotoAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('vehicle__vehicle_name', 'vehicle__vehicle_brand')

@admin.register(VehicleAvailability)
class VehicleAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'start_date', 'end_date', 'start_time', 'end_time', 'is_available')
    list_filter = ('is_available', 'start_date', 'created_at')
    search_fields = ('vehicle__vehicle_name', 'vehicle__vehicle_brand')
    date_hierarchy = 'start_date'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle', 'rating', 'is_verified_booking', 'created_at')
    list_filter = ('rating', 'is_verified_booking', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'vehicle__vehicle_name')
    readonly_fields = ('created_at', 'updated_at')