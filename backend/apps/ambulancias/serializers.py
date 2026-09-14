from rest_framework import serializers


class AmbulanceScheduleItemSerializer(serializers.Serializer):
    transferDate = serializers.DateField()
    transferTime = serializers.TimeField()
    transferTypeId = serializers.IntegerField()
    serviceTypeId = serializers.IntegerField()


class CreateAmbulanceRequestSerializer(serializers.Serializer):
    noExp = serializers.CharField()
    pkNum = serializers.IntegerField(required=False, default=0)
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


class AuthorizeAmbulanceRequestSerializer(serializers.Serializer):
    serviceNumber = serializers.CharField()


class RejectAmbulanceRequestSerializer(serializers.Serializer):
    notes = serializers.CharField()
