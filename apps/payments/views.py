from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.db import transaction as db_transaction
import razorpay
from .models import PaymentTransaction
from apps.registrations.models import RegistrationOrder
from apps.activity_logs.utils import log_action

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

from django.db.models import Q, Sum

@staff_member_required
def payment_list(request):
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    query = PaymentTransaction.objects.select_related('order__buyer').all()
    
    if search:
        query = query.filter(
            Q(razorpay_order_id__icontains=search) |
            Q(razorpay_payment_id__icontains=search) |
            Q(order__buyer__username__icontains=search) |
            Q(order__attendees__first_name__icontains=search) |
            Q(order__attendees__last_name__icontains=search)
        ).distinct()

    if status_filter != 'all':
        query = query.filter(status=status_filter)
        
    payment_list = query.order_by('-created_at')
    
    # Financial Summary for the admin
    total_paid = PaymentTransaction.objects.filter(status='paid').aggregate(Sum('amount'))['amount__sum'] or 0
    
    paginator = Paginator(payment_list, 10)
    page_number = request.GET.get('page')
    payments = paginator.get_page(page_number)
    
    return render(request, 'payments/list.html', {
        'payments': payments,
        'total_paid': total_paid,
        'filters': {
            'search': search,
            'status': status_filter
        }
    })

def checkout(request, order_id):
    order = get_object_or_404(RegistrationOrder, id=order_id, status='pending')
    
    # Create Razorpay Order
    razorpay_order = client.order.create({
        "amount": int(order.total_amount * 100), # amount in paise
        "currency": "INR",
        "payment_capture": "1"
    })
    
    # Save Transaction
    transaction, created = PaymentTransaction.objects.update_or_create(
        order=order,
        defaults={
            'razorpay_order_id': razorpay_order['id'],
            'amount': order.total_amount,
            'status': 'created'
        }
    )

    context = {
        'order': order,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount': razorpay_order['amount'],
        'currency': razorpay_order['currency'],
        'callback_url': request.build_absolute_uri(reverse('payments:verify')),
    }
    return render(request, 'payments/checkout.html', context)

import json

@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')

        # Handle Razorpay's nested error format for failures
        error_code = request.POST.get('error[code]')
        if error_code:
            error_desc = request.POST.get('error[description]', 'Payment Failed')
            metadata_str = request.POST.get('error[metadata]', '{}')
            try:
                metadata = json.loads(metadata_str)
                razorpay_order_id = metadata.get('order_id', razorpay_order_id)
            except:
                pass

            if razorpay_order_id:
                PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id).update(status='failed')

            return render(request, 'payments/payment_failed.html', {'error': error_desc})

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        try:
            # Check if this is a failure POST from our custom JS handler
            error_description = request.POST.get('error_description')
            if error_description:
                if razorpay_order_id:
                    PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id).update(status='failed')
                return render(request, 'payments/payment_failed.html', {'error': error_description})

            # Normal success path: Verify signature
            client.utility.verify_payment_signature(params_dict)

            with db_transaction.atomic():
                # Use select_for_update to lock the transaction record
                transaction = PaymentTransaction.objects.select_for_update().get(razorpay_order_id=razorpay_order_id)
                
                # If already paid, just redirect (prevents double processing)
                if transaction.status == 'paid':
                    return redirect('public:order_success', order_uuid=transaction.order.uuid)
                
                transaction.status = 'paid'
                transaction.razorpay_payment_id = payment_id
                transaction.razorpay_signature = signature
                transaction.save()
                
                # Use select_for_update to lock the order record
                order = RegistrationOrder.objects.select_for_update().get(id=transaction.order.id)
                order.status = 'completed'
                order.save()
                
                # Update all attendees in this order
                order.attendees.all().update(status='completed')
                
                # Security: Whitelist this order ID in the session for the success page
                request.session['last_order_id'] = order.id

                # Log the registration completion
                log_action(order.buyer, 'registration_create', order, request)
            
            return redirect('public:order_success', order_uuid=order.uuid)
        except Exception as e:
            # Handle failure
            if razorpay_order_id:
                transaction = PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id).first()
                if transaction:
                    transaction.status = 'failed'
                    transaction.save()
            return render(request, 'payments/payment_failed.html', {'error': str(e)})
            
    return redirect('public:ticket_list')
