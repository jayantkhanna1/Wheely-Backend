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
    VehicleAvailability, Review, Ride
)
from .serializers import (
    LocationSerializer, UserSerializer, UserListSerializer,
    VehicleSerializer, VehiclePhotoSerializer, VehicleAvailabilitySerializer,
    ReviewSerializer, VehicleListSerializer, RideSerializer
)
from .tasks import *
from .supabase_client import get_public_supabase_client, get_supabase_client
from django.db import transaction
import json
import logging

logger = logging.getLogger(__name__)

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


# User Authentication Views with Supabase Integration
class UserRegisterView(APIView):
    """User registration view with Supabase integration"""
    
    def post(self, request):
        data = request.data.copy()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Register user with Supabase Auth
            supabase = get_public_supabase_client()
            
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "first_name": data.get('first_name', ''),
                        "last_name": data.get('last_name', ''),
                    }
                }
            })
            
            if auth_response.user:
                # Create user in Django database
                if 'phone' not in data or not data['phone']:
                    data['phone'] = None
                
                # Don't hash password again as Supabase handles it
                data.pop('password', None)
                
                serializer = UserSerializer(data=data)
                if serializer.is_valid():
                    user = serializer.save()
                    user.otp = ''.join(random.choices(string.digits, k=6))  # Generate OTP
                    user.email_verified = False
                    user.save()
                    
                    return Response({
                        'message': 'User registered successfully. Please check your email for verification.',
                        'user_id': user.id,
                        'supabase_user_id': auth_response.user.id
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'error': 'Failed to register user with Supabase'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response({
                'error': f'Registration failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(APIView):
    """User login view with Supabase integration"""
    
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
            # Authenticate with Supabase
            supabase = get_public_supabase_client()
            
            # Use email for Supabase auth (phone auth would need different setup)
            if not email and phone:
                # Try to find user by phone to get email
                try:
                    user = User.objects.get(phone=phone)
                    email = user.email
                except User.DoesNotExist:
                    return Response({
                        'error': 'User not found with provided phone number'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user and auth_response.session:
                # Get Django user
                try:
                    user = User.objects.get(email=email)
                    
                    if not user.is_active:
                        return Response({
                            'error': 'Account is deactivated'
                        }, status=status.HTTP_401_UNAUTHORIZED)
                    
                    # Update email verification status
                    if not user.email_verified and auth_response.user.email_confirmed_at:
                        user.email_verified = True
                        user.save()
                    
                    serializer = UserSerializer(user)
                    return Response({
                        'message': 'Login successful',
                        'user': serializer.data,
                        'token': str(user.private_token),
                        'supabase_token': auth_response.session.access_token
                    }, status=status.HTTP_200_OK)
                    
                except User.DoesNotExist:
                    return Response({
                        'error': 'User not found in local database'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                'error': f'Login failed: {str(e)}'
            }, status=status.HTTP_401_UNAUTHORIZED)

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
    """Email verification view - now handled by Supabase"""
    
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')  # Supabase verification token

        if not all([email, otp]):
            return Response({
                'error': 'email and otp are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
           
            if not User.objects.filter(email=email).exists():
                return Response({
                    'error': 'User not found with this email'
                }, status=status.HTTP_404_NOT_FOUND)
            
            user = User.objects.get(email=email)
            if str(user.otp) == str(otp):
                user.email_verified = True
                user.otp = ''  # Clear OTP after verification
                user.save()
                return Response({
                    'message': 'Email verified successfully',
                    'user': UserSerializer(user).data
                }, status=status.HTTP_200_OK)
            
            return Response({
                    'error': 'Invalid OTP'
            }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            return Response({
                'error': f'Verification failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)

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
                    # Resend email verification through Supabase
                    supabase = get_public_supabase_client()
                    supabase.auth.resend({
                        'type': 'signup',
                        'email': user.email
                    })
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

class UserAutoLoginView(APIView):
    """User auto-login view"""

    def post(self, request):
        user_id = request.data.get('user_id')
        private_token = request.data.get('private_token')
        supabase_token = request.data.get('supabase_token')

        if not all([user_id, private_token]):
            return Response({
                'error': 'user_id and private_token are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id, private_token=private_token)
            if not user.is_active:
                return Response({
                    'error': 'Account is deactivated'
                }, status=status.HTTP_401_UNAUTHORIZED)
            if not user.email_verified:
                return Response({
                    'error': 'Account is not verified'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Optionally verify Supabase token if provided
            if supabase_token:
                try:
                    supabase = get_public_supabase_client()
                    supabase.auth.get_user(supabase_token)
                except:
                    logger.warning(f"Invalid Supabase token for user {user_id}")

            serializer = UserSerializer(user)
            return Response({
                'message': 'Auto-login successful',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'Invalid user_id or private_token'
            }, status=status.HTTP_404_NOT_FOUND)
        except:
            return Response({
                'error': 'An unexpected error occurred'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MyRideView(APIView):
    """View to get rides booked by the user"""
    
    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
            rides = Ride.objects.filter(user=user).order_by('-created_at')
            serializer = RideSerializer(rides, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)


# Vehicle Search and Discovery Views
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

class VehicleUploadView(APIView):
    def post(self, request):
        data = request.data.copy()
        # Validate required fields
        if 'owner_id' not in data:
            return Response({
                'error': 'owner_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        if "location" not in data:
            return Response({
                'error': 'location is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For non-bicycle vehicles, documents are required
        vehicle_type = data.get('vehicle_type', '')
        if vehicle_type != 'Bicycle':
            # Check for both FILES and data fields (for JSON file data)
            required_docs = ['vehicle_rc', 'vehicle_insurance', 'vehicle_pollution_certificate']
            missing_docs = []
            
            for doc in required_docs:
                # Check if document exists in either FILES or data
                if doc not in request.FILES and doc not in data:
                    missing_docs.append(doc)
            
            if missing_docs:
                print(f"Missing required documents: {', '.join(missing_docs)}")
                return Response({
                    'error': f'The following documents are required: {", ".join(missing_docs)}'
                }, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                # Create location
                location_data = data.pop('location')
                
                # Handle location data parsing
                if isinstance(location_data, str):
                    try:
                        location_data = json.loads(location_data)
                    except json.JSONDecodeError:
                        print("Invalid JSON format for location")
                        return Response({
                            'error': 'Invalid JSON format for location'
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif isinstance(location_data, list) and len(location_data) >= 1:
                    try:
                        location_data = json.loads(location_data[0])
                    except (json.JSONDecodeError, IndexError):
                        print("Invalid location data format")
                        return Response({
                            'error': 'Invalid location data format'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                location_serializer = LocationSerializer(data=location_data)
                if location_serializer.is_valid():
                    location_instance = location_serializer.save()
                    data['location_id'] = location_instance.id
                else:
                    print("Location validation failed:", location_serializer.errors)
                    return Response({
                        'error': 'Location validation failed',
                        'details': location_serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create vehicle
                vehicle_serializer = VehicleSerializer(data=data)
                if vehicle_serializer.is_valid():
                    vehicle = vehicle_serializer.save()
                else:
                    print("Vehicle validation failed:", vehicle_serializer.errors)
                    return Response({
                        'error': 'Vehicle validation failed',
                        'details': vehicle_serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Handle vehicle photos
                photos_data = []
                
                # Check for photos in FILES first
                photo_files = request.FILES.getlist('photos')
                if photo_files:
                    for i, photo_file in enumerate(photo_files):
                        photo_instance = VehiclePhoto.objects.create(
                            vehicle=vehicle,
                            photo=photo_file,
                            is_primary=i == 0
                        )
                        photos_data.append({
                            'id': photo_instance.id,
                            'photo': photo_instance.photo.url if photo_instance.photo else None,
                            'is_primary': photo_instance.is_primary,
                            'created_at': photo_instance.created_at
                        })
                else:
                    # Handle photos from data (JSON format from mobile)
                    photos_json = data.getlist('photos') if hasattr(data, 'getlist') else []
                    for i, photo_json in enumerate(photos_json):
                        try:
                            if isinstance(photo_json, str):
                                photo_info = json.loads(photo_json)
                            else:
                                photo_info = photo_json
                            
                            # Here you would handle the photo_info which contains uri, type, name
                            # For now, we'll skip actual file creation since we need the actual file content
                            print(f"Photo info received: {photo_info}")
                            # You might want to download from URI or handle differently based on your setup
                            
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"Error processing photo {i}: {str(e)}")
                            continue
                
                # Handle availability slots
                availability_data = []
                if 'availability_slots' in data:
                    availability_slots = data.get('availability_slots', [])
                    # Handle JSON string if sent as string
                    if isinstance(availability_slots, str):
                        try:
                            availability_slots = json.loads(availability_slots)
                        except json.JSONDecodeError:
                            print("Invalid JSON format for availability_slots:", availability_slots)
                            return Response({
                                'error': 'Invalid JSON format for availability_slots'
                            }, status=status.HTTP_400_BAD_REQUEST)
                    
                    print("Availability slots data:", availability_slots)
                    
                    # Handle new format with specificDates and timeSlots
                    if isinstance(availability_slots, dict) and 'timeSlots' in availability_slots:
                        print("Processing new format with timeSlots")
                        time_slots = availability_slots.get('timeSlots', [])
                        for slot_data in time_slots:
                            slot_data['vehicle'] = vehicle.id
                            availability_serializer = VehicleAvailabilitySerializer(data=slot_data)
                            if availability_serializer.is_valid():
                                availability_instance = availability_serializer.save()
                                availability_data.append(availability_serializer.data)
                            else:
                                print("Availability slot validation failed:", availability_serializer.errors)
                                return Response({
                                    'error': 'Availability slot validation failed',
                                    'details': availability_serializer.errors
                                }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Handle original list format
                    elif isinstance(availability_slots, list):
                        print("Processing original list format")
                        for slot_data in availability_slots:
                            slot_data['vehicle'] = vehicle.id
                            availability_serializer = VehicleAvailabilitySerializer(data=slot_data)
                            if availability_serializer.is_valid():
                                availability_instance = availability_serializer.save()
                                availability_data.append(availability_serializer.data)
                            else:
                                print("Availability slot validation failed:", availability_serializer.errors)
                                return Response({
                                    'error': 'Availability slot validation failed',
                                    'details': availability_serializer.errors
                                }, status=status.HTTP_400_BAD_REQUEST)
                    
                    else:
                        print("Invalid availability_slots format:", type(availability_slots))
                        return Response({
                            'error': 'Invalid availability_slots format. Expected list or object with timeSlots.'
                        }, status=status.HTTP_400_BAD_REQUEST)
    
                # Trigger vehicle verification task asynchronously
                verify_vehicle.delay(vehicle.id)
                
                # Return success response with created data
                response_data = {
                    'message': 'Vehicle uploaded successfully',
                    'vehicle_id': vehicle.id,
                    'vehicle': VehicleSerializer(vehicle).data,
                    'photos_uploaded': len(photos_data),
                    'availability_slots_created': len(availability_data)
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            print("An error occurred while uploading vehicle:", str(e))
            return Response({
                'error': 'An error occurred while uploading vehicle',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AvailableVehicle(APIView):
    def get(self, request):
        data = request.query_params.copy()
        required_data = ['location', 'start_date', 'end_date', 'start_time', 'end_time', 'vehicle_type']
        for field in required_data:
            if field not in data or not data[field]:
                return Response({
                    'error': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        try:
            location = data['location']
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            # Changed from '%H:%M' to '%H:%M:%S' to handle seconds
            start_time = datetime.strptime(data['start_time'], '%H:%M:%S').time()
            end_time = datetime.strptime(data['end_time'], '%H:%M:%S').time()

            # Find vehicles based on location (prioritize city, then state, then other fields)
            vehicles = Vehicle.objects.filter(
                is_available=True,
                is_verified=True,
                vehicle_type=data['vehicle_type']
            ).filter(
                Q(location__city__icontains=location) |
                Q(location__state__icontains=location) 
            ).distinct()

            # Filter vehicles that have availability slots covering the requested date range
            available_vehicles = []
            for vehicle in vehicles:
                availability_slots = vehicle.availability_slots.filter(
                    is_available=True,
                    start_date__lte=start_date,  # Slot starts before or on requested start date
                    end_date__gte=end_date       # Slot ends after or on requested end date
                )
                
                for slot in availability_slots:
                    # Check if the requested time range overlaps with the slot time range
                    if (start_time >= slot.start_time and start_time <= slot.end_time) and \
                       (end_time >= slot.start_time and end_time <= slot.end_time):
                        available_vehicles.append(vehicle)
                        break

            serializer = VehicleListSerializer(available_vehicles, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({
                'error': f'Invalid date or time format: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
               
class VehiclesUploadedByUser(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id)
            vehicles = Vehicle.objects.filter(owner=user).order_by('-created_at')
            serializer = VehicleListSerializer(vehicles, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

class VehicleDetailView(APIView):
    """Get detailed information about a vehicle"""
    
    def get(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            serializer = VehicleSerializer(vehicle, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Vehicle.DoesNotExist:
            return Response({
                'error': 'Vehicle not found'
            }, status=status.HTTP_404_NOT_FOUND)