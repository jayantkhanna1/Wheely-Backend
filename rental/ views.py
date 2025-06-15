from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.hashers import make_password, check_password
import random
import string
from datetime import datetime, timedelta

from .models import (
    Location, Customer, Host, Vehicle, VehiclePhoto, 
    VehicleAvailability, Review
)
from .serializers import (
    LocationSerializer, CustomerSerializer, HostSerializer,
    VehicleSerializer, VehiclePhotoSerializer, VehicleAvailabilitySerializer,
    ReviewSerializer, CustomerListSerializer, HostListSerializer,
    VehicleListSerializer
)
from .tasks import generate_and_send_otp

class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for Location model"""
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'state', 'country', 'pincode']
    search_fields = ['city', 'state', 'address', 'pincode']
    ordering_fields = ['city', 'state', 'created_at']
    ordering = ['-created_at']

class CustomerViewSet(viewsets.ModelViewSet):
    """ViewSet for Customer model"""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['email_verified', 'phone_verified', 'driving_license_verified', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer

    @action(detail=True, methods=['post'])
    def verify_driving_license(self, request, pk=None):
        """Action to verify customer's driving license"""
        customer = self.get_object()
        customer.driving_license_verified = True
        customer.save()
        return Response({'message': 'Driving license verified successfully'})

    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        """Get customer's booking history"""
        customer = self.get_object()
        reviews = Review.objects.filter(customer=customer).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

class HostViewSet(viewsets.ModelViewSet):
    """ViewSet for Host model"""
    queryset = Host.objects.all()
    serializer_class = HostSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['email_verified', 'phone_verified', 'business_license_verified', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['first_name', 'last_name', 'rating', 'total_bookings', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return HostListSerializer
        return HostSerializer

    @action(detail=True, methods=['post'])
    def verify_business_license(self, request, pk=None):
        """Action to verify host's business license"""
        host = self.get_object()
        host.business_license_verified = True
        host.save()
        return Response({'message': 'Business license verified successfully'})

    @action(detail=True, methods=['get'])
    def vehicles(self, request, pk=None):
        """Get all vehicles owned by this host"""
        host = self.get_object()
        vehicles = Vehicle.objects.filter(owner=host)
        serializer = VehicleListSerializer(vehicles, many=True, context={'request': request})
        return Response(serializer.data)

class VehicleViewSet(viewsets.ModelViewSet):
    """ViewSet for Vehicle model"""
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'vehicle_type', 'fuel_type', 'transmission_type', 'is_available', 
        'is_verified', 'owner', 'location__city', 'location__state'
    ]
    search_fields = ['vehicle_name', 'vehicle_brand', 'vehicle_model', 'vehicle_color']
    ordering_fields = ['vehicle_name', 'price_per_hour', 'rating', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return VehicleListSerializer
        return VehicleSerializer

    @action(detail=True, methods=['post'])
    def verify_vehicle(self, request, pk=None):
        """Action to verify vehicle documents"""
        vehicle = self.get_object()
        vehicle.is_verified = True
        vehicle.save()
        return Response({'message': 'Vehicle verified successfully'})

    @action(detail=True, methods=['post'])
    def toggle_availability(self, request, pk=None):
        """Toggle vehicle availability"""
        vehicle = self.get_object()
        vehicle.is_available = not vehicle.is_available
        vehicle.save()
        status_text = 'available' if vehicle.is_available else 'unavailable'
        return Response({'message': f'Vehicle is now {status_text}'})

    @action(detail=True, methods=['get'])
    def availability_slots(self, request, pk=None):
        """Get vehicle availability slots"""
        vehicle = self.get_object()
        slots = VehicleAvailability.objects.filter(vehicle=vehicle, is_available=True)
        serializer = VehicleAvailabilitySerializer(slots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get all reviews for this vehicle"""
        vehicle = self.get_object()
        reviews = Review.objects.filter(vehicle=vehicle).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

class VehiclePhotoViewSet(viewsets.ModelViewSet):
    """ViewSet for VehiclePhoto model"""
    queryset = VehiclePhoto.objects.all()
    serializer_class = VehiclePhotoSerializer
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['vehicle', 'is_primary']

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set this photo as primary for the vehicle"""
        photo = self.get_object()
        # Remove primary flag from other photos of the same vehicle
        VehiclePhoto.objects.filter(vehicle=photo.vehicle).update(is_primary=False)
        # Set this photo as primary
        photo.is_primary = True
        photo.save()
        return Response({'message': 'Photo set as primary successfully'})

class VehicleAvailabilityViewSet(viewsets.ModelViewSet):
    """ViewSet for VehicleAvailability model"""
    queryset = VehicleAvailability.objects.all()
    serializer_class = VehicleAvailabilitySerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['vehicle', 'is_available', 'start_date', 'end_date']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['start_date']

class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for Review model"""
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['vehicle', 'host', 'customer', 'rating', 'is_verified_booking']
    ordering_fields = ['rating', 'created_at']
    ordering = ['-created_at']

    def create(self, request, *args, **kwargs):
        """Override create to update vehicle and host ratings"""
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            review_data = response.data
            # Update vehicle rating
            vehicle = Vehicle.objects.get(id=review_data['vehicle_id'])
            avg_rating = Review.objects.filter(vehicle=vehicle).aggregate(Avg('rating'))['rating__avg']
            vehicle.rating = round(avg_rating, 2)
            vehicle.total_bookings = Review.objects.filter(vehicle=vehicle).count()
            vehicle.save()
            
            # Update host rating
            host = Host.objects.get(id=review_data['host_id'])
            avg_rating = Review.objects.filter(host=host).aggregate(Avg('rating'))['rating__avg']
            host.rating = round(avg_rating, 2)
            host.total_bookings = Review.objects.filter(host=host).count()
            host.save()
        
        return response

# Authentication Views
class CustomerRegisterView(APIView):
    """Customer registration view"""
    
    def post(self, request):
        data = request.data.copy()
        # Hash password
        if 'password' in data:
            data['password'] = make_password(data['password'])
        
        serializer = CustomerSerializer(data=data)
        if serializer.is_valid():
            customer = serializer.save()
            # Generate and send OTP
            generate_and_send_otp.delay(customer.id, 'customer')
            return Response({
                'message': 'Customer registered successfully. OTP sent to email.',
                'customer_id': customer.id
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

