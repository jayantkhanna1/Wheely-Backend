from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'locations', LocationViewSet)
router.register(r'users', UserViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'vehicle-photos', VehiclePhotoViewSet)
router.register(r'vehicle-availability', VehicleAvailabilityViewSet)
router.register(r'reviews', ReviewViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # User Authentication Endpoints
    path('user/register/', UserRegisterView.as_view(), name='user-register'),
    path('user/login/', UserLoginView.as_view(), name='user-login'),
    path('user/autoLogin/', UserAutoLoginView.as_view(), name='user-autologin'),
    path('user/addPhone/', UserAddPhoneView.as_view(), name='user-add-phone'),
    path('user/updateProfile/', UserUpdateProfileView.as_view(), name='user-update-profile'),
    path('user/deleteProfile/', UserDeleteView.as_view(), name='user-delete-profile'),
    path('user/verifyEmail/', VerifyEmailView.as_view(), name='verify-email'),
    path('user/verifyPhone/', VerifyPhoneView.as_view(), name='verify-phone'),
    path('user/resendOtp/', ResendOTPView.as_view(), name='resend-otp'),
    path('user/book/', UserBookVehicleView.as_view(), name='user-book-vehicle'),
    
    # Vehicle Search and Discovery Endpoints
    path('upload/vehicle/', VehicleUploadView.as_view(), name='upload-vehicle'),
    path('search/vehicles/', AvailableVehicle.as_view(), name='search-vehicles'),
    path('search/vehicle/<int:vehicle_id>/', VehicleDetailView.as_view(), name='vehicle-detail'),
    path('user/vehicles/', VehiclesUploadedByUser.as_view(), name='user-vehicles'),
    path('upload/vehicle-photos/', VehiclePhotoUploadView.as_view(), name='upload-vehicle-photos'),

]