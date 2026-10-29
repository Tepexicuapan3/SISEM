from rest_framework import serializers


class ScheduleSurgerySerializer(serializers.Serializer):
    idPaciente = serializers.IntegerField(min_value=1)
    surgeonId = serializers.IntegerField()
    surgeryTypeId = serializers.IntegerField()
    classificationId = serializers.IntegerField()
    originClinicId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    scheduledDate = serializers.DateField()
    scheduledTime = serializers.TimeField()
    durationMinutes = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    contactPhone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    diagnosisText = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    requirements = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    cieCodes = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        # Plan contraer la llave vieja (C7): solo idPaciente. La pantalla abre antes
        # al miembro que nunca se atendio (POST /visits/patient-open).
        from apps.consulta_medica.services.paciente_entrada import resolver_paciente_en_datos

        return resolver_paciente_en_datos(super().validate(attrs))


class CancelSurgerySerializer(serializers.Serializer):
    reasonId = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
