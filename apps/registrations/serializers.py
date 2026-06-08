from rest_framework import serializers
from .models import Registration
from apps.tickets.models import Ticket
import re

class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['ticket', 'name', 'email', 'phone']

    def validate_phone(self, value):
        # Strip spaces/dashes, check 10-digit Indian number
        cleaned = re.sub(r'[\s\-\+]', '', value)
        if not re.match(r'^[6-9]\d{9}$', cleaned):
            raise serializers.ValidationError('Enter a valid 10-digit Indian phone number.')
        return cleaned

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, data):
        ticket = data.get('ticket')
        email = data.get('email')

        # Check ticket availability
        if not ticket.is_available():
            raise serializers.ValidationError(
                {'ticket': 'This ticket is sold out.'}
            )

        # Duplicate email check (per ticket config)
        if ticket.duplicate_email_check:
            exists = Registration.objects.filter(
                ticket=ticket,
                email=email,
                status__in=['pending', 'completed']
            ).exists()
            if exists:
                raise serializers.ValidationError(
                    {'email': 'This email is already registered for this ticket.'}
                )

        return data
