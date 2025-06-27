from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import AnonymousUser
from .models import User
from .supabase_client import get_public_supabase_client
import logging

logger = logging.getLogger(__name__)

class SupabaseAuthBackend(BaseBackend):
    """Custom authentication backend for Supabase"""
    
    def authenticate(self, request, email=None, password=None, **kwargs):
        """Authenticate user with Supabase"""
        if not email or not password:
            return None
        
        try:
            supabase = get_public_supabase_client()
            
            # Authenticate with Supabase
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Get or create user in Django
                try:
                    user = User.objects.get(email=email)
                    # Update user info from Supabase if needed
                    if not user.email_verified and response.user.email_confirmed_at:
                        user.email_verified = True
                        user.save()
                except User.DoesNotExist:
                    # Create new user from Supabase data
                    user = User.objects.create(
                        email=email,
                        first_name=response.user.user_metadata.get('first_name', ''),
                        last_name=response.user.user_metadata.get('last_name', ''),
                        email_verified=bool(response.user.email_confirmed_at),
                        is_active=True
                    )
                
                return user
            
        except Exception as e:
            logger.error(f"Supabase authentication error: {str(e)}")
            return None
        
        return None
    
    def get_user(self, user_id):
        """Get user by ID"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

class SupabaseJWTBackend(BaseBackend):
    """JWT token authentication backend for Supabase"""
    
    def authenticate(self, request, token=None, **kwargs):
        """Authenticate user with Supabase JWT token"""
        if not token:
            # Try to get token from Authorization header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            else:
                return None
        
        try:
            supabase = get_public_supabase_client()
            
            # Verify token with Supabase
            response = supabase.auth.get_user(token)
            
            if response.user:
                # Get or create user in Django
                try:
                    user = User.objects.get(email=response.user.email)
                except User.DoesNotExist:
                    user = User.objects.create(
                        email=response.user.email,
                        first_name=response.user.user_metadata.get('first_name', ''),
                        last_name=response.user.user_metadata.get('last_name', ''),
                        email_verified=bool(response.user.email_confirmed_at),
                        is_active=True
                    )
                
                return user
            
        except Exception as e:
            logger.error(f"JWT authentication error: {str(e)}")
            return None
        
        return None