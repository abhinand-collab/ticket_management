from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import ActivityLog

from django.db.models import Q

@login_required
def log_list(request):
    search = request.GET.get('search', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    query = ActivityLog.objects.select_related('user').all()

    if search:
        query = query.filter(
            Q(description__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    if action_filter:
        query = query.filter(action=action_filter)

    if date_from:
        query = query.filter(timestamp__date__gte=date_from)
    if date_to:
        query = query.filter(timestamp__date__lte=date_to)

    log_queryset = query.order_by('-timestamp')
    
    paginator = Paginator(log_queryset, 20)
    page_number = request.GET.get('page')
    logs = paginator.get_page(page_number)
    
    return render(request, 'activity_logs/list.html', {
        'logs': logs,
        'action_choices': ActivityLog.ACTION_CHOICES,
        'filters': {
            'search': search,
            'action': action_filter,
            'date_from': date_from,
            'date_to': date_to,
        }
    })

@login_required
def registration_logs(request, registration_id):
    logs = ActivityLog.objects.filter(
        object_type='Registration',
        object_id=registration_id
    ).order_by('-timestamp')
    
    return render(request, 'activity_logs/registration_logs.html', {
        'logs': logs,
        'registration_id': registration_id
    })
