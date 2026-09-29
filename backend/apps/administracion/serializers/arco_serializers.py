from rest_framework import serializers

from apps.administracion.models import SolicitudArco


class CreateSolicitudArcoSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=SolicitudArco.Tipo.choices)
    noExp = serializers.CharField(max_length=20, allow_blank=False)
    pkNum = serializers.IntegerField(required=False, default=0, min_value=0)
    requesterName = serializers.CharField(max_length=255, allow_blank=False)
    requesterRelation = serializers.ChoiceField(
        choices=SolicitudArco.Relacion.choices, required=False,
    )
    requesterEmail = serializers.EmailField(
        max_length=255, required=False, allow_blank=True, allow_null=True,
    )
    requesterPhone = serializers.CharField(
        max_length=50, required=False, allow_blank=True, allow_null=True,
    )
    description = serializers.CharField(allow_blank=False)
    # Opcional: si la solicitud llego en papel dias antes de capturarse, el
    # plazo corre desde la recepcion real, no desde la captura.
    receivedDate = serializers.DateField(required=False)
    transparencyFolio = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)


class ChangeSolicitudArcoStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            SolicitudArco.Estatus.EN_PROCESO,
            SolicitudArco.Estatus.PROCEDENTE,
            SolicitudArco.Estatus.IMPROCEDENTE,
        ]
    )
    response = serializers.CharField(required=False, allow_blank=True, allow_null=True)
