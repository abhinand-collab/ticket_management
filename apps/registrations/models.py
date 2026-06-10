from django.db import models
from django.contrib.auth.models import User
from apps.tickets.models import Ticket

class RegistrationOrder(models.Model):
    """
    Groups multiple registrations into a single order/payment.
    Linked to the Buyer (User).
    """
    PAYMENT_METHOD_CHOICES = [
        ('razorpay', 'Razorpay'),
        ('free', 'Free Registration'),
        ('admin', 'Manual Admin Entry'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='free')
    status = models.CharField(max_length=20, default='pending') # pending, completed, failed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - Buyer: {self.buyer.username if self.buyer else 'Guest'}"

class Registration(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),
    ]

    order = models.ForeignKey(RegistrationOrder, on_delete=models.CASCADE, related_name='attendees', null=True, blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='registrations')
    
    # Attendee Details
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ticket', 'email']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        order_id = self.order.id if self.order else "N/A"
        return f"{self.name} - Ticket: {self.ticket.name} (Order #{order_id})"
