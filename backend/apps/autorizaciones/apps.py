from django.apps import AppConfig


class AutorizacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.autorizaciones"
    verbose_name = "Autorizaciones médicas"

    def ready(self):
        from .notificador import registrar

        registrar()
