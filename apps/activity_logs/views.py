from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import ActivityLog

@login_required
def log_list(request):
    log_list = ActivityLog.objects.all().order_by('-timestamp')
    paginator = Paginator(log_list, 20) # Show 20 logs per page
    page_number = request.GET.get('page')
    logs = paginator.get_page(page_number)
    return render(request, 'activity_logs/list.html', {'logs': logs})
