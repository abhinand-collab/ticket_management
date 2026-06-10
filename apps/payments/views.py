from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import razorpay
from .models import PaymentTransaction
from apps.registrations.models import RegistrationOrder
from apps.activity_logs.utils import log_action

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
def payment_list(request):
    payment_list = PaymentTransaction.objects.all().order_by('-created_at')
    paginator = Paginator(payment_list, 10) # Show 10 payments per page
    page_number = request.GET.get('page')
    payments = paginator.get_page(page_number)
    return render(request, 'payments/list.html', {'payments': payments})

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

@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')
        
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        try:
            # Verify signature
            client.utility.verify_payment_signature(params_dict)
            
            transaction = PaymentTransaction.objects.get(razorpay_order_id=razorpay_order_id)
            transaction.status = 'paid'
            transaction.razorpay_payment_id = payment_id
            transaction.razorpay_signature = signature
            transaction.save()
            
            order = transaction.order
            order.status = 'completed'
            order.save()
            
            # Update all attendees in this order
            order.attendees.all().update(status='completed')
            
            # Log the registration completion
            log_action(order.buyer, 'registration_create', order, request)
            
            return redirect('public:order_success', order_id=order.id)
        except Exception as e:
            # Handle failure
            if razorpay_order_id:
                transaction = PaymentTransaction.objects.filter(razorpay_order_id=razorpay_order_id).first()
                if transaction:
                    transaction.status = 'failed'
                    transaction.save()
            return render(request, 'payments/payment_failed.html', {'error': str(e)})
            
    return redirect('public:ticket_list')
