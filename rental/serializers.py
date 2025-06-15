from rest_framework import serializers
from .models import Location, Customer, Host, Vehicle, VehiclePhoto, VehicleAvailability, Review

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Customer
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'location', 'location_id',
            'driving_license', 'driving_license_verified', 'profile_picture', 'date_of_birth',
            'email_verified', 'phone_verified', 'private_token', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['private_token', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True},
            'phone': {'required': False, 'allow_blank': True, 'allow_null': True},
            'driving_license': {'required': False, 'allow_blank': True, 'allow_null': True},
            'profile_picture': {'required': False, 'allow_null': True},
            'date_of_birth': {'required': False, 'allow_null': True},
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        customer = Customer(**validated_data)
        if password:
            customer.password = password  # Password is already hashed in the view
        customer.save()
        return customer

class HostSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Host
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'location', 'location_id',
            'profile_picture', 'business_license', 'business_license_verified', 'rating',
            'total_bookings', 'email_verified', 'phone_verified', 'private_token', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['private_token', 'rating', 'total_bookings', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        host = Host(**validated_data)
        if password:
            host.password = password  # In production, hash this password
        host.save()
        return host

class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ['id', 'photo', 'is_primary', 'created_at']

class VehicleAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleAvailability
        fields = '__all__'

class VehicleSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_id = serializers.IntegerField(write_only=True)
    owner = HostSerializer(read_only=True)
    owner_id = serializers.IntegerField(write_only=True)
    photos = VehiclePhotoSerializer(many=True, read_only=True)
    availability_slots = VehicleAvailabilitySerializer(many=True, read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_name', 'vehicle_brand', 'vehicle_model', 'vehicle_color',
            'vehicle_year', 'vehicle_type', 'transmission_type', 'fuel_type',
            'seating_capacity', 'price_per_hour', 'price_per_day', 'location', 'location_id',
            'owner', 'owner_id', 'vehicle_rc', 'vehicle_insurance', 'vehicle_pollution_certificate',
            'is_available', 'is_verified', 'mileage', 'rating', 'total_bookings',
            'photos', 'availability_slots', 'created_at', 'updated_at'
        ]
        read_only_fields = ['rating', 'total_bookings', 'created_at', 'updated_at']

class ReviewSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    vehicle_id = serializers.IntegerField(write_only=True)
    host = HostSerializer(read_only=True)
    host_id = serializers.IntegerField(write_only=True)
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'vehicle', 'vehicle_id', 'host', 'host_id', 'customer', 'customer_id',
            'rating', 'comment', 'is_verified_booking', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

# Simplified serializers for listing views
class CustomerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'email_verified', 'phone_verified']

class HostListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Host
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'rating', 'total_bookings']

class VehicleListSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    owner_name = serializers.CharField(source='owner.first_name', read_only=True)
    primary_photo = serializers.SerializerMethodField()
    
    def get_primary_photo(self, obj):
        primary_photo = obj.photos.filter(is_primary=True).first()
        if primary_photo:
            return self.context['request'].build_absolute_uri(primary_photo.photo.url)
        return None
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_name', 'vehicle_brand', 'vehicle_model', 'vehicle_type',
            'price_per_hour', 'price_per_day', 'location', 'owner_name', 'rating',
            'is_available', 'primary_photo', 'seating_capacity', 'fuel_type'
        ]