from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'locations', views.LocationViewSet)
router.register(r'customers', views.CustomerViewSet)
router.register(r'hosts', views.HostViewSet)
router.register(r'vehicles', views.VehicleViewSet)
router.register(r'vehicle-photos', views.VehiclePhotoViewSet)
router.register(r'vehicle-availability', views.VehicleAvailabilityViewSet)
router.register(r'reviews', views.ReviewViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/customer/register/', views.CustomerRegisterView.as_view(), name='customer-register'),
    path('auth/host/register/', views.HostRegisterView.as_view(), name='host-register'),
    path('auth/customer/login/', views.CustomerLoginView.as_view(), name='customer-login'),
    path('auth/host/login/', views.HostLoginView.as_view(), name='host-login'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('auth/verify-phone/', views.VerifyPhoneView.as_view(), name='verify-phone'),
    path('auth/resend-otp/', views.ResendOTPView.as_view(), name='resend-otp'),
    
    # Search and filtering endpoints
    path('vehicles/search/', views.VehicleSearchView.as_view(), name='vehicle-search'),
    path('vehicles/nearby/', views.NearbyVehiclesView.as_view(), name='nearby-vehicles'),
    path('vehicles/available/', views.AvailableVehiclesView.as_view(), name='available-vehicles'),
    
    # Stats endpoints
    path('hosts/<int:host_id>/stats/', views.HostStatsView.as_view(), name='host-stats'),
    path('customers/<int:customer_id>/stats/', views.CustomerStatsView.as_view(), name='customer-stats'),
    
    # Upload endpoints
    path('upload/vehicle-photos/', views.VehiclePhotoUploadView.as_view(), name='upload-vehicle-photos'),
]