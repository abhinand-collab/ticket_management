"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def admin_panel_redirect(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('tickets:list')
    return redirect('admin_accounts:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Admin Panel Root Redirect
    path('admin-panel/', admin_panel_redirect),
    
    # Authentication
    path('accounts/', include('apps.accounts.public_urls')),
    path('admin-panel/auth/', include('apps.accounts.admin_urls')),
    
    # Custom Admin/Dashboard
    path('admin-panel/tickets/', include('apps.tickets.urls')),
    path('admin-panel/registrations/', include('apps.registrations.urls')),
    path('admin-panel/logs/', include('apps.activity_logs.urls')),
    
    # Public Portal
    path('', include('apps.public.urls')),
    path('payments/', include('apps.payments.urls')),
]
