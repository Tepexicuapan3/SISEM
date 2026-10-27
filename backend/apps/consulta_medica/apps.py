from django.apps import AppConfig


class ConsultaMedicaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.consulta_medica"

    def ready(self):
        # 5.1 paso 7c: todo registro clinico nuevo se guarda con su id_paciente.
        from apps.consulta_medica.services.operational_link_service import connect_operational_signals
        from apps.consulta_medica.services.patient_link_service import connect_signals

        connect_signals()
        # Plan identidad, Fase 5: lo mismo en las tablas operativas.
        connect_operational_signals()

        # Motor de autorizaciones: la decision tomada en la bandeja se refleja en la receta.
        from apps.consulta_medica.services.autorizacion_motor_service import conectar as conectar_motor

        conectar_motor()
