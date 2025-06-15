from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'locations', LocationViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'hosts', HostViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'vehicle-photos', VehiclePhotoViewSet)
router.register(r'vehicle-availability', VehicleAvailabilityViewSet)
router.register(r'reviews', ReviewViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # Host Endpoints
    path('host/register/', HostRegisterView.as_view(), name='host-register'),
    path('host/login/', HostLoginView.as_view(), name='host-login'),
    path('hosts/<int:host_id>/stats/', HostStatsView.as_view(), name='host-stats'),
    path('host/addPhone/', HostAddPhoneView.as_view(), name='host-add-phone'),
    path('host/updateProfile/', HostUpdateProfileView.as_view(), name='host-update-profile'),
    path('host/deleteProfile/', HostDeleteView.as_view(), name='host-delete-profile'),

    # Customer Endpoints
    path('customer/register/', CustomerRegisterView.as_view(), name='customer-register'),
    path('customer/login/', CustomerLoginView.as_view(), name='customer-login'),
    path('customers/<int:customer_id>/stats/', CustomerStatsView.as_view(), name='customer-stats'),
    
    # Customer and Host Common Endpoints
    path('verifyEmail/', VerifyEmailView.as_view(), name='verify-email'),
    path('verifyPhone/', VerifyPhoneView.as_view(), name='verify-phone'),
    path('resendOtp/', ResendOTPView.as_view(), name='resend-otp'),

    # Vehicle Endpoints
    path('vehicles/search/', VehicleSearchView.as_view(), name='vehicle-search'),
    path('vehicles/nearby/', NearbyVehiclesView.as_view(), name='nearby-vehicles'),
    path('vehicles/available/', AvailableVehiclesView.as_view(), name='available-vehicles'),
    path('upload/vehicle-photos/', VehiclePhotoUploadView.as_view(), name='upload-vehicle-photos'),
]