from django.apps import AppConfig


class PasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pases"

    def ready(self):
        # Motor de autorizaciones: el resultado de la bandeja se refleja en el pase.
        from apps.pases.services.autorizacion_motor_service import conectar

        conectar()
