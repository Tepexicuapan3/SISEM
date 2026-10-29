from rest_framework import serializers


class AmbulanceScheduleItemSerializer(serializers.Serializer):
    transferDate = serializers.DateField()
    transferTime = serializers.TimeField()
    transferTypeId = serializers.IntegerField()
    serviceTypeId = serializers.IntegerField()


class CreateAmbulanceRequestSerializer(serializers.Serializer):
    idPaciente = serializers.IntegerField(min_value=1)
    requestingClinicId = serializers.CharField()
    requestedByName = serializers.CharField()
    requestedByRelationshipId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    socialWorkNotes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    reasonId = serializers.IntegerField()
    reasonNotes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    diagnosisText = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    originStreet = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    originZip = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    originNeighborhood = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    originBorough = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    originPhone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    originReference = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    destinationId = serializers.IntegerField()
    schedules = AmbulanceScheduleItemSerializer(many=True)

    def validate(self, attrs):
        # Plan contraer la llave vieja (C7): solo idPaciente. La pantalla abre antes
        # al miembro que nunca se atendio (POST /visits/patient-open).
        from apps.consulta_medica.services.paciente_entrada import resolver_paciente_en_datos

        return resolver_paciente_en_datos(super().validate(attrs))


class AuthorizeAmbulanceRequestSerializer(serializers.Serializer):
    serviceNumber = serializers.CharField()


class RejectAmbulanceRequestSerializer(serializers.Serializer):
    notes = serializers.CharField()
