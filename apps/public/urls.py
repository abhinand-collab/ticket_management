from django.urls import path
from . import views

app_name = 'public'

urlpatterns = [
    path('', views.ticket_list, name='ticket_list'),
    path('register/', views.register_form, name='register_form'),
    path('success/<uuid:order_uuid>/', views.order_success, name='order_success'),
]
