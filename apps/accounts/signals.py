from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from apps.activity_logs.utils import log_action

@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_action(user, 'login', request=request)

@receiver(user_logged_out)
def on_login(sender, request, user, **kwargs):
    log_action(user, 'logout', request=request)
