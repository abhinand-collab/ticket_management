from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Ticket
from .serializers import TicketSerializer
from apps.activity_logs.utils import log_action

@login_required
def ticket_list(request):
    query = request.GET.get('q')
    ticket_type = request.GET.get('ticket_type')
    quantity_type = request.GET.get('quantity_type')
    
    ticket_queryset = Ticket.objects.filter(is_active=True).order_by('-created_at')
    
    if query:
        ticket_queryset = ticket_queryset.filter(name__icontains=query)
    
    if ticket_type:
        ticket_queryset = ticket_queryset.filter(ticket_type=ticket_type)
        
    if quantity_type:
        ticket_queryset = ticket_queryset.filter(quantity_type=quantity_type)

    paginator = Paginator(ticket_queryset, 10)
    page_number = request.GET.get('page')
    tickets = paginator.get_page(page_number)
    
    return render(request, 'tickets/list.html', {
        'tickets': tickets,
        'query': query,
        'ticket_type': ticket_type,
        'quantity_type': quantity_type
    })

@login_required
def ticket_create(request):
    if request.method == 'POST':
        serializer = TicketSerializer(data=request.POST)
        if serializer.is_valid():
            ticket = serializer.save()
            log_action(request.user, 'ticket_create', ticket, request)
            messages.success(request, 'Ticket created successfully.')
            return redirect('tickets:list')
        else:
            return render(request, 'tickets/form.html', {
                'errors': serializer.errors,
                'form_data': request.POST,
                'title': 'Add Ticket'
            })
    return render(request, 'tickets/form.html', {'title': 'Add Ticket'})

@login_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        serializer = TicketSerializer(ticket, data=request.POST)
        if serializer.is_valid():
            ticket = serializer.save()
            log_action(request.user, 'ticket_edit', ticket, request)
            messages.success(request, 'Ticket updated successfully.')
            return redirect('tickets:list')
        else:
            return render(request, 'tickets/form.html', {
                'errors': serializer.errors,
                'form_data': request.POST,
                'ticket': ticket,
                'title': 'Edit Ticket'
            })
    
    # Pre-populate form with existing data
    return render(request, 'tickets/form.html', {
        'ticket': ticket,
        'title': 'Edit Ticket'
    })

@login_required
def ticket_delete(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if request.method == 'POST':
        ticket_name = ticket.name
        ticket.is_active = False
        ticket.save()
        log_action(request.user, 'ticket_delete', ticket, request)
        messages.success(request, f'Ticket "{ticket_name}" deleted successfully.')
        return redirect('tickets:list')
    return render(request, 'tickets/delete_confirm.html', {'ticket': ticket})
