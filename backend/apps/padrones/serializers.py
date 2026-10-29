from rest_framework import serializers


class EnrollSerializer(serializers.Serializer):
    idPaciente = serializers.IntegerField(min_value=1)
    # CIE-10 (texto) para cronicos o id de discapacidad: se valida en el caso de uso.
    itemId = serializers.CharField(max_length=20)
    centerId = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    enrolledOn = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        # Plan contraer la llave vieja (C7): solo idPaciente. La pantalla abre antes
        # al miembro que nunca se atendio (POST /visits/patient-open).
        from apps.consulta_medica.services.paciente_entrada import resolver_paciente_en_datos

        return resolver_paciente_en_datos(super().validate(attrs))


class DischargeSerializer(serializers.Serializer):
    reasonId = serializers.IntegerField(min_value=1)
    detail = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    dischargedOn = serializers.DateField(required=False, allow_null=True)
