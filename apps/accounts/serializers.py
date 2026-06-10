from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

class LoginSerializer(serializers.Serializer):
    # Added max_length for security (prevents large string processing attacks)
    username = serializers.CharField(required=True, max_length=150)
    password = serializers.CharField(required=True, write_only=True, max_length=128)

    def validate(self, data):
        from django.contrib.auth import authenticate
        username = data.get('username')
        password = data.get('password')

        # Industry Standard: Use a single generic message for all authentication failures
        error_msg = "Invalid username or password."

        if username and password:
            user = authenticate(username=username, password=password)
            if not user or not user.is_active:
                raise serializers.ValidationError(error_msg)
        else:
            raise serializers.ValidationError(error_msg)

        data['user'] = user
        return data

import re
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, min_length=1, max_length=150)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate_username(self, value):
        if ' ' in value:
            raise serializers.ValidationError("Username cannot contain spaces.")
        if not re.match(r'^[\w.@+-]+$', value):
            raise serializers.ValidationError("Enter a valid username. This value may contain only letters, numbers, and @/./+/-/_ characters.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return email

    def validate_first_name(self, value):
        if not re.match(r'^[a-zA-Z\s\-]+$', value):
            raise serializers.ValidationError("First name can only contain letters, spaces, and hyphens.")
        return value

    def validate_last_name(self, value):
        if not re.match(r'^[a-zA-Z\s\-]+$', value):
            raise serializers.ValidationError("Last name can only contain letters, spaces, and hyphens.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        
        # Also run Django's built-in validators (similarity, common pass, etc.)
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
            
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user
