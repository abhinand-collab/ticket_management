from django.db import models

class Ticket(models.Model):
    TICKET_TYPE_CHOICES = [('free', 'Free'), ('paid', 'Paid')]
    QUANTITY_TYPE_CHOICES = [('limited', 'Limited'), ('unlimited', 'Unlimited')]

    name = models.CharField(max_length=255)
    ticket_type = models.CharField(max_length=10, choices=TICKET_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity_type = models.CharField(max_length=20, choices=QUANTITY_TYPE_CHOICES)
    quantity = models.PositiveIntegerField(null=True, blank=True)  # only if limited
    max_per_order = models.PositiveIntegerField(default=50, help_text="Maximum tickets allowed per single purchase.")
    duplicate_email_check = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def available_slots(self):
        if self.quantity_type == 'unlimited':
            return None
            
        from apps.registrations.models import Registration
        used = Registration.objects.active(ticket=self).count()
        return max(0, self.quantity - used)

    def get_next_available_time(self):
        """
        Returns the number of minutes until the next pending registration expires.
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.conf import settings
        from apps.registrations.models import Registration
        
        if self.available_slots() > 0:
            return 0
            
        expiry_minutes = getattr(settings, 'PENDING_REGISTRATION_EXPIRY_MINUTES', 10)
        expiry_threshold = timezone.now() - timedelta(minutes=expiry_minutes)
        
        # Find the oldest non-expired pending registration
        oldest_pending = Registration.objects.filter(
            ticket=self,
            is_active=True, 
            status='pending',
            created_at__gte=expiry_threshold
        ).order_by('created_at').first()
        
        if oldest_pending:
            expire_time = oldest_pending.created_at + timedelta(minutes=expiry_minutes)
            remaining = expire_time - timezone.now()
            return max(1, int(remaining.total_seconds() / 60))
        
        return 0

    def is_available(self):
        if self.quantity_type == 'unlimited':
            return True
        slots = self.available_slots()
        return slots is None or slots > 0

    @classmethod
    def check_availability(cls, ticket_id, requested_qty):
        """
        Locks the ticket record and checks if the requested quantity is available.
        Must be called within a transaction.
        """
        from django.db import transaction
        ticket = cls.objects.select_for_update().get(id=ticket_id)
        if ticket.quantity_type == 'unlimited':
            return True, ticket
        
        available = ticket.available_slots()
        if available is not None and requested_qty > available:
            return False, ticket
        return True, ticket
