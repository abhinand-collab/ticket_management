from django.db import transaction
from rest_framework import serializers
from .models import Registration,RegistrationOrder
from apps.tickets.models import Ticket
import re

import phonenumbers

class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['ticket', 'first_name', 'last_name', 'email', 'phone', 'status']

    def validate_first_name(self, value):
        if not re.match(r"^[a-zA-Z\s\-']+$", value):
            raise serializers.ValidationError("First name should only contain letters, spaces, and hyphens.")
        return value

    def validate_last_name(self, value):
        if not re.match(r"^[a-zA-Z\s\-']+$", value):
            raise serializers.ValidationError("Last name should only contain letters, spaces, and hyphens.")
        return value

    def validate_phone(self, value):
        try:
            # Parse the number (expected in E.164 format like +919876543210)
            parsed_number = phonenumbers.parse(value, None)
            if not phonenumbers.is_valid_number(parsed_number):
                raise serializers.ValidationError('Enter a valid phone number for your country.')
            # Normalize to E.164 format
            return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            raise serializers.ValidationError('Invalid phone number format.')

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, data):
        ticket = data.get('ticket')
        email = data.get('email')
        
        # Check ticket availability
        if ticket and not ticket.is_available():
            # If editing existing, we should account for its own slot
            if not self.instance or self.instance.ticket != ticket:
                raise serializers.ValidationError({'ticket': 'This ticket is sold out.'})

        # Cross-ticket Duplicate Email Logic:
        # 1. If CURRENT ticket is strict, block if email exists ANYWHERE
        if ticket and ticket.duplicate_email_check:
            exists_query = Registration.objects.filter(
                email=email,
                is_active=True,
                status__in=['pending', 'completed']
            )
            if self.instance:
                exists_query = exists_query.exclude(pk=self.instance.pk)
            
            if exists_query.exists():
                raise serializers.ValidationError({'email': 'This email is already registered for a ticket.'})
        
        # 2. If CURRENT ticket is flexible, block if email exists for a STRICT ticket
        elif ticket:
            exists_query = Registration.objects.filter(
                email=email,
                ticket__duplicate_email_check=True,
                is_active=True,
                status__in=['pending', 'completed']
            )
            if self.instance:
                exists_query = exists_query.exclude(pk=self.instance.pk)
                
            if exists_query.exists():
                raise serializers.ValidationError({'email': 'This email is already used for a restricted ticket type.'})

        return data

class PublicRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['ticket', 'first_name', 'last_name', 'email', 'phone']

    def validate_first_name(self, value):
        if not re.match(r"^[a-zA-Z\s\-']+$", value):
            raise serializers.ValidationError("First name should only contain letters, spaces, and hyphens.")
        return value

    def validate_last_name(self, value):
        if not re.match(r"^[a-zA-Z\s\-']+$", value):
            raise serializers.ValidationError("Last name should only contain letters, spaces, and hyphens.")
        return value

    def validate_phone(self, value):
        try:
            parsed_number = phonenumbers.parse(value, None)
            if not phonenumbers.is_valid_number(parsed_number):
                raise serializers.ValidationError('Enter a valid phone number for your country.')
            return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            raise serializers.ValidationError('Invalid phone number format.')

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, data):
        ticket = data.get('ticket')
        email = data.get('email')

        # Check database for cross-ticket conflicts
        # 1. Strict tickets block any prior registration of this email
        if ticket and ticket.duplicate_email_check:
            exists = Registration.objects.filter(
                email=email,
                is_active=True,
                status__in=['pending', 'completed']
            ).exists()
            if exists:
                raise serializers.ValidationError({'email': 'This email is already registered for a ticket.'})
        
        # 2. Flexible tickets block if email was previously used for a STRICT ticket
        elif ticket:
            exists = Registration.objects.filter(
                email=email,
                ticket__duplicate_email_check=True,
                is_active=True,
                status__in=['pending', 'completed']
            ).exists()
            if exists:
                raise serializers.ValidationError({'email': 'This email is already used for a restricted ticket type.'})
                
        return data

class PublicRegistrationOrderSerializer(serializers.Serializer):
    attendees = PublicRegistrationSerializer(many=True)

    def validate_attendees(self, value):
        if not value:
            raise serializers.ValidationError("At least one attendee is required.")
        
        ticket_counts = {}
        # Track emails in current order
        strict_emails = set() # Emails used for tickets with duplicate_email_check=True
        all_emails_in_order = {} # Email -> set of ticket IDs used for this email in this order

        errors = []
        any_error = False

        for index, attendee in enumerate(value):
            attendee_errors = {}
            ticket = attendee['ticket']
            email = attendee['email']

            # 1. Check availability
            ticket_counts[ticket.id] = ticket_counts.get(ticket.id, 0) + 1
            available = ticket.available_slots()
            if available is not None and ticket_counts[ticket.id] > available:
                attendee_errors['ticket'] = [f"Not enough slots available for {ticket.name}."]
                any_error = True

            # 2. Intra-order Cross-ticket Duplicate Logic
            if ticket:
                if ticket.duplicate_email_check:
                    # If current is strict, it cannot be a duplicate of ANY attendee processed so far
                    if email in all_emails_in_order:
                        attendee_errors['email'] = ["This email is already used by another attendee in this order."]
                        any_error = True
                    else:
                        strict_emails.add(email)
                else:
                    # If current is flexible, it only blocks if a STRICT ticket already used this email
                    if email in strict_emails:
                        attendee_errors['email'] = ["This email is already used for a restricted ticket in this order."]
                        any_error = True
                
                # Track for future attendees in the loop
                if email not in all_emails_in_order:
                    all_emails_in_order[email] = set()
                all_emails_in_order[email].add(ticket.id)

            errors.append(attendee_errors)

        if any_error:
            raise serializers.ValidationError(errors)

        return value

    @transaction.atomic
    def create(self, validated_data):
        attendees_data = validated_data.pop('attendees')
        user = self.context.get('user')
        buyer = user if user and user.is_authenticated else None
        
        # Group requested quantities per ticket
        ticket_qtys = {}
        for attendee in attendees_data:
            t_id = attendee['ticket'].id
            ticket_qtys[t_id] = ticket_qtys.get(t_id, 0) + 1
        
        # Perform final availability check with locking (Sorted by ID to prevent deadlocks)
        for t_id in sorted(ticket_qtys.keys()):
            qty = ticket_qtys[t_id]
            is_available, ticket = Ticket.check_availability(t_id, qty)
            if not is_available:
                raise serializers.ValidationError(
                    f"Sorry, {ticket.name} just sold out or doesn't have enough slots."
                )

        total_amount = sum(item['ticket'].price for item in attendees_data)
        is_free = (total_amount == 0)
        status = 'completed' if is_free else 'pending'
        
        order = RegistrationOrder.objects.create(
            buyer=buyer,
            total_amount=total_amount,
            payment_method='razorpay' if total_amount > 0 else 'free',
            status=status
        )

        for attendee_data in attendees_data:
            Registration.objects.create(
                order=order,
                **attendee_data,
                status=status
            )
        
        return order
