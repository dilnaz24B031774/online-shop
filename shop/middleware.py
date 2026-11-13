from django.utils import translation


class StaffLanguageMiddleware:
    """Keep the management interface Russian without changing the storefront API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith(("/admin/", "/staff/")):
            with translation.override("ru"):
                request.LANGUAGE_CODE = "ru"
                response = self.get_response(request)
                response.headers.setdefault("Content-Language", "ru")
                return response
        return self.get_response(request)
