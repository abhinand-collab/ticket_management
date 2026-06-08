from rest_framework import serializers
from .models import Ticket

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = '__all__'

    def validate(self, data):
        ticket_type = data.get('ticket_type')
        price = data.get('price')
        quantity_type = data.get('quantity_type')
        quantity = data.get('quantity')

        # Price must be > 0 for paid tickets
        if ticket_type == 'paid':
            if not price or price <= 0:
                raise serializers.ValidationError(
                    {'price': 'Price is required and must be greater than 0 for paid tickets.'}
                )
        else:
            data['price'] = 0.00  # Force free tickets to 0

        # Quantity required if limited
        if quantity_type == 'limited':
            if not quantity or quantity <= 0:
                raise serializers.ValidationError(
                    {'quantity': 'Quantity is required for limited tickets.'}
                )
        else:
            data['quantity'] = None  # Clear quantity for unlimited

        return data
