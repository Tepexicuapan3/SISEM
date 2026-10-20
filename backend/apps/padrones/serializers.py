from rest_framework import serializers


class EnrollSerializer(serializers.Serializer):
    noExp = serializers.CharField(max_length=20)
    pkNum = serializers.IntegerField(min_value=0, required=False, default=0)
    # CIE-10 (texto) para cronicos o id de discapacidad: se valida en el caso de uso.
    itemId = serializers.CharField(max_length=20)
    centerId = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    enrolledOn = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)


class DischargeSerializer(serializers.Serializer):
    reasonId = serializers.IntegerField(min_value=1)
    detail = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    dischargedOn = serializers.DateField(required=False, allow_null=True)
