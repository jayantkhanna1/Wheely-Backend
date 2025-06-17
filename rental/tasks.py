from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models
from .models import User, Vehicle, Review
import random
import string
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_otp_email(email, otp):
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
def generate_and_send_otp(user_id, user_type='user'):
    """Generate OTP and send to user"""
    try:
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Get user (unified User model)
        user = User.objects.get(id=user_id)
        
        # Save OTP to user
        user.otp = otp
        user.save()
        
        # Send OTP email
        send_otp_email.delay(user.email, otp)
        
        logger.info(f"OTP generated and sent for user ID: {user_id}")
        return True
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False
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
                vehicle.rating = round(avg_rating, 2) if avg_rating else 0.0
                vehicle.total_bookings = reviews.count()
                vehicle.save()
        
        logger.info("Vehicle ratings updated successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to update vehicle ratings: {str(e)}")
        return False

@shared_task
def update_user_ratings():
    """Update user ratings based on their vehicle reviews (for hosts)"""
    try:
        # Get all users who own vehicles (hosts)
        hosts = User.objects.filter(vehicles__isnull=False).distinct()
        
        for host in hosts:
            # Get all reviews for vehicles owned by this host
            reviews = Review.objects.filter(vehicle__owner=host)
            if reviews.exists():
                avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
                # Note: You might need to add a rating field to User model for hosts
                # or handle this differently based on your User model structure
                logger.info(f"Host {host.id} average rating: {avg_rating}")
        
        logger.info("User ratings updated successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to update user ratings: {str(e)}")
        return False

@shared_task
def cleanup_expired_otps():
    """Clean up expired OTPs (older than 10 minutes)"""
    try:
        # Clear OTPs for users (unified model)
        expired_time = timezone.now() - timezone.timedelta(minutes=10)
        
        updated_count = User.objects.filter(
            otp__isnull=False,
            updated_at__lt=expired_time
        ).update(otp='')
        
        logger.info(f"Expired OTPs cleaned up successfully. {updated_count} OTPs cleared.")
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

@shared_task
def send_vehicle_verification_notification(user_id, vehicle_id, is_verified):
    """Send notification to vehicle owner about verification status"""
    try:
        user = User.objects.get(id=user_id)
        vehicle = Vehicle.objects.get(id=vehicle_id)
        
        status = "approved" if is_verified else "rejected"
        subject = f'Wheely - Vehicle Verification {status.title()}'
        
        message = f'''
        Hi {user.first_name},
        
        Your vehicle "{vehicle.vehicle_name}" has been {status} for listing on Wheely.
        
        {"You can now start receiving bookings!" if is_verified else "Please check your vehicle documents and resubmit."}
        
        Best regards,
        Wheely Team
        '''
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Vehicle verification notification sent to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send vehicle verification notification: {str(e)}")
        return False

@shared_task
def send_review_notification(host_user_id, vehicle_name, rating, comment):
    """Send notification to host when they receive a new review"""
    try:
        host = User.objects.get(id=host_user_id)
        
        subject = f'Wheely - New Review for {vehicle_name}'
        message = f'''
        Hi {host.first_name},
        
        You have received a new review for your vehicle "{vehicle_name}":
        
        Rating: {rating}/5 stars
        Comment: {comment}
        
        Keep up the great work!
        
        Best regards,
        Wheely Team
        '''
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [host.email],
            fail_silently=False,
        )
        
        logger.info(f"Review notification sent to host {host_user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send review notification: {str(e)}")
        return False
    
@shared_task
def verify_vehicle(vehicle_id):
    """Verify vehicle documents and update status"""
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
        
        # Placeholder for actual verification logic
        # For example, checking if all required documents are uploaded and valid
        
        if vehicle.vehicle_rc and vehicle.vehicle_insurance and vehicle.vehicle_pollution_certificate:
            # vehicle.is_verified = True # paused temporarily for testing
            print("Vehicle verification is paused temporarily for testing.")
            vehicle.save()
        else:
            vehicle.is_verified = False
            vehicle.save()
        return True
    except Vehicle.DoesNotExist:
        logger.error(f"Vehicle with ID {vehicle_id} not found")
        return False
    except Exception as e:
        logger.error(f"Failed to verify vehicle: {str(e)}")
        return False