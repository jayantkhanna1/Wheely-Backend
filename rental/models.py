from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
import uuid

class Location(models.Model):
    """Location model for storing address information"""
    address = models.TextField()
    street = models.CharField(max_length=200, blank=True)
    colony = models.CharField(max_length=200, blank=True)
    road = models.CharField(max_length=200, blank=True)
    pincode = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='India')
    google_map_location = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.city}, {self.state}"

    class Meta:
        ordering = ['-created_at']

class User(models.Model):
    """Abstract base class for user"""
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    password = models.CharField(max_length=255)
    otp = models.CharField(max_length=6, blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    private_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    driving_license = models.FileField(upload_to='licenses/users/', blank=True, null=True)
    driving_license_verified = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profiles/users/', blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    default_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='default_location')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
        

class Vehicle(models.Model):
    """Vehicle model for rental vehicles"""
    VEHICLE_TYPES = [
        ('4_wheeler', '4_wheeler'),
        ('2_wheeler', '2_wheeler'),
        ('Bicycle', 'Bicycle'),
        ('Other', 'Other'),
    ]
    
    TRANSMISSION_TYPES = [
        ('manual', 'manual'),
        ('automatic', 'automatic'),
        ('cvt', 'cvt'),
    ]
    
    FUEL_TYPES = [
        ('petrol', 'petrol'),
        ('diesel', 'diesel'),
        ('electric', 'electric'),
        ('hybrid', 'hybrid'),
        ('cng', 'cng'),
        ('none', 'none'),  # For bicycles
    ]

    CATEGORY_CHOICES = [
        ('SUV', 'SUV'),
        ('Sedan', 'Sedan'),
        ('Hatchback', 'Hatchback'),
        ('MUV', 'MUV'),
        ('Luxury', 'Luxury'),
        ('Sports', 'Sports'),
        ('Other', 'Other'),
        ('Bicycle', 'Bicycle'),
    ]

    vehicle_name = models.CharField(max_length=200)
    vehicle_brand = models.CharField(max_length=100)
    vehicle_model = models.CharField(max_length=100)
    vehicle_color = models.CharField(max_length=50)
    vehicle_year = models.PositiveIntegerField()
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    transmission_type = models.CharField(max_length=20, choices=TRANSMISSION_TYPES, blank=True)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPES, default='petrol')
    seating_capacity = models.PositiveIntegerField(default=4)
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    license_plate = models.CharField(max_length=20, help_text="Vehicle license plate number", null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='sedan') 
    features = models.JSONField(default=list, blank=True, help_text="Additional features of the vehicle")  
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles')
    
    # Documents - not required for bicycles
    vehicle_rc = models.FileField(upload_to='documents/rc/', blank=True, null=True)
    vehicle_insurance = models.FileField(upload_to='documents/insurance/', blank=True, null=True)
    vehicle_pollution_certificate = models.FileField(upload_to='documents/pollution/', blank=True, null=True)
    
    # Status and availability
    is_available = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    # Ratings and bookings
    rating = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    total_bookings = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vehicle_brand} {self.vehicle_model} - {self.vehicle_name}"

    class Meta:
        ordering = ['-created_at']

class VehiclePhoto(models.Model):
    """Model for storing multiple photos of a vehicle"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='vehicles/photos/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.vehicle.vehicle_name}"

    class Meta:
        ordering = ['is_primary', '-created_at']

class VehicleAvailability(models.Model):
    """Model for tracking vehicle availability"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='availability_slots')
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vehicle.vehicle_name} - {self.start_date} to {self.end_date}"

    class Meta:
        ordering = ['start_date']

class Review(models.Model):
    """Review model for user feedback"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_verified_booking = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} - {self.vehicle.vehicle_name} - {self.rating} stars"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['vehicle', 'user']  # One review per user per vehicle

class Ride(models.Model):
    """Model for tracking rides"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='rides')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rides')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status  = models.CharField(max_length=20, choices=[
        ('booked', 'Booked'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='booked')

    def __str__(self):
        return f"Ride by {self.user.first_name} in {self.vehicle.vehicle_name} from {self.start_location.city} to {self.end_location.city}"
    
    class Meta:
        ordering = ['-created_at']       