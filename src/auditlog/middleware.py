import threading
from auditlog.compat import is_authenticated
from django.utils.deprecation import MiddlewareMixin

threadlocal = threading.local()


def set_audit_info(ip=None, user=None):
    threadlocal.auditlog = {
        'remote_addr': ip,
        'actor': user
    }


class AuditlogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.META.get('HTTP_X_FORWARDED_FOR'):
            audit_ip = request.META.get('HTTP_X_FORWARDED_FOR').split(',')[0]
        else:
            audit_ip = request.META.get('REMOTE_ADDR')

        set_audit_info(
            audit_ip,
            request.user if (
                (hasattr(request, 'user') and is_authenticated(request.user))
            ) else None
        )

    def process_response(self, request, response):
        set_audit_info()
        return response

    def process_exception(self, request, exception):
        set_audit_info()
        return None
