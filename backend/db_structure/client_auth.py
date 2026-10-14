import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ClientApiKey


logger = logging.getLogger(__name__)


def issue_client_api_key(user):
    """Create a client key and return its plain value exactly once."""
    while True:
        prefix = f'dsh_{secrets.token_hex(8)}'
        if not ClientApiKey.objects.filter(prefix=prefix).exists():
            break

    secret = secrets.token_urlsafe(32)
    raw_key = f'{prefix}.{secret}'
    ClientApiKey.objects.create(
        user=user,
        prefix=prefix,
        key_hash=hashlib.sha256(raw_key.encode('utf-8')).hexdigest(),
    )
    return raw_key


class ClientApiKeyAuthentication(BaseAuthentication):
    """Authenticate client requests using the X-API-Key header."""

    HEADER_NAME = 'X-API-Key'

    def authenticate(self, request):
        raw_key = request.headers.get(self.HEADER_NAME, '').strip().strip('"\'')
        if not raw_key:
            return None

        prefix, separator, _secret = raw_key.partition('.')
        if not separator or not prefix.startswith('dsh_'):
            logger.warning('Client API key rejected: invalid format prefix=%s', prefix[:24])
            raise AuthenticationFailed('Invalid API key.')

        api_key = (
            ClientApiKey.objects
            .select_related('user')
            .filter(prefix=prefix)
            .first()
        )
        if api_key is None:
            logger.warning('Client API key rejected: prefix not found prefix=%s', prefix)
            raise AuthenticationFailed('Invalid API key.')

        # The preferred credential is prefix.secret, where the backend hashes
        # the complete value. Also accept prefix.key_hash because the admin
        # verification screen sends the stored hash suffix explicitly.
        supplied_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        supplied_stored_hash = _secret
        valid_raw_key = hmac.compare_digest(supplied_hash, api_key.key_hash)
        valid_hash_credential = hmac.compare_digest(supplied_stored_hash, api_key.key_hash)
        if not (valid_raw_key or valid_hash_credential):
            logger.warning(
                'Client API key rejected: prefix=%s prefix_found=%s raw_hash_match=%s stored_hash_match=%s',
                prefix,
                api_key is not None,
                valid_raw_key,
                valid_hash_credential,
            )
            raise AuthenticationFailed('Invalid API key.')
        if not api_key.is_active or api_key.revoked_at is not None:
            logger.warning('Client API key rejected: inactive or revoked prefix=%s', prefix)
            raise AuthenticationFailed('API key is inactive.')
        if api_key.expires_at and api_key.expires_at <= timezone.now():
            logger.warning('Client API key rejected: expired prefix=%s', prefix)
            raise AuthenticationFailed('API key has expired.')
        if not api_key.user.is_active:
            logger.warning('Client API key rejected: inactive user prefix=%s', prefix)
            raise AuthenticationFailed('User is inactive.')

        # Avoid writing to the database on every request.
        now = timezone.localtime()
        if not api_key.last_used_at or now - api_key.last_used_at >= timedelta(minutes=5):
            ClientApiKey.objects.filter(pk=api_key.pk).update(last_used_at=now)

        logger.info('Client API key authenticated: prefix=%s user_id=%s', prefix, api_key.user_id)
        return api_key.user, api_key
