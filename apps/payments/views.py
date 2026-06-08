from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import PaymentTransaction

@login_required
def payment_list(request):
    payments = PaymentTransaction.objects.all().order_by('-created_at')
    return render(request, 'payments/list.html', {'payments': payments})
