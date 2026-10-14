"""Isolated test database; never connects to the configured application database."""
from .settings import *  # noqa: F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
LOGGING = {'version': 1, 'disable_existing_loggers': False, 'handlers': {'null': {'class': 'logging.NullHandler'}}, 'root': {'handlers': ['null']}}
