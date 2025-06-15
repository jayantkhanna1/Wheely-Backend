from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Customer, Host, Vehicle, Review
import random
import string
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_otp_email(email, otp, user_type='customer'):
    """Send OTP email to user for verification"""
    try:
        subject = 'Wheely - Email Verification OTP'
        message = f'''
        Hi there!
        
        Your OTP for email verification is: {otp}
        
        This OTP is valid for 10 minutes.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        Wheely Team
        '''
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )
        logger.info(f"OTP email sent successfully to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        return False

@shared_task
def send_booking_confirmation_email(customer_email, vehicle_name, booking_details):
    """Send booking confirmation email to customer"""
    try:
        subject = f'Wheely - Booking Confirmation for {vehicle_name}'
        message = f'''
        Hi there!
        
        Your booking has been confirmed!
        
        Vehicle: {vehicle_name}
        Booking Details: {booking_details}
        
        Have a great trip!
        
        Best regards,
        Wheely Team
        '''
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [customer_email],
            fail_silently=False,
        )
        logger.info(f"Booking confirmation email sent to {customer_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send booking confirmation email: {str(e)}")
        return False

@shared_task
def generate_and_send_otp(user_id, user_type):
    """Generate OTP and send to user"""
    try:
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        
        if user_type == 'customer':
            user = Customer.objects.get(id=user_id)
        else:
            user = Host.objects.get(id=user_id)
        
        # Save OTP to user
        user.otp = otp
        user.save()
        
        # Send OTP email
        # send_otp_email.delay(user.email, otp, user_type) # commented this line during testing will start it while in production
        
        logger.info(f"OTP generated and sent for {user_type} ID: {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate and send OTP: {str(e)}")
        return False

@shared_task
def send_otp_sms(phone_number, otp):
    """Send OTP via SMS to user for verification"""
    try:
        # Here you would integrate with an SMS gateway API
        # For example, using Twilio or any other service
        # This is a placeholder for actual SMS sending logic
        logger.info(f"OTP {otp} sent to {phone_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP SMS to {phone_number}: {str(e)}")
        return False
    
@shared_task
def update_vehicle_ratings():
    """Update vehicle ratings based on reviews"""
    try:
        vehicles = Vehicle.objects.all()
        for vehicle in vehicles:
            reviews = Review.objects.filter(vehicle=vehicle)
            if reviews.exists():
                avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
                vehicle.rating = round(avg_rating, 2)
                vehicle.total_bookings = reviews.count()
                vehicle.save()
        
        logger.info("Vehicle ratings updated successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to update vehicle ratings: {str(e)}")
        return False

@shared_task
def update_host_ratings():
    """Update host ratings based on their vehicle reviews"""
    try:
        hosts = Host.objects.all()
        for host in hosts:
            reviews = Review.objects.filter(host=host)
            if reviews.exists():
                avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
                host.rating = round(avg_rating, 2)
                host.total_bookings = reviews.count()
                host.save()
        
        logger.info("Host ratings updated successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to update host ratings: {str(e)}")
        return False

@shared_task
def cleanup_expired_otps():
    """Clean up expired OTPs (older than 10 minutes)"""
    try:
        # Clear OTPs for customers and hosts
        Customer.objects.filter(
            otp__isnull=False,
            updated_at__lt=timezone.now() - timezone.timedelta(minutes=10)
        ).update(otp='')
        
        Host.objects.filter(
            otp__isnull=False,
            updated_at__lt=timezone.now() - timezone.timedelta(minutes=10)
        ).update(otp='')
        
        logger.info("Expired OTPs cleaned up successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup expired OTPs: {str(e)}")
        return False

@shared_task
def send_reminder_email(email, message, subject="Wheely Reminder"):
    """Send reminder emails"""
    try:
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )
        logger.info(f"Reminder email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reminder email: {str(e)}")
        return False