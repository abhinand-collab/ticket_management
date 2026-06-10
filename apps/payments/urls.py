from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('', views.payment_list, name='list'),
    path('checkout/<int:order_id>/', views.checkout, name='checkout'),
    path('verify/', views.verify_payment, name='verify'),
]
