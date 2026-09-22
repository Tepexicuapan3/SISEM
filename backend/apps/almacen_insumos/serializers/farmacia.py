from rest_framework import serializers

from apps.catalogos.models import Medicamentos

from ..models.catalogos import CatInsumo
from ..models.farmacia import MedicamentoInsumo


class MedicamentoInsumoSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="pk", read_only=True)
    idMedicamento = serializers.PrimaryKeyRelatedField(
        source="medicamento",
        queryset=Medicamentos.objects.filter(is_active=True),
    )
    medicamentoLabel = serializers.SerializerMethodField()
    idInsumo = serializers.PrimaryKeyRelatedField(
        source="insumo",
        queryset=CatInsumo.objects.filter(is_active=True),
    )
    insumoLabel = serializers.SerializerMethodField()
    factorConversion = serializers.DecimalField(
        source="factor_conversion", max_digits=12, decimal_places=4, required=False,
    )
    permiteFraccion = serializers.BooleanField(source="permite_fraccion", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    def get_medicamentoLabel(self, obj) -> str:
        return obj.medicamento.name if obj.medicamento_id else ""

    def get_insumoLabel(self, obj) -> str:
        return obj.insumo.nombre if obj.insumo_id else ""

    def validate(self, attrs):
        medicamento = attrs.get("medicamento") or getattr(self.instance, "medicamento", None)
        is_active = attrs.get("is_active", True if self.instance is None else self.instance.is_active)

        if medicamento is not None and is_active:
            conflicto = MedicamentoInsumo.objects.filter(
                medicamento=medicamento, is_active=True,
            )
            if self.instance is not None:
                conflicto = conflicto.exclude(pk=self.instance.pk)
            if conflicto.exists():
                raise serializers.ValidationError({
                    "idMedicamento": [
                        "Este medicamento ya tiene un mapeo activo a un insumo."
                    ],
                })

        return attrs

    class Meta:
        model = MedicamentoInsumo
        fields = [
            "id", "idMedicamento", "medicamentoLabel", "idInsumo", "insumoLabel",
            "factorConversion", "permiteFraccion", "isActive", "createdAt",
        ]
        read_only_fields = ["id", "medicamentoLabel", "insumoLabel", "createdAt"]
