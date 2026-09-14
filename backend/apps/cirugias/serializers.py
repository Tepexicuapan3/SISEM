from rest_framework import serializers


class ScheduleSurgerySerializer(serializers.Serializer):
    noExp = serializers.CharField()
    pkNum = serializers.IntegerField(required=False, default=0)
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


class CancelSurgerySerializer(serializers.Serializer):
    reasonId = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_null=True, allow_blank=True)
