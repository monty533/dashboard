import logging

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .client_auth import ClientApiKeyAuthentication
from .models import ClientApiKey, UserDetails
from .serializers import UserDetailsSerializer


logger = logging.getLogger(__name__)
User = get_user_model()

PUSH_PERMISSION_TIMESTAMP_FIELDS = {
    'bse_push': 'bse_push_at',
    'bsestarmf_push': 'bsestarmf_push_at',
    'nse_push': 'nse_push_at',
    'nsdl_push': 'nsdl_push_at',
    'cdsl_push': 'cdsl_push_at',
    'mcx_push': 'mcx_push_at',
    'mse_push': 'mse_push_at',
    'ckyc_push': 'ckyc_push_at',
    'kra_push': 'kra_push_at',
}


class UserDetailsAPIView(APIView):
    """Browse and save UserDetails using an API key or dashboard token."""

    authentication_classes = (ClientApiKeyAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _target_user(request):
        """Resolve the record owner without allowing a client to impersonate another user."""
        if isinstance(request.auth, ClientApiKey):
            return request.user, None

        if not (request.user.is_staff or request.user.is_superuser):
            return request.user, None

        raw_user_id = request.query_params.get('user_id', '').strip()
        if not raw_user_id:
            return None, Response(
                {
                    'success': False,
                    'valid': False,
                    'message': 'Select a company before saving UserDetails.',
                    'errors': {'user_id': ['user_id is required for admin requests.']},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_user = User.objects.get(
                pk=raw_user_id,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return None, Response(
                {
                    'success': False,
                    'valid': False,
                    'message': 'Selected company was not found.',
                    'errors': {'user_id': ['Select a valid company.']},
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return target_user, None

    @staticmethod
    def _validation_response(serializer):
        return Response(
            {
                'success': False,
                'valid': False,
                'message': 'Validation failed.',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    @staticmethod
    def _body_error_response():
        return Response(
            {
                'success': False,
                'valid': False,
                'message': 'Validation failed.',
                'errors': {'body': ['Request body must be a JSON object.']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        target_user, target_error = self._target_user(request)
        if target_error:
            return target_error

        clientcode = request.query_params.get('clientcode', '').strip()
        queryset = UserDetails.objects.filter(user_id=target_user.id)
        if clientcode:
            record = queryset.filter(clientcode=clientcode).first()
            if record is None:
                return Response(
                    {
                        'success': False,
                        'message': 'Client code was not found.',
                        'errors': {'clientcode': ['Select a valid client code.']},
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response({
                'success': True,
                'user_id': target_user.id,
                'data': UserDetailsSerializer(record).data,
            })

        clients = list(queryset.values(
            'id', 'clientcode', 'aadhaar_name', 'pan', 'email',
        ).order_by('clientcode'))
        return Response({
            'success': True,
            'user_id': target_user.id,
            'clients': clients,
        })

    def post(self, request):
        target_user, target_error = self._target_user(request)
        if target_error:
            return target_error
        if not isinstance(request.data, dict):
            return self._body_error_response()

        serializer = UserDetailsSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_response(serializer)

        try:
            with transaction.atomic():
                user_details = serializer.save(user=target_user)
        except IntegrityError:
            logger.warning(
                'UserDetails create conflict: user_id=%s clientcode=%s',
                target_user.id,
                request.data.get('clientcode', ''),
            )
            return Response(
                {
                    'success': False,
                    'valid': False,
                    'message': 'A UserDetails record with this clientcode already exists.',
                    'errors': {
                        'clientcode': ['This clientcode is already registered.'],
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        logger.info(
            'UserDetails created through API: user_id=%s clientcode=%s id=%s',
            target_user.id,
            user_details.clientcode,
            user_details.id,
        )
        return Response(
            {
                'success': True,
                'valid': True,
                'message': 'UserDetails validated and created successfully.',
                'user_id': target_user.id,
                'data': UserDetailsSerializer(user_details).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        return self._update(request, partial=True)

    def put(self, request):
        return self._update(request, partial=False)

    def _update(self, request, partial):
        target_user, target_error = self._target_user(request)
        if target_error:
            return target_error
        if not isinstance(request.data, dict):
            return self._body_error_response()

        clientcode = request.query_params.get('clientcode', '').strip()
        if not clientcode:
            clientcode = str(request.data.get('clientcode', '') or '').strip()
        if not clientcode:
            return Response(
                {
                    'success': False,
                    'valid': False,
                    'message': 'Client code is required for an update.',
                    'errors': {'clientcode': ['clientcode is required.']},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        record = UserDetails.objects.filter(
            user_id=target_user.id,
            clientcode=clientcode,
        ).first()
        if record is None:
            return Response(
                {
                    'success': False,
                    'valid': False,
                    'message': 'Client code was not found.',
                    'errors': {'clientcode': ['Select a valid client code.']},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UserDetailsSerializer(record, data=request.data, partial=partial)
        if not serializer.is_valid():
            return self._validation_response(serializer)

        try:
            with transaction.atomic():
                changed_timestamps = [
                    timestamp_field
                    for permission_field, timestamp_field in PUSH_PERMISSION_TIMESTAMP_FIELDS.items()
                    if permission_field in serializer.validated_data
                    and bool(getattr(record, permission_field))
                    != bool(serializer.validated_data[permission_field])
                    and timestamp_field not in serializer.validated_data
                ]
                updated_record = serializer.save()
                if changed_timestamps:
                    for timestamp_field in changed_timestamps:
                        setattr(updated_record, timestamp_field, None)
                    updated_record.save(update_fields=changed_timestamps)
        except IntegrityError:
            logger.warning(
                'UserDetails update conflict: user_id=%s clientcode=%s',
                target_user.id,
                clientcode,
            )
            return Response(
                {
                    'success': False,
                    'valid': False,
                    'message': 'Another UserDetails record already uses this clientcode.',
                    'errors': {
                        'clientcode': ['This clientcode is already registered.'],
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        logger.info(
            'UserDetails updated through API: user_id=%s clientcode=%s id=%s',
            target_user.id,
            updated_record.clientcode,
            updated_record.id,
        )
        return Response({
            'success': True,
            'valid': True,
            'message': 'UserDetails updated successfully.',
            'user_id': target_user.id,
            'data': UserDetailsSerializer(updated_record).data,
        })
