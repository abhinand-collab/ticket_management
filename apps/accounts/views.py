from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

def admin_login(request):
    if request.user.is_authenticated:
        return redirect('tickets:list')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_staff:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('tickets:list')
            else:
                messages.error(request, "Access denied. Admin privileges required.")
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'accounts/login.html')

def admin_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')
