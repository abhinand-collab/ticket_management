from .models import ActivityLog

def log_action(user, action, obj=None, request=None):
    """
    Utility to log admin actions.
    """
    ip = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

    ActivityLog.objects.create(
        user=user,
        action=action,
        object_type=obj.__class__.__name__ if obj else '',
        object_id=obj.pk if obj else None,
        description=f"{action.replace('_', ' ').title()}: {str(obj) if obj else 'N/A'}",
        ip_address=ip,
    )
