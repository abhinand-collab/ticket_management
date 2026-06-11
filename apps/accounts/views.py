from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .serializers import UserRegistrationSerializer, LoginSerializer
from django.contrib.auth.decorators import login_required

from django.contrib.auth.models import User
from django.core.paginator import Paginator

@login_required
def user_list(request):
    if not request.user.is_staff:
        return redirect('public:ticket_list')
    
    search = request.GET.get('search', '')
    joined_from = request.GET.get('joined_from', '')
    joined_to = request.GET.get('joined_to', '')
    
    from django.db.models import Q, Value, CharField
    from django.db.models.functions import Concat

    user_queryset = User.objects.filter(is_staff=False)
    
    if search:
        user_queryset = user_queryset.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(full_name__icontains=search)
        )
        
    if joined_from:
        user_queryset = user_queryset.filter(date_joined__date__gte=joined_from)
    if joined_to:
        user_queryset = user_queryset.filter(date_joined__date__lte=joined_to)

    user_queryset = user_queryset.order_by('-date_joined')
    
    paginator = Paginator(user_queryset, 10)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'filters': {
            'search': search,
            'joined_from': joined_from,
            'joined_to': joined_to,
        }
    })

def admin_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('tickets:list')
        else:
            # If a normal user is already logged in, show them why they can't access admin
            messages.error(request, "Access denied. Admin privileges required.")
            return redirect('public:ticket_list')

    if request.method == 'POST':
        serializer = LoginSerializer(data=request.POST)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            if user.is_staff:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('tickets:list')
            else:
                # Security: Generic message to prevent account discovery
                messages.error(request, "Invalid username or password.")
                return render(request, 'accounts/login.html', {
                    'form_data': request.POST
                })
        else:
            return render(request, 'accounts/login.html', {
                'errors': serializer.errors, 
                'form_data': request.POST
            })
            
    return render(request, 'accounts/login.html')

def admin_logout(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('admin_accounts:login')

from django.http import JsonResponse
from django.urls import reverse

def user_register(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('tickets:list')
        return redirect('public:ticket_list')

    if request.method == 'POST':
        serializer = UserRegistrationSerializer(data=request.POST)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        
        if serializer.is_valid():
            user = serializer.save()
            login(request, user)
            
            redirect_url = reverse('public:ticket_list')
            if is_ajax:
                return JsonResponse({
                    'success': True, 
                    'redirect_url': redirect_url,
                    'message': f"Welcome, {user.username}! Your account has been created."
                })
            
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect(redirect_url)
        else:
            if is_ajax:
                return JsonResponse({
                    'success': False, 
                    'errors': serializer.errors
                }, status=400)
            return render(request, 'accounts/register.html', {
                'errors': serializer.errors, 
                'form_data': request.POST
            })
    
    return render(request, 'accounts/register.html')

def user_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('tickets:list')
        return redirect('public:ticket_list')

    if request.method == 'POST':
        serializer = LoginSerializer(data=request.POST)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

        if serializer.is_valid():
            user = serializer.validated_data['user']
            if not user.is_staff:
                login(request, user)
                
                next_url = request.GET.get('next') or reverse('public:ticket_list')
                if is_ajax:
                    return JsonResponse({
                        'success': True, 
                        'redirect_url': next_url,
                        'message': f"Welcome back, {user.username}!"
                    })
                
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(next_url)
            else:
                # Security: Generic message
                error_msg = "Invalid username or password."
                if is_ajax:
                    return JsonResponse({
                        'success': False, 
                        'message': error_msg
                    }, status=400)
                messages.error(request, error_msg)
        else:
            if is_ajax:
                return JsonResponse({
                    'success': False, 
                    'errors': serializer.errors
                }, status=400)
            return render(request, 'accounts/user_login.html', {
                'errors': serializer.errors, 
                'form_data': request.POST
            })
            
    return render(request, 'accounts/user_login.html')

def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('public:ticket_list')
