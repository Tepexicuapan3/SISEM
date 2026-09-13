"""
Validación de esquema (capa de presentación) para las listas anidadas de
horarios. Antes de esto, `medico_views.py` indexaba los dicts de horario
directo (`h["diaSemana"]`) sin validar que las llaves existieran -- un
payload malformado producía un `KeyError` sin capturar (500), en vez de un
400 limpio. Las reglas de NEGOCIO (ej. "solo un pase activo") siguen
viviendo en `uses_case/`, acá solo se valida forma/tipo.
"""

from rest_framework import serializers

from apps.medicos.models import CANAL_ATENCION, DIAS_SEMANA

_DIA_SEMANA_CHOICES = [d[0] for d in DIAS_SEMANA]
_CANAL_CHOICES = [c[0] for c in CANAL_ATENCION]


class ConsultorioHorarioSerializer(serializers.Serializer):
    diaSemana = serializers.ChoiceField(choices=_DIA_SEMANA_CHOICES)
    horaInicio = serializers.TimeField()
    horaFin = serializers.TimeField()
    intervaloCitaMin = serializers.IntegerField(required=False, default=20, min_value=1)
    canal = serializers.ChoiceField(choices=_CANAL_CHOICES, required=False, default="PRESENCIAL")


class CoberturaHorarioSerializer(serializers.Serializer):
    diaSemana = serializers.ChoiceField(choices=_DIA_SEMANA_CHOICES)
    horaInicio = serializers.TimeField()
    horaFin = serializers.TimeField()


def validate_horarios(horarios_payload, *, serializer_class=ConsultorioHorarioSerializer):
    """
    Valida una lista de horarios contra `serializer_class`. Devuelve la
    lista normalizada (`validated_data`, con defaults aplicados) o lanza
    `serializers.ValidationError` (el llamador la traduce a VisitDomainError
    con el detalle de campo por campo).
    """
    serializer = serializer_class(data=horarios_payload or [], many=True)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
