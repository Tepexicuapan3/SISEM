from rest_framework import serializers

from apps.catalogos.serializers import AuditFieldsMixin, build_user_ref
from apps.catalogos.models import CatCentroAtencion, Vacunas

from .models import VacInventario


class VacInventarioListSerializer(serializers.ModelSerializer):
    vaccine = serializers.SerializerMethodField()
    center = serializers.SerializerMethodField()
    stockQuantity = serializers.IntegerField(source="stock_quantity")
    appliedDoses = serializers.IntegerField(source="applied_doses")
    availableDoses = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = VacInventario
        fields = ("id", "vaccine", "center", "stockQuantity", "appliedDoses", "availableDoses", "isActive")

    def get_vaccine(self, obj):
        v = obj.vaccine
        return {"id": v.id, "name": v.name}

    def get_center(self, obj):
        c = obj.center
        return {"id": c.id, "name": c.name}

    def get_availableDoses(self, obj):
        return max(obj.stock_quantity - obj.applied_doses, 0)


class VacInventarioDetailSerializer(AuditFieldsMixin, VacInventarioListSerializer):
    class Meta(VacInventarioListSerializer.Meta):
        fields = VacInventarioListSerializer.Meta.fields + (
            "createdAt", "createdBy", "updatedAt", "updatedBy",
        )

    def get_createdBy(self, obj):
        return build_user_ref(obj.created_by_id)

    def get_updatedBy(self, obj):
        return build_user_ref(obj.updated_by_id)


class VacInventarioCreateSerializer(serializers.Serializer):
    vaccineId = serializers.IntegerField(min_value=1)
    centerId = serializers.IntegerField(min_value=1)
    stockQuantity = serializers.IntegerField(min_value=0)

    def validate_vaccineId(self, value):
        if not Vacunas.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Vacuna no encontrada o inactiva.")
        return value

    def validate_centerId(self, value):
        if not CatCentroAtencion.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Centro de atención no encontrado o inactivo.")
        return value


class VacInventarioUpdateSerializer(serializers.Serializer):
    stockQuantity = serializers.IntegerField(min_value=0, required=False)
    isActive = serializers.BooleanField(required=False)
