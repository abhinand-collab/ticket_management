from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import Registration, RegistrationOrder

@shared_task
def cleanup_expired_registrations():
    """
    Task to mark expired pending registrations as 'abandoned'.
    """
    expiry_minutes = getattr(settings, 'PENDING_REGISTRATION_EXPIRY_MINUTES', 10)
    expiry_threshold = timezone.now() - timedelta(minutes=expiry_minutes)

    # Find expired pending registrations
    expired_registrations = Registration.objects.filter(
        status='pending',
        created_at__lt=expiry_threshold
    )
    
    count = expired_registrations.count()
    if count > 0:
        expired_registrations.update(status='abandoned')
        
        # Also handle orders that might be fully abandoned
        # (This is optional but good for cleanliness)
        expired_orders = RegistrationOrder.objects.filter(
            status='pending',
            created_at__lt=expiry_threshold,
            attendees__status='abandoned'
        ).distinct()
        expired_orders.update(status='failed')
        
    return f"Marked {count} registrations as abandoned."
