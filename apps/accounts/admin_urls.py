from django.urls import path
from . import views

app_name = 'admin_accounts'

urlpatterns = [
    path('login/', views.admin_login, name='login'),
    path('logout/', views.admin_logout, name='logout'),
    path('users/', views.user_list, name='user_list'),
]
