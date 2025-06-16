from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Count
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from geopy.distance import geodesic
import random
import string
from datetime import datetime, timedelta

from .models import (
    Location, User, Vehicle, VehiclePhoto, 
    VehicleAvailability, Review
)
from .serializers import (
    LocationSerializer, UserSerializer, UserListSerializer,
    VehicleSerializer, VehiclePhotoSerializer, VehicleAvailabilitySerializer,
    ReviewSerializer, VehicleListSerializer
)
from .tasks import generate_and_send_otp, send_otp_sms


# Viewsets
class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for Location model"""
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'state', 'country', 'pincode']
    search_fields = ['city', 'state', 'address', 'pincode']
    ordering_fields = ['city', 'state', 'created_at']
    ordering = ['-created_at']

class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model (both customers and hosts)"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['email_verified', 'phone_verified', 'driving_license_verified', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return UserListSerializer
        return UserSerializer

    @action(detail=True, methods=['post'])
    def verify_driving_license(self, request, pk=None):
        """Action to verify user's driving license"""
        user = self.get_object()
        user.driving_license_verified = True
        user.save()
        return Response({'message': 'Driving license verified successfully'})

    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        """Get user's booking history (reviews they've given)"""
        user = self.get_object()
        reviews = Review.objects.filter(user=user).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def vehicles(self, request, pk=None):
        """Get user's vehicles (for hosts)"""
        user = self.get_object()
        vehicles = Vehicle.objects.filter(owner=user).order_by('-created_at')
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
    filterset_fields = ['vehicle', 'user', 'rating', 'is_verified_booking']
    ordering_fields = ['rating', 'created_at']
    ordering = ['-created_at']

    def create(self, request, *args, **kwargs):
        """Override create to update vehicle ratings"""
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            review_data = response.data
            # Update vehicle rating
            vehicle = Vehicle.objects.get(id=review_data['vehicle_id'])
            avg_rating = Review.objects.filter(vehicle=vehicle).aggregate(Avg('rating'))['rating__avg']
            vehicle.rating = round(avg_rating, 2) if avg_rating else 0.0
            vehicle.total_bookings = Review.objects.filter(vehicle=vehicle).count()
            vehicle.save()
        
        return response


# User Authentication Views
class UserRegisterView(APIView):
    """User registration view"""
    
    def post(self, request):
        data = request.data.copy()
        # Hash password
        if 'password' in data:
            data['password'] = make_password(data['password'])

        if 'phone' not in data or not data['phone']:
            data['phone'] = None  
        
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            user.password = data['password']  # Ensure password is hashed
            user.save()
            # Generate and send OTP
            try:
                generate_and_send_otp.delay(user.id, 'user')
            except:
                # If celery is not configured, generate OTP without task
                otp = ''.join(random.choices(string.digits, k=6))
                user.otp = otp
                user.save()
            
            return Response({
                'message': 'User registered successfully. OTP sent to email.',
                'user_id': user.id
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(APIView):
    """User login view"""
    
    def post(self, request):
        email = request.data.get('email')
        phone = request.data.get('phone')
        password = request.data.get('password')
        
        # Check if either email or phone is provided
        if not (email or phone) or not password:
            return Response({
                'error': 'Either email or phone, and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Try to find user by email or phone
            if email:
                user = User.objects.get(email=email)
            else:
                user = User.objects.get(phone=phone)

            if check_password(password, user.password):
                if not user.is_active:
                    return Response({
                        'error': 'Account is deactivated'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                serializer = UserSerializer(user)
                return Response({
                    'message': 'Login successful',
                    'user': serializer.data,
                    'token': str(user.private_token)
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found with provided credentials'
            }, status=status.HTTP_404_NOT_FOUND)

class UserAddPhoneView(APIView):
    """User add phone number view"""
    
    def post(self, request):
        user_id = request.data.get('user_id')
        phone = request.data.get('phone')
        
        if not user_id or not phone:
            return Response({
                'error': 'user_id and phone are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # if phone number is already present with some other user
        if User.objects.filter(phone=phone).exclude(id=user_id).exists():
            return Response({
                'error': 'This phone number is already associated with another user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            otp = ''.join(random.choices(string.digits, k=6))
            user = User.objects.get(id=user_id)
            user.phone = phone
            user.otp = otp  # Save OTP for verification
            user.phone_verified = False  # Set phone as not verified
            user.save()
            send_otp_sms.delay(phone, otp)  # Send OTP via SMS
            return Response({
                'message': 'OTP has been sent to the provided phone number',
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
class UserUpdateProfileView(APIView):
    """User update profile view"""
    
    def put(self, request):
        user_id = request.data.get('user_id')
        data = request.data.copy()
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            serializer = UserSerializer(user, data=data, partial=True)
            if serializer.is_valid():
                updated_user = serializer.save()
                return Response({
                    'message': 'Profile updated successfully',
                    'user': UserSerializer(updated_user).data
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
class UserDeleteView(APIView):
    """User delete account view"""
    def delete(self, request):
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            user.is_active = False  # Soft delete
            user.save()
            return Response({
                'message': 'User account deactivated successfully'
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

class VerifyEmailView(APIView):
    """Email verification view"""
    
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        
        if not all([email, otp]):
            return Response({
                'error': 'email and otp are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            
            if str(user.otp) == str(otp):
                user.email_verified = True
                user.otp = ''  # Clear OTP after verification
                user.save()
                return Response({
                    'message': 'Email verified successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid OTP'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

class VerifyPhoneView(APIView):
    """Phone verification view"""
    
    def post(self, request):
        user_id = request.data.get('user_id')
        otp = request.data.get('otp')
        
        if not all([user_id, otp]):
            return Response({
                'error': 'user_id and otp are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            
            if str(user.otp) == str(otp):
                user.phone_verified = True
                user.otp = ''  # Clear OTP after verification
                user.save()
                return Response({
                    'message': 'Phone verified successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid OTP'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

class ResendOTPView(APIView):
    """Resend OTP view"""
    
    def post(self, request):
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            
            # Generate and send new OTP
            try:
                if not user.email_verified:
                    generate_and_send_otp.delay(user.id, 'user')
                else:
                    otp = ''.join(random.choices(string.digits, k=6))
                    user.otp = otp
                    user.save()
                    send_otp_sms.delay(user.phone, otp)
            except:
                # If celery is not configured, generate OTP without task
                otp = ''.join(random.choices(string.digits, k=6))
                user.otp = otp
                user.save()
            
            return Response({
                'message': 'OTP sent successfully'
            }, status=status.HTTP_200_OK)
                
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)



# Vehicle Search and Discovery Views
class VehicleSearchView(APIView):
    """Advanced vehicle search view"""
    
    def get(self, request):
        queryset = Vehicle.objects.filter(is_available=True, is_verified=True)
        
        # Filter parameters
        vehicle_type = request.GET.get('vehicle_type')
        fuel_type = request.GET.get('fuel_type')
        transmission_type = request.GET.get('transmission_type')
        city = request.GET.get('city')
        state = request.GET.get('state')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        min_rating = request.GET.get('min_rating')
        search_query = request.GET.get('q')
        
        # Apply filters
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)
        if fuel_type:
            queryset = queryset.filter(fuel_type=fuel_type)
        if transmission_type:
            queryset = queryset.filter(transmission_type=transmission_type)
        if city:
            queryset = queryset.filter(location__city__icontains=city)
        if state:
            queryset = queryset.filter(location__state__icontains=state)
        if min_price:
            queryset = queryset.filter(price_per_hour__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_per_hour__lte=max_price)
        if min_rating:
            queryset = queryset.filter(rating__gte=min_rating)
        if search_query:
            queryset = queryset.filter(
                Q(vehicle_name__icontains=search_query) |
                Q(vehicle_brand__icontains=search_query) |
                Q(vehicle_model__icontains=search_query)
            )
        
        # Order by rating and price
        ordering = request.GET.get('ordering', '-rating')
        queryset = queryset.order_by(ordering)
        
        serializer = VehicleListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

class NearbyVehiclesView(APIView):
    """Find vehicles near a location"""
    
    def get(self, request):
        latitude = request.GET.get('latitude')
        longitude = request.GET.get('longitude')
        radius = request.GET.get('radius', 10)  # Default 10km radius
        
        if not latitude or not longitude:
            return Response({
                'error': 'latitude and longitude are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user_location = (float(latitude), float(longitude))
            radius = float(radius)
        except ValueError:
            return Response({
                'error': 'Invalid latitude, longitude, or radius'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        vehicles = Vehicle.objects.filter(
            is_available=True, 
            is_verified=True,
            location__latitude__isnull=False,
            location__longitude__isnull=False
        )
        
        nearby_vehicles = []
        for vehicle in vehicles:
            vehicle_location = (vehicle.location.latitude, vehicle.location.longitude)
            distance = geodesic(user_location, vehicle_location).kilometers
            
            if distance <= radius:
                vehicle_data = VehicleListSerializer(vehicle, context={'request': request}).data
                vehicle_data['distance'] = round(distance, 2)
                nearby_vehicles.append(vehicle_data)
        
        # Sort by distance
        nearby_vehicles.sort(key=lambda x: x['distance'])
        
        return Response(nearby_vehicles)

class AvailableVehiclesView(APIView):
    """Get available vehicles for specific dates"""
    
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date or not end_date:
            return Response({
                'error': 'start_date and end_date are required (YYYY-MM-DD format)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get vehicles that have availability slots for the requested dates
        available_vehicles = Vehicle.objects.filter(
            is_available=True,
            is_verified=True,
            availability_slots__is_available=True,
            availability_slots__start_date__lte=start_date,
            availability_slots__end_date__gte=end_date
        ).distinct()
        
        serializer = VehicleListSerializer(available_vehicles, many=True, context={'request': request})
        return Response(serializer.data)

class VehiclePhotoUploadView(APIView):
    """Upload multiple photos for a vehicle"""
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        vehicle_id = request.data.get('vehicle_id')
        photos = request.FILES.getlist('photos')
        
        if not vehicle_id:
            return Response({
                'error': 'vehicle_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not photos:
            return Response({
                'error': 'At least one photo is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({
                'error': 'Vehicle not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        uploaded_photos = []
        for i, photo in enumerate(photos):
            vehicle_photo = VehiclePhoto.objects.create(
                vehicle=vehicle,
                photo=photo,
                is_primary=(i == 0 and not VehiclePhoto.objects.filter(vehicle=vehicle, is_primary=True).exists())
            )
            uploaded_photos.append(VehiclePhotoSerializer(vehicle_photo).data)
        
        return Response({
            'message': f'{len(uploaded_photos)} photos uploaded successfully',
            'photos': uploaded_photos
        }, status=status.HTTP_201_CREATED)

  