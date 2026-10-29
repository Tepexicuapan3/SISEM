from django.apps import AppConfig


class ConsultaMedicaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.consulta_medica"

    def ready(self):
        # Plan contraer la llave vieja: las tablas de atencion guardan solo
        # id_paciente; la cuenta del portal se vincula por su llave.
        from apps.consulta_medica.services.operational_link_service import connect_operational_signals

        connect_operational_signals()

        # Motor de autorizaciones: la decision tomada en la bandeja se refleja en la receta.
        from apps.consulta_medica.services.autorizacion_motor_service import conectar as conectar_motor

        conectar_motor()
