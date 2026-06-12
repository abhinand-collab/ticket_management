from rest_framework import serializers
from decimal import Decimal
from .models import Ticket

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = '__all__'

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Ticket name is required.")
        
        # 1. Strip whitespace
        name = value.strip()
        
        # 2. Check length (min 2, max 100)
        if len(name) < 2:
            raise serializers.ValidationError("Ticket name must be at least 2 characters long.")
        if len(name) > 100:
            raise serializers.ValidationError("Ticket name cannot exceed 100 characters.")
            
        # 3. Check for disallowed special characters (only letters, numbers, spaces, hyphens, underscores, parentheses, brackets, and colons)
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_()[\]:]+$', name):
            raise serializers.ValidationError("Ticket name contains invalid characters. Only letters, numbers, spaces, and basic punctuation (- _ ( ) [ ] :) are allowed.")
            
        # 4. Check uniqueness among active tickets
        instance = getattr(self, 'instance', None)
        queryset = Ticket.objects.filter(name__iexact=name, is_active=True)
        if instance:
            queryset = queryset.exclude(pk=instance.pk)
            
        if queryset.exists():
            raise serializers.ValidationError("A ticket with this name already exists.")
            
        return name

    def validate(self, data):
        ticket_type = data.get('ticket_type')
        price = data.get('price')
        quantity_type = data.get('quantity_type')
        quantity = data.get('quantity')
        max_per_order = data.get('max_per_order')

        # Max Per Order validation
        if max_per_order is not None and max_per_order < 1:
            raise serializers.ValidationError(
                {'max_per_order': 'Maximum tickets per order must be at least 1.'}
            )

        # Price must be > 0 for paid tickets
        if ticket_type == 'paid':
            if not price or price <= 0:
                raise serializers.ValidationError(
                    {'price': 'Price is required and must be greater than 0 for paid tickets.'}
                )
        else:
            data['price'] = Decimal('0.00')  # Force free tickets to 0

        # Quantity required if limited
        if quantity_type == 'limited':
            if not quantity or quantity <= 0:
                raise serializers.ValidationError(
                    {'quantity': 'Quantity is required for limited tickets.'}
                )
        else:
            data['quantity'] = None  # Clear quantity for unlimited

        return data
