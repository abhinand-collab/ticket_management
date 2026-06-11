from django.urls import path
from . import views

app_name = 'activity_logs'

urlpatterns = [
    path('', views.log_list, name='list'),
    path('registration/<int:registration_id>/', views.registration_logs, name='registration_logs'),
]
