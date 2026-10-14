import logging


class SkipOptionsFilter(logging.Filter):
    """Hide browser CORS preflight access logs from Django's server logger."""

    def filter(self, record):
        request = getattr(record, 'request', None)
        if getattr(request, 'method', '').upper() == 'OPTIONS':
            return False
        return not record.getMessage().startswith('"OPTIONS ')
