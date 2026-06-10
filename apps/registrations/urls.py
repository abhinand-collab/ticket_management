from django.urls import path
from . import views

app_name = 'registrations'

urlpatterns = [
    path('', views.registration_list, name='list'),
    path('orders/', views.order_list, name='order_list'),
    path('create/', views.registration_create, name='create'),
    path('<int:pk>/edit/', views.registration_edit, name='edit'),
    path('<int:pk>/delete/', views.registration_delete, name='delete'),
]
