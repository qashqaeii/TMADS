from django.core.asgi import get_asgi_application

from config.django_settings import apply_django_settings_module

apply_django_settings_module()

application = get_asgi_application()
