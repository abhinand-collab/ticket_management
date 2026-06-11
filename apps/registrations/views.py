from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from .models import Registration, RegistrationOrder
from .serializers import RegistrationSerializer
from apps.tickets.models import Ticket
from apps.activity_logs.utils import log_action

@login_required
def order_list(request):
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    payment_method = request.GET.get('payment_method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    query = RegistrationOrder.objects.select_related('buyer', 'transaction').prefetch_related('attendees').all()

    if search:
        query = query.filter(
            Q(id__icontains=search) |
            Q(buyer__username__icontains=search) |
            Q(buyer__email__icontains=search) |
            Q(attendees__first_name__icontains=search) |
            Q(attendees__last_name__icontains=search) |
            Q(attendees__email__icontains=search) |
            Q(transaction__razorpay_order_id__icontains=search) |
            Q(transaction__razorpay_payment_id__icontains=search)
        ).distinct()

    if status_filter:
        query = query.filter(status=status_filter)

    if payment_method:
        query = query.filter(payment_method=payment_method)

    if date_from:
        query = query.filter(created_at__date__gte=date_from)
    if date_to:
        query = query.filter(created_at__date__lte=date_to)

    order_queryset = query.order_by('-created_at')
    
    paginator = Paginator(order_queryset, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    
    return render(request, 'registrations/order_list.html', {
        'orders': orders,
        'payment_methods': RegistrationOrder.PAYMENT_METHOD_CHOICES,
        'filters': {
            'search': search,
            'status': status_filter,
            'payment_method': payment_method,
            'date_from': date_from,
            'date_to': date_to,
        }
    })

@login_required
def registration_list(request):
    # Get filter parameters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    ticket_id = request.GET.get('ticket', '')
    payment_method = request.GET.get('payment_method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    query = Registration.objects.select_related('ticket', 'order__transaction').filter(is_active=True)
    
    # Text Search (Name, Email, Phone, Order ID)
    if search:
        query = query.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(order__transaction__razorpay_order_id__icontains=search) |
            Q(order__transaction__razorpay_payment_id__icontains=search)
        )

    # Status Filter
    if status_filter == 'completed':
        query = query.filter(status='completed')
    elif status_filter == 'pending':
        query = query.filter(status='pending')
    elif status_filter == 'failed':
        query = query.filter(status='failed')
    elif status_filter == 'abandoned':
        query = query.filter(status='abandoned')
    elif status_filter == 'incomplete':
        query = query.filter(status__in=['pending', 'failed', 'abandoned'])
    
    # Ticket Filter
    if ticket_id:
        query = query.filter(ticket_id=ticket_id)
        
    # Payment Method Filter
    if payment_method:
        query = query.filter(order__payment_method=payment_method)
        
    # Date Range Filter
    if date_from:
        query = query.filter(created_at__date__gte=date_from)
    if date_to:
        query = query.filter(created_at__date__lte=date_to)
        
    registration_list = query.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(registration_list, 10)
    page_number = request.GET.get('page')
    registrations = paginator.get_page(page_number)
    
    # Context data for filters
    tickets = Ticket.objects.all()
    payment_methods = RegistrationOrder.PAYMENT_METHOD_CHOICES
    
    return render(request, 'registrations/list.html', {
        'registrations': registrations,
        'tickets': tickets,
        'payment_methods': payment_methods,
        'filters': {
            'search': search,
            'status': status_filter,
            'ticket': ticket_id,
            'payment_method': payment_method,
            'date_from': date_from,
            'date_to': date_to,
        }
    })

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
            
            from django.db import transaction
            try:
                with transaction.atomic():
                    # Check availability with lock for admin too
                    is_available, ticket_obj = Ticket.check_availability(ticket.id, 1)
                    if not is_available:
                        messages.error(request, f"Sorry, {ticket_obj.name} is sold out.")
                        return render(request, 'registrations/form.html', {
                            'tickets': tickets,
                            'form_data': request.POST,
                            'title': 'Add Registration'
                        })

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
            except Exception as e:
                messages.error(request, f"Error creating registration: {str(e)}")
                return render(request, 'registrations/form.html', {
                    'tickets': tickets,
                    'form_data': request.POST,
                    'title': 'Add Registration'
                })
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
    
    # Store old values for logging (explicitly as strings to avoid reference issues)
    old_data = {
        'ticket': str(registration.ticket.name),
        'first_name': str(registration.first_name),
        'last_name': str(registration.last_name),
        'email': str(registration.email),
        'phone': str(registration.phone),
        'status': str(registration.status)
    }

    if request.method == 'POST':
        serializer = RegistrationSerializer(registration, data=request.POST)
        if serializer.is_valid():
            from django.db import transaction
            try:
                with transaction.atomic():
                    # Check availability if:
                    # 1. Ticket is changed
                    # 2. Status is changed from non-consuming to consuming (completed/pending)
                    new_ticket = serializer.validated_data.get('ticket')
                    new_status = serializer.validated_data.get('status')
                    
                    consuming_statuses = ['completed', 'pending']
                    was_consuming = registration.status in consuming_statuses
                    will_be_consuming = new_status in consuming_statuses
                    
                    ticket_changed = new_ticket and new_ticket != registration.ticket
                    consumption_increased = not was_consuming and will_be_consuming
                    
                    if ticket_changed or consumption_increased:
                        # Use new ticket if changed, else current
                        target_ticket = new_ticket if ticket_changed else registration.ticket
                        is_available, ticket_obj = Ticket.check_availability(target_ticket.id, 1)
                        if not is_available:
                            messages.error(request, f"Sorry, {ticket_obj.name} is sold out.")
                            return render(request, 'registrations/form.html', {
                                'tickets': tickets,
                                'registration': registration,
                                'form_data': request.POST,
                                'title': 'Edit Registration'
                            })

                    registration = serializer.save()
                    
                    # Calculate changes
                    new_data = {
                        'ticket': str(registration.ticket.name),
                        'first_name': str(registration.first_name),
                        'last_name': str(registration.last_name),
                        'email': str(registration.email),
                        'phone': str(registration.phone),
                        'status': str(registration.status)
                    }
                    
                    changes = {}
                    for field, old_value in old_data.items():
                        new_value = new_data.get(field)
                        if old_value != new_value:
                            changes[field] = [old_value, new_value]
                    
                    if changes:
                        log_action(request.user, 'registration_edit', registration, request, changes=changes)
                    
                    messages.success(request, 'Registration updated successfully.')
                    return redirect('registrations:list')
            except Exception as e:
                messages.error(request, f"Error updating registration: {str(e)}")
                return render(request, 'registrations/form.html', {
                    'tickets': tickets,
                    'registration': registration,
                    'form_data': request.POST,
                    'title': 'Edit Registration'
                })
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
        reg_name = f"{registration.first_name} {registration.last_name}"
        registration.is_active = False
        registration.save()
        log_action(request.user, 'registration_delete', registration, request)
        messages.success(request, f'Registration for "{reg_name}" deleted successfully.')
        return redirect('registrations:list')
    return render(request, 'registrations/delete_confirm.html', {'registration': registration})
