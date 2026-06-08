from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('', views.ticket_list, name='list'),
    path('create/', views.ticket_create, name='create'),
    path('<int:pk>/edit/', views.ticket_edit, name='edit'),
    path('<int:pk>/delete/', views.ticket_delete, name='delete'),
]
