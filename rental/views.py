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
    Location, Customer, Host, Vehicle, VehiclePhoto, 
    VehicleAvailability, Review
)
from .serializers import (
    LocationSerializer, CustomerSerializer, HostSerializer,
    VehicleSerializer, VehiclePhotoSerializer, VehicleAvailabilitySerializer,
    ReviewSerializer, CustomerListSerializer, HostListSerializer,
    VehicleListSerializer
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
            vehicle = Vehicle.objects.get(id=review_data['vehicle'])
            avg_rating = Review.objects.filter(vehicle=vehicle).aggregate(Avg('rating'))['rating__avg']
            vehicle.rating = round(avg_rating, 2) if avg_rating else 0.0
            vehicle.total_bookings = Review.objects.filter(vehicle=vehicle).count()
            vehicle.save()
            
            # Update host rating
            host = Host.objects.get(id=review_data['host'])
            avg_rating = Review.objects.filter(host=host).aggregate(Avg('rating'))['rating__avg']
            host.rating = round(avg_rating, 2) if avg_rating else 0.0
            host.total_bookings = Review.objects.filter(host=host).count()
            host.save()
        
        return response



# Customer Views
class CustomerRegisterView(APIView):
    """Customer registration view"""
    
    def post(self, request):
        data = request.data.copy()
        # Hash password
        if 'password' in data:
            data['password'] = make_password(data['password'])

        if 'phone' not in data or not data['phone']:
            data['phone'] = None  
        
        serializer = CustomerSerializer(data=data)
        if serializer.is_valid():
            customer = serializer.save()
            # Generate and send OTP
            try:
                generate_and_send_otp.delay(customer.id, 'customer')
            except:
                # If celery is not configured, generate OTP without task
                otp = ''.join(random.choices(string.digits, k=6))
                customer.otp = otp
                customer.save()
            
            return Response({
                'message': 'Customer registered successfully. OTP sent to email.',
                'customer_id': customer.id
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CustomerLoginView(APIView):
    """Customer login view"""
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            customer = Customer.objects.get(email=email)
            if check_password(password, customer.password):
                if not customer.is_active:
                    return Response({
                        'error': 'Account is deactivated'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                serializer = CustomerSerializer(customer)
                return Response({
                    'message': 'Login successful',
                    'customer': serializer.data,
                    'token': str(customer.private_token)
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        except Customer.DoesNotExist:
            return Response({
                'error': 'Customer not found'
            }, status=status.HTTP_404_NOT_FOUND)

class CustomerStatsView(APIView):
    """Get customer statistics"""
    
    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({
                'error': 'Customer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate statistics
        total_bookings = Review.objects.filter(customer=customer).count()
        vehicle_types_used = Review.objects.filter(customer=customer).values(
            'vehicle__vehicle_type'
        ).annotate(count=Count('vehicle__vehicle_type')).order_by('-count')
        
        # Average rating given by customer
        avg_rating_given = Review.objects.filter(customer=customer).aggregate(
            avg_rating=Avg('rating')
        )['avg_rating']
        
        # Recent bookings
        recent_bookings = Review.objects.filter(customer=customer).order_by('-created_at')[:5]
        recent_bookings_data = ReviewSerializer(recent_bookings, many=True, context={'request': request}).data
        
        stats = {
            'customer_info': CustomerSerializer(customer).data,
            'total_bookings': total_bookings,
            'average_rating_given': round(avg_rating_given, 2) if avg_rating_given else 0.0,
            'vehicle_types_used': list(vehicle_types_used),
            'recent_bookings': recent_bookings_data
        }
        
        return Response(stats)

# Host Views
class HostLoginView(APIView):
    """Host login view"""
    
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
            # Try to find host by email or phone
            if email:
                host = Host.objects.get(email=email)
            else:
                host = Host.objects.get(phone=phone)

            if check_password(password, host.password):
                if not host.is_active:
                    return Response({
                        'error': 'Account is deactivated'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                serializer = HostSerializer(host)
                return Response({
                    'message': 'Login successful',
                    'host': serializer.data,
                    'token': str(host.private_token)
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Invalid credentials'
                }, status=status.HTTP_401_UNAUTHORIZED)
        except Host.DoesNotExist:
            return Response({
                'error': 'Host not found with provided credentials'
            }, status=status.HTTP_404_NOT_FOUND)
        
class HostRegisterView(APIView):
    """Host registration view"""
    
    def post(self, request):
        data = request.data.copy()
        # Hash password
        if 'password' in data:
            data['password'] = make_password(data['password'])
        
        serializer = HostSerializer(data=data)
        if serializer.is_valid():
            host = serializer.save()
            host.password = data['password']  # Ensure password is hashed 
            host.save()
            # Generate and send OTP
            try:
                generate_and_send_otp.delay(host.id, 'host')
            except:
                # If celery is not configured, generate OTP without task
                otp = ''.join(random.choices(string.digits, k=6))
                host.otp = otp
                host.save()
            
            return Response({
                'message': 'Host registered successfully. OTP sent to email.',
                'host_id': host.id
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class HostStatsView(APIView):
    """Get host statistics"""
    
    def get(self, request, host_id):
        try:
            host = Host.objects.get(id=host_id)
        except Host.DoesNotExist:
            return Response({
                'error': 'Host not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate statistics
        total_vehicles = Vehicle.objects.filter(owner=host).count()
        active_vehicles = Vehicle.objects.filter(owner=host, is_available=True).count()
        verified_vehicles = Vehicle.objects.filter(owner=host, is_verified=True).count()
        total_reviews = Review.objects.filter(host=host).count()
        
        # Rating distribution
        rating_distribution = Review.objects.filter(host=host).values('rating').annotate(
            count=Count('rating')
        ).order_by('rating')
        
        # Recent reviews
        recent_reviews = Review.objects.filter(host=host).order_by('-created_at')[:5]
        recent_reviews_data = ReviewSerializer(recent_reviews, many=True, context={'request': request}).data
        
        stats = {
            'host_info': HostSerializer(host).data,
            'total_vehicles': total_vehicles,
            'active_vehicles': active_vehicles,
            'verified_vehicles': verified_vehicles,
            'total_reviews': total_reviews,
            'average_rating': host.rating,
            'total_bookings': host.total_bookings,
            'rating_distribution': list(rating_distribution),
            'recent_reviews': recent_reviews_data
        }
        
        return Response(stats)

class HostAddPhoneView(APIView):
    """Host add phone number view"""
    
    def post(self, request):
        host_id = request.data.get('host_id')
        phone = request.data.get('phone')
        
        if not host_id or not phone:
            return Response({
                'error': 'host_id and phone are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # if phone number is already present with some other host
        if Host.objects.filter(phone=phone).exclude(id=host_id).exists():
            return Response({
                'error': 'This phone number is already associated with another host'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            otp = ''.join(random.choices(string.digits, k=6))
            host = Host.objects.get(id=host_id)
            host.phone = phone
            host.otp = otp  # Save OTP for verification
            host.phone_verified = False  # Set phone as not verified
            host.save()
            send_otp_sms.delay(phone, otp)  # Send OTP via SMS
            return Response({
                'message': 'OTP has been sent to the provided phone number',
            }, status=status.HTTP_200_OK)
        except Host.DoesNotExist:
            return Response({
                'error': 'Host not found'
            }, status=status.HTTP_404_NOT_FOUND)

class HostUpdateProfileView(APIView):
    """Host update profile view"""
    
    def put(self, request):
        host_id = request.data.get('host_id')
        data = request.data.copy()
        
        if not host_id:
            return Response({
                'error': 'host_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            host = Host.objects.get(id=host_id)
            serializer = HostSerializer(host, data=data, partial=True)
            if serializer.is_valid():
                updated_host = serializer.save()
                return Response({
                    'message': 'Profile updated successfully',
                    'host': HostSerializer(updated_host).data
                }, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Host.DoesNotExist:
            return Response({
                'error': 'Host not found'
            }, status=status.HTTP_404_NOT_FOUND)

class HostDeleteView(APIView):
    """Host delete account view"""
    
    def delete(self, request):
        host_id = request.data.get('host_id')
        
        if not host_id:
            return Response({
                'error': 'host_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            host = Host.objects.get(id=host_id)
            host.is_active = False  # Soft delete
            host.save()
            return Response({
                'message': 'Host account deactivated successfully'
            }, status=status.HTTP_200_OK)
        except Host.DoesNotExist:
            return Response({
                'error': 'Host not found'
            }, status=status.HTTP_404_NOT_FOUND)      


# Customer-Host Common Views

class VerifyEmailView(APIView):
    """Email verification view"""
    
    def post(self, request):
        email = request.data.get('email')
        user_type = request.data.get('user_type')  # 'customer' or 'host'
        otp = request.data.get('otp')
        
        if not all([email, user_type, otp]):
            return Response({
                'error': 'email, user_type, and otp are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if user_type == 'customer':
                user = Customer.objects.get(email=email)
            elif user_type == 'host':
                user = Host.objects.get(email=email)
            else:
                return Response({
                    'error': 'Invalid user_type. Must be customer or host'
                }, status=status.HTTP_400_BAD_REQUEST)
            
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
                
        except (Customer.DoesNotExist, Host.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

class VerifyPhoneView(APIView):
    """Phone verification view"""
    
    def post(self, request):
        user_id = request.data.get('user_id')
        user_type = request.data.get('user_type')  # 'customer' or 'host'
        otp = request.data.get('otp')
        
        if not all([user_id, user_type, otp]):
            return Response({
                'error': 'user_id, user_type, and otp are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if user_type == 'customer':
                user = Customer.objects.get(id=user_id)
            elif user_type == 'host':
                user = Host.objects.get(id=user_id)
            else:
                return Response({
                    'error': 'Invalid user_type. Must be customer or host'
                }, status=status.HTTP_400_BAD_REQUEST)
            
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
                
        except (Customer.DoesNotExist, Host.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

class ResendOTPView(APIView):
    """Resend OTP view"""
    
    def post(self, request):
        user_id = request.data.get('user_id')
        user_type = request.data.get('user_type')  # 'customer' or 'host'
        
        if not all([user_id, user_type]):
            return Response({
                'error': 'user_id and user_type are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if user_type == 'customer':
                user = Customer.objects.get(id=user_id)
            elif user_type == 'host':
                user = Host.objects.get(id=user_id)
            else:
                return Response({
                    'error': 'Invalid user_type. Must be customer or host'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate and send new OTP
            try:
                generate_and_send_otp.delay(user.id, user_type)
            except:
                # If celery is not configured, generate OTP without task
                otp = ''.join(random.choices(string.digits, k=6))
                user.otp = otp
                user.save()
            
            return Response({
                'message': 'OTP sent successfully'
            }, status=status.HTTP_200_OK)
                
        except (Customer.DoesNotExist, Host.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)



# Vehicle views
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
 


# Stats views




