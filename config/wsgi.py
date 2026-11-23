from django.core.wsgi import get_wsgi_application

from config.django_settings import apply_django_settings_module

apply_django_settings_module()

application = get_wsgi_application()
