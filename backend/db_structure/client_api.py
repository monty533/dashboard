import logging
import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils.timezone import localtime
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .client_auth import ClientApiKeyAuthentication, issue_client_api_key
from .models import ClientApiKey, UserProfile


User = get_user_model()
logger = logging.getLogger(__name__)
REGISTER_FIELDS = frozenset({'email', 'password', 'company_name', 'phone', 'address'})


def _text_value(payload, field_name):
    value = payload.get(field_name, '')
    if not isinstance(value, str):
        raise ValueError(f'{field_name} must be a string.')
    return value.strip()


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def register_view(request):
    """
    POST /api/register/

    Required: email, password
    Optional profile fields: company_name, phone, address
    The plain api_key is returned only in this response.
    """
    logger.info('Client registration requested: admin_user_id=%s', request.user.id)
    if not (request.user.is_staff):
        logger.warning('Client registration denied: user_id=%s', request.user.id)
        return Response(
            {'error': 'Only an admin can register client users.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not isinstance(request.data, dict):
        return Response(
            {'error': 'Request body must be a JSON object.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    unexpected = set(request.data.keys()) - REGISTER_FIELDS
    if unexpected:
        return Response(
            {'error': f'Unknown fields: {", ".join(sorted(unexpected))}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        email = _text_value(request.data, 'email').lower()
        password = request.data.get('password', '')
        company_name = _text_value(request.data, 'company_name')
        phone = _text_value(request.data, 'phone')
        address = _text_value(request.data, 'address')
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if not email or not password:
        return Response(
            {'error': 'email and password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(password, str):
        return Response({'error': 'password must be a string.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_email(email)
    except ValidationError:
        return Response({'error': 'Enter a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)

    if len(password) < 8:
        return Response(
            {'error': 'password must contain at least 8 characters.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(phone) > 20:
        return Response({'error': 'phone cannot exceed 20 characters.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email__iexact=email).exists():
        return Response({'error': 'A user with this email already exists.'}, status=status.HTTP_409_CONFLICT)

    try:
        with transaction.atomic():
            username = f'user_{secrets.token_hex(12)}'
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'company_name': company_name,
                    'phone': phone,
                    'address': address,
                },
            )
            raw_api_key = issue_client_api_key(user)
    except IntegrityError:
        logger.warning('Client registration conflict: admin_user_id=%s', request.user.id)
        return Response(
            {'error': 'A user with this email already exists.'},
            status=status.HTTP_409_CONFLICT,
        )

    logger.info('Client registered: user_id=%s admin_user_id=%s', user.id, request.user.id)
    return Response(
        {
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'role': 'admin' if (user.is_staff or user.is_superuser) else 'user',
                'is_active': user.is_active,
                'date_joined': localtime(user.date_joined).strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else '',
            },
            'profile': {
                'company_name': company_name,
                'phone': phone,
                'address': address,
            },
            'api_key': raw_api_key,
            'message': 'Save this API key securely. It will not be shown again.',
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([ClientApiKeyAuthentication])
@permission_classes([IsAuthenticated])
def client_me_view(request):
    """GET /api/client/me/ — verify an API key and inspect its owner."""
    # ClientApiKeyAuthentication validates the X-API-Key header and exposes
    # the matching ClientApiKey row as request.auth.
    client_api_key = request.auth
    if not isinstance(client_api_key, ClientApiKey):
        return Response(
            {'error': 'A valid client API key is required.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        user = User.objects.get(pk=client_api_key.user_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'The user linked to this API key no longer exists.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    profile = UserProfile.objects.filter(user_id=client_api_key.user_id).first()
    logger.info('Client details requested: user_id=%s', user.id)
    return Response({
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'date_joined': localtime(user.date_joined).strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else None,
            'last_login': localtime(user.last_login).strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
        },
        'profile': {
            'company_name': profile.company_name if profile else '',
            'phone': profile.phone if profile else '',
            'address': profile.address if profile else '',
            'created_at': localtime(profile.created_at).strftime('%Y-%m-%d %H:%M:%S') if profile and profile.created_at else None,
            'updated_at': localtime(profile.updated_at).strftime('%Y-%m-%d %H:%M:%S') if profile and profile.updated_at else None,
        },
    })
