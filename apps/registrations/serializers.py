from django.db import transaction
from rest_framework import serializers
from .models import Registration,RegistrationOrder
from apps.tickets.models import Ticket
import re

class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['ticket', 'name', 'email', 'phone', 'status']

    def validate_phone(self, value):
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
        fields = ['ticket', 'name', 'email', 'phone']

    def validate_phone(self, value):
        cleaned = re.sub(r'[\s\-\+]', '', value)
        if not re.match(r'^[6-9]\d{9}$', cleaned):
            raise serializers.ValidationError('Enter a valid 10-digit Indian phone number.')
        return cleaned

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
        
        total_amount = sum(item['ticket'].price for item in attendees_data)
        
        order = RegistrationOrder.objects.create(
            buyer=buyer,
            total_amount=total_amount,
            payment_method='razorpay' if total_amount > 0 else 'free',
            status='pending'
        )

        for attendee_data in attendees_data:
            Registration.objects.create(
                order=order,
                **attendee_data,
                status='pending'
            )
        
        return order
