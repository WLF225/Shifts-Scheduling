"""Logs requests and responses to Logs.txt."""
import logging

handler = logging.FileHandler('Logs.txt')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s '))

logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class SimpleMiddleware:
    """Logs each request and response status."""

    def __init__(self, get_response):
        """Stores the next handler in the chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Logs the request, calls through, logs the status."""
        logger.info(f"Request: {request.method} {request.path}")

        response = self.get_response(request)

        logger.info(f"Response: {response.status_code}")

        return response