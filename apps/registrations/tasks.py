from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from .models import Registration, RegistrationOrder
from apps.activity_logs.utils import log_action

@shared_task
def cleanup_expired_registrations():
    """
    Task to mark expired pending registrations as 'abandoned'.
    Runs via Celery Beat every minute.
    """
    expiry_minutes = getattr(settings, 'PENDING_REGISTRATION_EXPIRY_MINUTES', 10)
    expiry_threshold = timezone.now() - timedelta(minutes=expiry_minutes)

    with transaction.atomic():
        # 1. Find and update expired registrations
        expired_registrations = Registration.objects.filter(
            status='pending',
            created_at__lt=expiry_threshold
        )
        
        reg_count = expired_registrations.count()
        if reg_count > 0:
            # Use select_for_update to avoid races with incoming payments
            # But update() doesn't support select_for_update directly on all DBs 
            # and might be overkill for a cleanup task.
            # We'll just perform the update.
            expired_registrations.update(status='abandoned')
            
            # 2. Update parent orders if they are now fully abandoned/expired
            # We look for pending orders that are older than threshold
            expired_orders = RegistrationOrder.objects.filter(
                status='pending',
                created_at__lt=expiry_threshold
            )
            
            order_count = expired_orders.count()
            if order_count > 0:
                expired_orders.update(status='failed')
            
            # 3. Log the system activity
            # We use user=None for system-automated tasks
            log_action(
                user=None, 
                action='registration_cleanup', 
                description=f"Auto-cleanup: Marked {reg_count} registrations as abandoned and {order_count} orders as failed (Threshold: {expiry_minutes}m)."
            )
            
            return f"Cleanup complete: {reg_count} registrations abandoned, {order_count} orders failed."

    return "No expired registrations found."
