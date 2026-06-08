i want to create a event registration system with admin dashboard. first a login page for admin with proper validation. then there is two sections ticket listing and registration listing. admin can add,edit,delete ticket .there is a toggle field of validate duplicate email checkbox.the registration page also like all crud operations.all admin activities like edit,add ,delete should see the logs. also want to see payment transactions
i will give you the documentation for clear understanding.
analyse the documentation and i want to do it like a real project like all the real proper validation. validation should be consistent and all should be in backend and do serializers also.


Event Registration System — Full Implementation Plan
Project Structure
event_registration/
├── manage.py
├── config/                  # Project settings
│   ├── settings.py
│   ├── urls.py
├── apps/
│   ├── accounts/            # Admin auth
│   ├── tickets/             # Ticket management
│   ├── registrations/       # Registration management
│   ├── payments/            # Razorpay integration
│   └── activity_logs/       # Admin audit logs
├── templates/
│   ├── base.html
│   ├── accounts/
│   ├── tickets/
│   ├── registrations/
│   └── public/              # Public registration portal
└── static/

Phase 1 — Models
accounts app
python# No custom model needed — use Django's built-in User
# But log the login activity via signals
tickets app — models.py
pythonclass Ticket(models.Model):
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

    def available_slots(self):
        if self.quantity_type == 'unlimited':
            return None
        used = self.registrations.filter(status__in=['completed', 'pending']).count()
        return max(0, self.quantity - used)

    def is_available(self):
        if self.quantity_type == 'unlimited':
            return True
        return self.available_slots() > 0
registrations app — models.py
pythonclass Registration(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('abandoned', 'Abandoned'),  # incomplete/missed
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT,
                               related_name='registrations')
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ticket', 'email']),
            models.Index(fields=['status']),
        ]
payments app — models.py
pythonclass PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    registration = models.OneToOneField(Registration, on_delete=models.CASCADE,
                                        related_name='transaction')
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
activity_logs app — models.py
pythonclass ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('ticket_create', 'Ticket Created'),
        ('ticket_edit', 'Ticket Edited'),
        ('ticket_delete', 'Ticket Deleted'),
        ('registration_create', 'Registration Created'),
        ('registration_edit', 'Registration Edited'),
        ('registration_delete', 'Registration Deleted'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=50, blank=True)  # 'Ticket', 'Registration'
    object_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

Phase 2 — Serializers (DRF-style, for validation reuse)
Even in a Django HTML project, you write serializers in each app's serializers.py and call them in views — this keeps all validation in one place, backend-only, no duplication.
tickets/serializers.py
pythonfrom rest_framework import serializers
from .models import Ticket

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = '__all__'

    def validate(self, data):
        # Price must be > 0 for paid tickets
        if data.get('ticket_type') == 'paid':
            if not data.get('price') or data['price'] <= 0:
                raise serializers.ValidationError(
                    {'price': 'Price is required and must be greater than 0 for paid tickets.'}
                )
        else:
            data['price'] = 0.00  # Force free tickets to 0

        # Quantity required if limited
        if data.get('quantity_type') == 'limited':
            if not data.get('quantity') or data['quantity'] <= 0:
                raise serializers.ValidationError(
                    {'quantity': 'Quantity is required for limited tickets.'}
                )
        else:
            data['quantity'] = None  # Clear quantity for unlimited

        return data
registrations/serializers.py
pythonfrom rest_framework import serializers
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

Phase 3 — Views Architecture
Key principle: Serializer validates, View acts
python# tickets/views.py (admin)
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from .serializers import TicketSerializer
from apps.activity_logs.utils import log_action

@staff_member_required
def ticket_create(request):
    if request.method == 'POST':
        serializer = TicketSerializer(data=request.POST)
        if serializer.is_valid():
            ticket = serializer.save()
            log_action(request.user, 'ticket_create', ticket, request)
            messages.success(request, 'Ticket created successfully.')
            return redirect('tickets:list')
        # Pass errors back to template
        return render(request, 'tickets/form.html', {
            'errors': serializer.errors,
            'form_data': request.POST,
        })
    return render(request, 'tickets/form.html')
Error display in templates (consistent pattern)
html<!-- base error display — reuse this across all forms -->
{% if errors %}
  {% for field, error_list in errors.items %}
    <div class="alert alert-danger">{{ field }}: {{ error_list|join:", " }}</div>
  {% endfor %}
{% endif %}

Phase 4 — Activity Log Utility
python# activity_logs/utils.py
from .models import ActivityLog

def log_action(user, action, obj=None, request=None):
    ip = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

    ActivityLog.objects.create(
        user=user,
        action=action,
        object_type=obj.__class__.__name__ if obj else '',
        object_id=obj.pk if obj else None,
        description=f"{action.replace('_', ' ').title()}: {str(obj)}",
        ip_address=ip,
    )
Use Django signals for login/logout:
python# accounts/signals.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from apps.activity_logs.utils import log_action

def on_login(sender, request, user, **kwargs):
    log_action(user, 'login', request=request)

def on_logout(sender, request, user, **kwargs):
    log_action(user, 'logout', request=request)

user_logged_in.connect(on_login)
user_logged_out.connect(on_logout)

Phase 5 — Payment Flow (Razorpay)
User submits registration form
        ↓
RegistrationSerializer.validate()
        ↓
Registration saved with status='pending'
        ↓
If ticket is paid:
    Create Razorpay order via API
    Save PaymentTransaction(status='created')
    Redirect to payment page with order_id
        ↓
User pays on Razorpay checkout
        ↓
POST /payment/verify/  (Razorpay webhook/callback)
    Verify HMAC signature
    Update PaymentTransaction(status='paid')
    Update Registration(status='completed')
    log_action(...)
    Redirect to confirmation page
        ↓
If ticket is free:
    Registration(status='completed') immediately
    Redirect to confirmation page
Signature Verification (critical for security)
pythonimport hmac, hashlib

def verify_razorpay_signature(order_id, payment_id, signature, secret):
    message = f"{order_id}|{payment_id}"
    generated = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(generated, signature)

Phase 6 — URL Structure
python# config/urls.py
urlpatterns = [
    path('admin-panel/login/',  ..., name='login'),
    path('admin-panel/dashboard/', ..., name='dashboard'),

    # Tickets
    path('admin-panel/tickets/', include('apps.tickets.urls')),
    # tickets/list, tickets/create, tickets/<id>/edit, tickets/<id>/delete

    # Registrations
    path('admin-panel/registrations/', include('apps.registrations.urls')),

    # Logs
    path('admin-panel/logs/', include('apps.activity_logs.urls')),

    # Public portal
    path('register/', include('apps.public.urls')),

    # Payment
    path('payment/', include('apps.payments.urls')),
]