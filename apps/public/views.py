from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.tickets.models import Ticket
from apps.registrations.serializers import PublicRegistrationOrderSerializer
from apps.registrations.models import RegistrationOrder

def ticket_list(request):
    tickets = Ticket.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'public/ticket_list.html', {'tickets': tickets})

from django.http import JsonResponse
from django.urls import reverse

from django.conf import settings

def register_form(request):
    # 1. Sync Selection from GET (Initial Arrival)
    has_get_params = any(key.startswith('qty_') for key in request.GET.keys())
    if has_get_params:
        selection = {k: v for k, v in request.GET.items() if k.startswith('qty_')}
        request.session['registration_selection'] = selection
    
    # 2. Sync Selection from POST (Handling Form Deletions)
    # If the user submits a POST, their actual selection is what's in the attendee forms
    if request.method == 'POST':
        post_selection = {}
        for key in request.POST.keys():
            if key.startswith('attendee_') and key.endswith('_ticket'):
                t_id = request.POST.get(key)
                qty_key = f'qty_{t_id}'
                post_selection[qty_key] = post_selection.get(qty_key, 0) + 1
        
        # Update session with the current state of forms in the UI
        if post_selection:
            request.session['registration_selection'] = post_selection
    
    # Load effective selection from session
    current_selection = request.session.get('registration_selection', {})
    
    # Parse quantities and check availability
    selected_items = []
    total_requested_qty = 0
    availability_errors = []

    for key, value in current_selection.items():
        try:
            ticket_id = int(key.split('_')[1])
            qty = int(value)
            if qty > 0:
                total_requested_qty += qty
                ticket = get_object_or_404(Ticket, id=ticket_id, is_active=True)
                
                available = ticket.available_slots()
                is_available = available is None or qty <= available
                
                if not is_available:
                    err = f"Only {available} slots available for {ticket.name}."
                    availability_errors.append(err)
                
                if qty > ticket.max_per_order:
                    err = f"Maximum {ticket.max_per_order} tickets allowed for {ticket.name}."
                    availability_errors.append(err)
                
                selected_items.append({
                    'ticket': ticket,
                    'quantity': qty,
                    'subtotal': ticket.price * qty,
                    'is_available': is_available
                })
        except (ValueError, IndexError):
            continue

    if not selected_items:
        if has_get_params:
            messages.warning(request, "Please select at least one ticket.")
            return redirect('public:ticket_list')
        return redirect('public:ticket_list')

    # Attendee Slots Generation
    attendee_slots = []
    for item in selected_items:
        for i in range(item['quantity']):
            attendee_slots.append({
                'ticket': item['ticket'],
                'index': len(attendee_slots)
            })

    # Error message if availability dropped
    form_error = " ".join(availability_errors) if availability_errors else None

    if request.method == 'POST':
        # Now that we've updated the session/selection from the POST data above,
        # we check the availability_errors again based on the NEW count.
        if availability_errors:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'non_field_errors': [form_error]}}, status=400)
            return render(request, 'public/registration_form.html', {
                'errors': {'non_field_errors': [form_error]},
                'selected_items': selected_items,
                'attendee_slots': attendee_slots,
                'form_data': request.POST,
                'total_amount': sum(item['subtotal'] for item in selected_items)
            })

        # Process Attendees
        attendees = []
        indices = set()
        for key in request.POST.keys():
            if key.startswith('attendee_') and key.endswith('_ticket'):
                try:
                    index = int(key.split('_')[1])
                    indices.add(index)
                except (ValueError, IndexError):
                    continue
        
        for i in sorted(list(indices)):
            attendees.append({
                'ticket': request.POST.get(f'attendee_{i}_ticket'),
                'first_name': request.POST.get(f'attendee_{i}_first_name'),
                'last_name': request.POST.get(f'attendee_{i}_last_name'),
                'email': request.POST.get(f'attendee_{i}_email'),
                'phone': request.POST.get(f'attendee_{i}_phone'),
            })

        serializer = PublicRegistrationOrderSerializer(
            data={'attendees': attendees},
            context={'user': request.user}
        )

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

        if serializer.is_valid():
            order = serializer.save()
            if 'registration_selection' in request.session:
                del request.session['registration_selection']

            # Security: Whitelist this order ID in the session for the success page
            request.session['last_order_id'] = order.id

            redirect_url = reverse('payments:checkout', kwargs={'order_id': order.id}) if order.total_amount > 0 else reverse('public:order_success', kwargs={'order_uuid': order.uuid})
            
            if is_ajax: return JsonResponse({'success': True, 'redirect_url': redirect_url})
            return redirect(redirect_url)
        else:
            if is_ajax: return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)
            return render(request, 'public/registration_form.html', {
                'errors': serializer.errors,
                'selected_items': selected_items,
                'attendee_slots': attendee_slots,
                'form_data': request.POST,
                'total_amount': sum(item['subtotal'] for item in selected_items)
            })

    total_amount = sum(item['subtotal'] for item in selected_items)
    # Prepare enhanced ticket list for the 'Add Ticket' modal with limits
    all_available_tickets = Ticket.objects.filter(is_active=True).order_by('-created_at')
    enhanced_tickets = []
    for t in all_available_tickets:
        enhanced_tickets.append({
            'id': t.id,
            'name': t.name,
            'price': t.price,
            'available_slots': t.available_slots(),
            'max_per_order': t.max_per_order,
            'duplicate_email_check': t.duplicate_email_check
        })

    return render(request, 'public/registration_form.html', {
        'errors': {'non_field_errors': [form_error]} if form_error else None,
        'selected_items': selected_items,
        'attendee_slots': attendee_slots,
        'total_amount': total_amount,
        'all_tickets': enhanced_tickets,
        'MAX_GLOBAL': getattr(settings, 'MAX_TOTAL_TICKETS_PER_ORDER', 100)
    })

def order_success(request, order_uuid):
    order = get_object_or_404(RegistrationOrder, uuid=order_uuid)
    
    # Ownership check
    is_session_owner = request.session.get('last_order_id') == order.id
    is_buyer = request.user.is_authenticated and order.buyer == request.user
    
    if not (is_session_owner or is_buyer or request.user.is_staff):
        messages.error(request, "You do not have permission to view this order.")
        return redirect('public:ticket_list')

    return render(request, 'public/order_success.html', {'order': order})
