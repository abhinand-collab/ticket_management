from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import ActivityLog

@login_required
def log_list(request):
    logs = ActivityLog.objects.all().order_by('-timestamp')
    return render(request, 'activity_logs/list.html', {'logs': logs})
