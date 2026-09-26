import hmac

from django.conf import settings
from django.http import HttpResponseForbidden


def origin_auth(get_response):
    """Refuse requests that skipped Cloudflare.

    Cloudflare adds X-Origin-Auth (Transform Rule) on every proxied request. Someone hitting
    Railway's edge directly with our Host header does not know the secret. Off when unset (local).
    """

    def middleware(request):
        secret = settings.ORIGIN_AUTH_SECRET
        if (
            secret
            and request.META.get("HTTP_HOST") != "healthcheck.railway.app"
            and not hmac.compare_digest(request.META.get("HTTP_X_ORIGIN_AUTH", ""), secret)
        ):
            return HttpResponseForbidden()
        return get_response(request)

    return middleware
