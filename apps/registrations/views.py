from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Registration, RegistrationOrder
from .serializers import RegistrationSerializer
from apps.tickets.models import Ticket
from apps.activity_logs.utils import log_action

@login_required
def order_list(request):
    order_list = RegistrationOrder.objects.select_related('buyer', 'transaction').all().order_by('-created_at')
    paginator = Paginator(order_list, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    return render(request, 'registrations/order_list.html', {'orders': orders})

@login_required
def registration_list(request):
    registration_list = Registration.objects.select_related('ticket', 'order__transaction').filter(is_active=True).order_by('-created_at')
    paginator = Paginator(registration_list, 10) # Show 10 registrations per page
    page_number = request.GET.get('page')
    registrations = paginator.get_page(page_number)
    return render(request, 'registrations/list.html', {'registrations': registrations})

@login_required
def registration_create(request):
    tickets = Ticket.objects.filter(is_active=True)
    if request.method == 'POST':
        # Admin manual registration - we might not need a full payment flow here
        # but we should still follow the serializer validation
        serializer = RegistrationSerializer(data=request.POST)
        if serializer.is_valid():
            # For admin, we create a simple order if it doesn't exist
            # or just a standalone registration if we want to allow it.
            # Let's create an order for consistency.
            ticket = serializer.validated_data['ticket']
            order = RegistrationOrder.objects.create(
                buyer=request.user,
                total_amount=ticket.price,
                payment_method='admin',
                status='completed' # Admin entry is usually considered pre-approved/paid
            )
            registration = serializer.save(order=order, status='completed')
            log_action(request.user, 'registration_create', registration, request)
            messages.success(request, 'Registration added successfully.')
            return redirect('registrations:list')
        else:
            return render(request, 'registrations/form.html', {
                'errors': serializer.errors,
                'form_data': request.POST,
                'tickets': tickets,
                'title': 'Add Registration'
            })
            
    return render(request, 'registrations/form.html', {
        'tickets': tickets,
        'title': 'Add Registration'
    })

@login_required
def registration_edit(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    tickets = Ticket.objects.filter(is_active=True)
    if request.method == 'POST':
        serializer = RegistrationSerializer(registration, data=request.POST)
        if serializer.is_valid():
            registration = serializer.save()
            log_action(request.user, 'registration_edit', registration, request)
            messages.success(request, 'Registration updated successfully.')
            return redirect('registrations:list')
        else:
            return render(request, 'registrations/form.html', {
                'errors': serializer.errors,
                'form_data': request.POST,
                'registration': registration,
                'tickets': tickets,
                'title': 'Edit Registration'
            })
            
    return render(request, 'registrations/form.html', {
        'registration': registration,
        'tickets': tickets,
        'title': 'Edit Registration'
    })

@login_required
def registration_delete(request, pk):
    registration = get_object_or_404(Registration, pk=pk)
    if request.method == 'POST':
        reg_name = registration.name
        registration.is_active = False
        registration.save()
        log_action(request.user, 'registration_delete', registration, request)
        messages.success(request, f'Registration for "{reg_name}" deleted successfully.')
        return redirect('registrations:list')
    return render(request, 'registrations/delete_confirm.html', {'registration': registration})
