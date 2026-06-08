from django.db import models

class Ticket(models.Model):
    TICKET_TYPE_CHOICES = [('free', 'Free'), ('paid', 'Paid')]
    QUANTITY_TYPE_CHOICES = [('limited', 'Limited'), ('unlimited', 'Unlimited')]

    name = models.CharField(max_length=255)
    ticket_type = models.CharField(max_length=10, choices=TICKET_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity_type = models.CharField(max_length=20, choices=QUANTITY_TYPE_CHOICES)
    quantity = models.PositiveIntegerField(null=True, blank=True)  # only if limited
    duplicate_email_check = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def available_slots(self):
        if self.quantity_type == 'unlimited':
            return None
        used = self.registrations.filter(status__in=['completed', 'pending']).count()
        return max(0, self.quantity - used)

    def is_available(self):
        if self.quantity_type == 'unlimited':
            return True
        slots = self.available_slots()
        return slots is None or slots > 0
