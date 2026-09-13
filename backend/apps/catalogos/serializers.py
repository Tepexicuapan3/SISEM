import re

from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.authentication.repositories.user_repository import UserRepository
from apps.catalogos.models import (
    Areas,
    Autorizadores,
    Bajas,
    CalidadLaboral,
    CatAreaClinica,
    CatCentroAtencion,
    CatCentroAtencionHorario,
    CatCentroAtencionExcepcion,
    CentroAreaClinica,
    Consultorios,
    CatCie9Mc,
    Discapacidades,
    EdoCivil,
    Enfermedades,
    Escolaridad,
    Escuelas,
    Especialidades,
    EstudiosMed,
    GruposDeMedicamentos,
    Licencias,
    Medicamentos,
    MotivoCita,
    Ocupaciones,
    OrigenCons,
    Parentesco,
    Pases,
    Permisos,
    Religion,
    Roles,
    CatSucursal,
    TipoDeCitas,
    TipoConsulta,
    TipoResidencia,
    TiposAreas,
    TiposSanguineo,
    TpAutorizacion,
    Turnos,
    Vacunas,
    CatTipoPersonal,
)
from apps.catalogos.models.cies import CatCies


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_user_ref(user_id):
    """Resuelve un user_id a {id, name} independientemente del tipo de modelo."""
    if not user_id:
        return None
    user = UserRepository.get_by_id(user_id)
    if not user:
        return {"id": user_id, "name": ""}

    if hasattr(user, "nombre") and hasattr(user, "paterno"):
        name = " ".join(filter(None, [user.nombre, user.paterno, user.materno])).strip()
        sy_user = getattr(user, "id_usuario", None)
        if not name:
            name = getattr(sy_user, "usuario", "")
        resolved_id = getattr(sy_user, "id_usuario", None) or user_id
        return {"id": resolved_id, "name": name}

    profile = getattr(user, "detalle", None) or getattr(user, "syusuarios", None)
    if profile:
        name = " ".join(filter(None, [profile.nombre, profile.paterno, profile.materno])).strip()
    else:
        name = getattr(user, "usuario", "")
    resolved_id = getattr(user, "id_usuario", None) or getattr(user, "id", None) or user_id
    return {"id": resolved_id, "name": name}


def build_catalog_ref(ref_id, queryset):
    """Resuelve un FK a {id, name} con una sola consulta ligera."""
    if not ref_id:
        return None
    item = queryset.filter(pk=ref_id).only("id", "name").first()
    return {"id": ref_id, "name": item.name if item else ""}


# ---------------------------------------------------------------------------
# Mixins de auditoría
# ---------------------------------------------------------------------------

class AuditFieldsMixin(serializers.Serializer):
    """
    Añade createdAt/createdBy/updatedAt/updatedBy a cualquier serializer.
    Usar como mixin junto a ModelSerializer.
    """
    createdAt = serializers.DateTimeField(source="created_at", format="%Y-%m-%dT%H:%M:%SZ", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedAt = serializers.DateTimeField(source="updated_at", format="%Y-%m-%dT%H:%M:%SZ", read_only=True)
    updatedBy = serializers.SerializerMethodField()

    def get_createdBy(self, obj):
        return build_user_ref(getattr(obj, "created_by_id", None))

    def get_updatedBy(self, obj):
        return build_user_ref(getattr(obj, "updated_by_id", None))


# ---------------------------------------------------------------------------
# Serializers base de catálogos
# ---------------------------------------------------------------------------

class CatalogListSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        fields = ("id", "name", "isActive")


class CatalogDetailSerializer(AuditFieldsMixin, serializers.ModelSerializer):
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        fields = ("id", "name", "isActive", "createdAt", "createdBy", "updatedAt", "updatedBy")


class CatalogWriteSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        fields = ("name", "isActive")


class CatalogListWithCodeSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        fields = CatalogListSerializer.Meta.fields + ("code",)


class CatalogDetailWithCodeSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        fields = CatalogDetailSerializer.Meta.fields + ("code",)


class CatalogRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


# ---------------------------------------------------------------------------
# CatCentroAtencion
# ---------------------------------------------------------------------------

class CatCentroAtencionListSerializer(CatalogListSerializer):
    code = serializers.CharField()
    centerType = serializers.CharField(source="center_type")
    legacyFolio = serializers.CharField(source="legacy_folio", allow_null=True)
    isExternal = serializers.BooleanField(source="is_external")

    class Meta(CatalogListSerializer.Meta):
        model = CatCentroAtencion
        fields = CatalogListSerializer.Meta.fields + ("code", "centerType", "legacyFolio", "isExternal")


class CatCentroAtencionDetailSerializer(CatalogDetailSerializer):
    code = serializers.CharField()
    centerType = serializers.CharField(source="center_type")
    legacyFolio = serializers.CharField(source="legacy_folio", allow_null=True)
    isExternal = serializers.BooleanField(source="is_external")
    address = serializers.CharField(allow_null=True, allow_blank=True)
    postalCode = serializers.CharField(source="postal_code", allow_null=True, allow_blank=True)
    neighborhood = serializers.CharField(allow_null=True, allow_blank=True)
    municipality = serializers.CharField(allow_null=True, allow_blank=True)
    state = serializers.CharField(allow_null=True, allow_blank=True)
    city = serializers.CharField(allow_null=True, allow_blank=True)
    phone = serializers.CharField(allow_null=True, allow_blank=True)

    class Meta(CatalogDetailSerializer.Meta):
        model = CatCentroAtencion
        fields = CatalogDetailSerializer.Meta.fields + (
            "code", "centerType", "legacyFolio", "isExternal",
            "address", "postalCode", "neighborhood", "municipality", "state", "city", "phone",
        )


_CENTRO_WRITE_EXTRA = (
    "code", "centerType", "legacyFolio", "isExternal",
    "address", "postalCode", "neighborhood", "municipality", "state", "city", "phone",
)

class CatCentroAtencionWriteSerializer(CatalogWriteSerializer):
    code = serializers.CharField()
    centerType = serializers.CharField(source="center_type")
    legacyFolio = serializers.CharField(source="legacy_folio", required=False, allow_null=True, allow_blank=True)
    isExternal = serializers.BooleanField(source="is_external", required=False)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    postalCode = serializers.CharField(source="postal_code", required=False, allow_null=True, allow_blank=True)
    neighborhood = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    municipality = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    state = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    city = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta(CatalogWriteSerializer.Meta):
        model = CatCentroAtencion
        fields = CatalogWriteSerializer.Meta.fields + _CENTRO_WRITE_EXTRA

    def validate_center_type(self, value):
        valid = set(CatCentroAtencion.TipoCentro.values)
        if value not in valid:
            raise serializers.ValidationError(
                f"El tipo de centro debe ser uno de: {', '.join(valid)}."
            )
        return value


    def validate_postal_code(self, value):
        if value and (not value.isdigit() or len(value) != 5):
            raise serializers.ValidationError("El código postal debe tener 5 dígitos.")
        return value


# ---------------------------------------------------------------------------
# CatCentroAtencionHorario
# ---------------------------------------------------------------------------

class _HorarioReadMixin(serializers.Serializer):
    """Campos de lectura compartidos entre List y Detail de horario."""
    center = serializers.SerializerMethodField()
    shift = serializers.SerializerMethodField()
    weekDay = serializers.IntegerField(source="week_day")
    isOpen = serializers.BooleanField(source="is_open")
    is24Hours = serializers.BooleanField(source="is_24_hours")
    openingTime = serializers.TimeField(source="opening_time", allow_null=True)
    closingTime = serializers.TimeField(source="closing_time", allow_null=True)

    def get_center(self, obj):
        return build_catalog_ref(obj.center_id, CatCentroAtencion.objects)

    def get_shift(self, obj):
        return build_catalog_ref(obj.shift_id, Turnos.objects)


class CatCentroAtencionHorarioListSerializer(_HorarioReadMixin, serializers.ModelSerializer):
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = CatCentroAtencionHorario
        fields = ("id", "center", "shift", "weekDay", "isOpen", "is24Hours", "openingTime", "closingTime", "isActive")


class CatCentroAtencionHorarioDetailSerializer(AuditFieldsMixin, _HorarioReadMixin, serializers.ModelSerializer):
    observations = serializers.CharField(allow_null=True, allow_blank=True)
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = CatCentroAtencionHorario
        fields = (
            "id", "center", "shift", "weekDay", "isOpen", "is24Hours",
            "openingTime", "closingTime", "observations", "isActive",
            "createdAt", "createdBy", "updatedAt", "updatedBy",
        )


class CatCentroAtencionHorarioWriteSerializer(serializers.ModelSerializer):
    centerId = serializers.IntegerField(source="center_id")
    shiftId = serializers.IntegerField(source="shift_id")
    weekDay = serializers.IntegerField(source="week_day")
    isOpen = serializers.BooleanField(source="is_open")
    is24Hours = serializers.BooleanField(source="is_24_hours", required=False)
    openingTime = serializers.TimeField(source="opening_time", required=False, allow_null=True)
    closingTime = serializers.TimeField(source="closing_time", required=False, allow_null=True)
    observations = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = CatCentroAtencionHorario
        fields = (
            "centerId", "shiftId", "weekDay",
            "isOpen", "is24Hours",
            "openingTime", "closingTime",
            "observations", "isActive"
        )

    def validate_week_day(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError("El día de la semana debe estar entre 1 y 7.")
        return value

    def validate(self, attrs):
        is_open = attrs.get("is_open", True)
        is_24h = attrs.get("is_24_hours", False)
        opening = attrs.get("opening_time")
        closing = attrs.get("closing_time")

        # Tus validaciones actuales
        if not is_open:
            if is_24h:
                raise serializers.ValidationError("Si el horario está cerrado, no puede ser 24 horas.")
            if opening or closing:
                raise serializers.ValidationError("Si el horario está cerrado, no debe tener hora de apertura ni cierre.")

        elif is_24h:
            if opening or closing:
                raise serializers.ValidationError("Si el horario es 24 horas, no debe incluir horas de apertura o cierre.")

        else:
            if not opening or not closing:
                raise serializers.ValidationError("Debe capturar hora de apertura y hora de cierre.")
            if opening >= closing:
                raise serializers.ValidationError("La hora de apertura debe ser menor que la hora de cierre.")

        # NUEVO: Validación del modelo (clean)
        model_fields = {f.name for f in CatCentroAtencionHorario._meta.get_fields()}
        instance_data = {k: v for k, v in attrs.items() if k in model_fields}

        instance = CatCentroAtencionHorario(**instance_data)

        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

        return attrs


# ---------------------------------------------------------------------------
# Código postal
# ---------------------------------------------------------------------------

class CodigoPostalResultSerializer(serializers.Serializer):
    codigoPostal = serializers.CharField(source="codigo_postal")
    colonia = serializers.CharField()
    tipoAsentamiento = serializers.CharField(source="tipo_asentamiento")
    municipio = serializers.CharField()
    estado = serializers.CharField()
    ciudad = serializers.CharField()
    zona = serializers.CharField()


# ---------------------------------------------------------------------------
# Catálogos simples — patrón repetitivo colapsado
# ---------------------------------------------------------------------------

class AreasListSerializer(CatalogListWithCodeSerializer):
    class Meta(CatalogListWithCodeSerializer.Meta):
        model = Areas

class AreasDetailSerializer(CatalogDetailWithCodeSerializer):
    tipoArea = CatalogRefSerializer(source="tipo_area", read_only=True)

    class Meta(CatalogDetailWithCodeSerializer.Meta):
        model = Areas
        fields = CatalogDetailWithCodeSerializer.Meta.fields + ("tipoArea",)

class AreasWriteSerializer(CatalogWriteSerializer):
    idTipoArea = serializers.IntegerField(source="tipo_area_id")

    class Meta(CatalogWriteSerializer.Meta):
        model = Areas
        fields = ("name", "code", "idTipoArea", "isActive")


class BajasListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Bajas

class BajasDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Bajas

class BajasWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Bajas


class CalidadLaboralListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = CalidadLaboral

class CalidadLaboralDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = CalidadLaboral

class CalidadLaboralWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = CalidadLaboral
        fields = ("id",) + CatalogWriteSerializer.Meta.fields


class DiscapacidadesListSerializer(CatalogListWithCodeSerializer):
    class Meta(CatalogListWithCodeSerializer.Meta):
        model = Discapacidades

class DiscapacidadesDetailSerializer(CatalogDetailWithCodeSerializer):
    class Meta(CatalogDetailWithCodeSerializer.Meta):
        model = Discapacidades

class DiscapacidadesWriteSerializer(CatalogWriteSerializer):
    code = serializers.CharField()
    class Meta(CatalogWriteSerializer.Meta):
        model = Discapacidades
        fields = ("name", "code", "isActive")


class Cie9McListSerializer(CatalogListWithCodeSerializer):
    class Meta(CatalogListWithCodeSerializer.Meta):
        model = CatCie9Mc

class Cie9McDetailSerializer(CatalogDetailWithCodeSerializer):
    class Meta(CatalogDetailWithCodeSerializer.Meta):
        model = CatCie9Mc

class Cie9McWriteSerializer(CatalogWriteSerializer):
    code = serializers.CharField()
    class Meta(CatalogWriteSerializer.Meta):
        model = CatCie9Mc
        fields = ("name", "code", "isActive")


class EdoCivilListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = EdoCivil

class EdoCivilDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = EdoCivil

class EdoCivilWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = EdoCivil


class SucursalListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = CatSucursal

class SucursalDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = CatSucursal

class SucursalWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = CatSucursal


class EnfermedadesListSerializer(CatalogListWithCodeSerializer):
    cieVersion = serializers.CharField(source="cie_version")
    class Meta(CatalogListWithCodeSerializer.Meta):
        model = Enfermedades
        fields = CatalogListWithCodeSerializer.Meta.fields + ("cieVersion",)

class EnfermedadesDetailSerializer(CatalogDetailWithCodeSerializer):
    cieVersion = serializers.CharField(source="cie_version")
    class Meta(CatalogDetailWithCodeSerializer.Meta):
        model = Enfermedades
        fields = CatalogDetailWithCodeSerializer.Meta.fields + ("cieVersion",)

class EnfermedadesWriteSerializer(CatalogWriteSerializer):
    cieVersion = serializers.CharField(source="cie_version")
    class Meta(CatalogWriteSerializer.Meta):
        model = Enfermedades
        fields = CatalogWriteSerializer.Meta.fields + ("code", "cieVersion")


class EscolaridadListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Escolaridad

class EscolaridadDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Escolaridad

class EscolaridadWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Escolaridad


class TipoPersonalListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = CatTipoPersonal

class TipoPersonalDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = CatTipoPersonal

class TipoPersonalWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = CatTipoPersonal


class EscuelasListSerializer(CatalogListWithCodeSerializer):
    class Meta(CatalogListWithCodeSerializer.Meta):
        model = Escuelas

class EscuelasDetailSerializer(CatalogDetailWithCodeSerializer):
    class Meta(CatalogDetailWithCodeSerializer.Meta):
        model = Escuelas

class EscuelasWriteSerializer(CatalogWriteSerializer):
    code = serializers.CharField()
    class Meta(CatalogWriteSerializer.Meta):
        model = Escuelas
        fields = ("name", "code", "isActive")


class EspecialidadesListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Especialidades

class EspecialidadesDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Especialidades

class EspecialidadesWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Especialidades


class EstudiosMedListSerializer(CatalogListSerializer):
    studyType = serializers.CharField(source="study_type")
    precio = serializers.DecimalField(
        source="code", max_digits=18, decimal_places=2, allow_null=True, required=False,
    )
    isGeneral = serializers.SerializerMethodField()
    isAuthorized = serializers.SerializerMethodField()
    groupType = serializers.IntegerField(source="group_type", allow_null=True, required=False)
    providerId = serializers.IntegerField(source="provider_id", allow_null=True, required=False)

    class Meta(CatalogListSerializer.Meta):
        model = EstudiosMed
        fields = CatalogListSerializer.Meta.fields + (
            "studyType", "indication", "precio", "isGeneral", "isAuthorized", "groupType", "providerId",
        )

    def get_isGeneral(self, obj):
        return obj.is_general == "S"

    def get_isAuthorized(self, obj):
        return obj.is_authorized == "S"


class EstudiosMedDetailSerializer(CatalogDetailSerializer):
    studyType = serializers.CharField(source="study_type")
    precio = serializers.DecimalField(
        source="code", max_digits=18, decimal_places=2, allow_null=True, required=False,
    )
    isGeneral = serializers.SerializerMethodField()
    isAuthorized = serializers.SerializerMethodField()
    groupType = serializers.IntegerField(source="group_type", allow_null=True, required=False)
    providerId = serializers.IntegerField(source="provider_id", allow_null=True, required=False)

    class Meta(CatalogDetailSerializer.Meta):
        model = EstudiosMed
        fields = CatalogDetailSerializer.Meta.fields + (
            "studyType", "indication", "precio", "isGeneral", "isAuthorized", "groupType", "providerId",
        )

    def get_isGeneral(self, obj):
        return obj.is_general == "S"

    def get_isAuthorized(self, obj):
        return obj.is_authorized == "S"


class EstudiosMedWriteSerializer(CatalogWriteSerializer):
    studyType = serializers.CharField(source="study_type")
    precio = serializers.DecimalField(
        source="code", max_digits=18, decimal_places=2, allow_null=True, required=False,
    )
    isGeneral = serializers.BooleanField(required=False)
    isAuthorized = serializers.BooleanField(required=False)
    groupType = serializers.IntegerField(source="group_type", allow_null=True, required=False)
    providerId = serializers.IntegerField(source="provider_id", allow_null=True, required=False)

    class Meta(CatalogWriteSerializer.Meta):
        model = EstudiosMed
        fields = CatalogWriteSerializer.Meta.fields + (
            "studyType", "indication", "precio", "isGeneral", "isAuthorized", "groupType", "providerId",
        )

    @staticmethod
    def _pop_flags(validated_data):
        flags = {}
        if "isGeneral" in validated_data:
            flags["is_general"] = "S" if validated_data.pop("isGeneral") else "N"
        if "isAuthorized" in validated_data:
            flags["is_authorized"] = "S" if validated_data.pop("isAuthorized") else "N"
        return flags

    def create(self, validated_data):
        flags = self._pop_flags(validated_data)
        instance = super().create(validated_data)
        if flags:
            for attr, value in flags.items():
                setattr(instance, attr, value)
            instance.save(update_fields=list(flags.keys()))
        return instance

    def update(self, instance, validated_data):
        flags = self._pop_flags(validated_data)
        instance = super().update(instance, validated_data)
        if flags:
            for attr, value in flags.items():
                setattr(instance, attr, value)
            instance.save(update_fields=list(flags.keys()))
        return instance


class GruposDeMedicamentosListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = GruposDeMedicamentos

class GruposDeMedicamentosDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = GruposDeMedicamentos

class GruposDeMedicamentosWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = GruposDeMedicamentos


class MedicamentosListSerializer(CatalogListSerializer):
    genericName = serializers.CharField(
        source="generic_name", allow_null=True, required=False,
    )
    presentation = serializers.CharField(allow_null=True, required=False)
    cuadroBasico = serializers.ChoiceField(
        source="cuadro_basico", choices=Medicamentos.CuadroBasico.choices,
    )
    isControlled = serializers.BooleanField(source="is_controlled")
    maxQuantity = serializers.IntegerField(
        source="max_quantity", allow_null=True, required=False,
    )

    class Meta(CatalogListSerializer.Meta):
        model = Medicamentos
        fields = CatalogListSerializer.Meta.fields + (
            "genericName", "presentation", "cuadroBasico", "isControlled", "maxQuantity",
        )


class MedicamentosDetailSerializer(CatalogDetailSerializer):
    genericName = serializers.CharField(
        source="generic_name", allow_null=True, required=False,
    )
    presentation = serializers.CharField(allow_null=True, required=False)
    cuadroBasico = serializers.ChoiceField(
        source="cuadro_basico", choices=Medicamentos.CuadroBasico.choices,
    )
    isControlled = serializers.BooleanField(source="is_controlled")
    maxQuantity = serializers.IntegerField(
        source="max_quantity", allow_null=True, required=False,
    )

    class Meta(CatalogDetailSerializer.Meta):
        model = Medicamentos
        fields = CatalogDetailSerializer.Meta.fields + (
            "genericName", "presentation", "cuadroBasico", "isControlled", "maxQuantity",
        )


class MedicamentosWriteSerializer(CatalogWriteSerializer):
    genericName = serializers.CharField(
        source="generic_name", allow_null=True, required=False,
    )
    presentation = serializers.CharField(allow_null=True, required=False)
    cuadroBasico = serializers.ChoiceField(
        source="cuadro_basico", choices=Medicamentos.CuadroBasico.choices, required=False,
    )
    isControlled = serializers.BooleanField(source="is_controlled", required=False)
    maxQuantity = serializers.IntegerField(
        source="max_quantity", allow_null=True, required=False,
    )

    class Meta(CatalogWriteSerializer.Meta):
        model = Medicamentos
        fields = CatalogWriteSerializer.Meta.fields + (
            "genericName", "presentation", "cuadroBasico", "isControlled", "maxQuantity",
        )


class LicenciasListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Licencias

class LicenciasDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Licencias

class LicenciasWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Licencias


class OcupacionesListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Ocupaciones

class OcupacionesDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Ocupaciones

class OcupacionesWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Ocupaciones


class OrigenConsListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = OrigenCons

class OrigenConsDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = OrigenCons

class OrigenConsWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = OrigenCons
        fields = ("id",) + CatalogWriteSerializer.Meta.fields


class ParentescoListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Parentesco

class ParentescoDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Parentesco

class ParentescoWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Parentesco
        fields = ("id",) + CatalogWriteSerializer.Meta.fields


class PasesListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Pases

class PasesDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Pases

class PasesWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Pases


class TiposAreasListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = TiposAreas

class TiposAreasDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = TiposAreas

class TiposAreasWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = TiposAreas


class TipoDeCitasListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = TipoDeCitas

class TipoDeCitasDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = TipoDeCitas

class TipoDeCitasWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = TipoDeCitas


class TipoConsultaListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = TipoConsulta

class TipoConsultaDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = TipoConsulta

class TipoConsultaWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = TipoConsulta


class ReligionListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Religion

class ReligionDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Religion

class ReligionWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Religion


class TipoResidenciaListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = TipoResidencia

class TipoResidenciaDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = TipoResidencia

class TipoResidenciaWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = TipoResidencia


class MotivoCitaListSerializer(CatalogListSerializer):
    aplicaA = serializers.CharField(source="aplica_a")

    class Meta(CatalogListSerializer.Meta):
        model = MotivoCita
        fields = CatalogListSerializer.Meta.fields + ("aplicaA",)

class MotivoCitaDetailSerializer(CatalogDetailSerializer):
    aplicaA = serializers.CharField(source="aplica_a")

    class Meta(CatalogDetailSerializer.Meta):
        model = MotivoCita
        fields = CatalogDetailSerializer.Meta.fields + ("aplicaA",)

class MotivoCitaWriteSerializer(CatalogWriteSerializer):
    aplicaA = serializers.ChoiceField(source="aplica_a", choices=MotivoCita.AplicaA.choices, required=False)

    class Meta(CatalogWriteSerializer.Meta):
        model = MotivoCita
        fields = CatalogWriteSerializer.Meta.fields + ("aplicaA",)


class TiposSanguineoListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = TiposSanguineo

class TiposSanguineoDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = TiposSanguineo

class TiposSanguineoWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = TiposSanguineo


class TpAutorizacionListSerializer(CatalogListWithCodeSerializer):
    class Meta(CatalogListWithCodeSerializer.Meta):
        model = TpAutorizacion

class TpAutorizacionDetailSerializer(CatalogDetailWithCodeSerializer):
    class Meta(CatalogDetailWithCodeSerializer.Meta):
        model = TpAutorizacion

class TpAutorizacionWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = TpAutorizacion
        fields = CatalogWriteSerializer.Meta.fields + ("code",)


class TurnosListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Turnos

class TurnosDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Turnos

class TurnosWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Turnos


# ---------------------------------------------------------------------------
# Vacunas
# ---------------------------------------------------------------------------

class VacunasListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Vacunas

class VacunasDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = Vacunas

class VacunasWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = Vacunas


# ---------------------------------------------------------------------------
# Consultorios
# ---------------------------------------------------------------------------

class ConsultoriosListSerializer(CatalogListSerializer):
    centerId   = serializers.IntegerField(source="id_center_id",       read_only=True)
    centerName = serializers.CharField(source="id_center.name",        read_only=True, default=None)
    turnName   = serializers.CharField(source="id_turn.name",          read_only=True, default=None)

    class Meta(CatalogListSerializer.Meta):
        model = Consultorios
        fields = CatalogListSerializer.Meta.fields + ("numero", "centerId", "centerName", "turnName")

class ConsultoriosDetailSerializer(CatalogDetailSerializer):
    turn = CatalogRefSerializer(source="id_turn", read_only=True)
    center = CatalogRefSerializer(source="id_center", read_only=True)

    class Meta(CatalogDetailSerializer.Meta):
        model = Consultorios
        fields = CatalogDetailSerializer.Meta.fields + ("numero", "turn", "center")

class ConsultoriosWriteSerializer(CatalogWriteSerializer):
    numero = serializers.IntegerField()
    idTurn = serializers.IntegerField(source="id_turn_id")
    idCenter = serializers.IntegerField(source="id_center_id")

    class Meta(CatalogWriteSerializer.Meta):
        model = Consultorios
        fields = CatalogWriteSerializer.Meta.fields + ("numero", "idTurn", "idCenter")


# ---------------------------------------------------------------------------
# Autorizadores
# ---------------------------------------------------------------------------

class AutorizadoresListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = Autorizadores

class AutorizadoresDetailSerializer(CatalogDetailSerializer):
    center = serializers.SerializerMethodField()
    authorizationType = serializers.SerializerMethodField()
    signatureImage = serializers.CharField(source="signature_image", allow_null=True, required=False, allow_blank=True)
    user = serializers.SerializerMethodField()
    fileNumber = serializers.CharField(source="file_number", allow_null=True, required=False, allow_blank=True)

    def get_center(self, obj):
        return build_catalog_ref(obj.center_id, CatCentroAtencion.objects)

    def get_authorizationType(self, obj):
        return build_catalog_ref(obj.authorization_type_id, TpAutorizacion.objects)

    def get_user(self, obj):
        return build_user_ref(obj.user_id)

    class Meta(CatalogDetailSerializer.Meta):
        model = Autorizadores
        fields = CatalogDetailSerializer.Meta.fields + (
            "position", "center", "authorizationType", "signatureImage", "user", "fileNumber",
        )

class AutorizadoresWriteSerializer(CatalogWriteSerializer):
    centerId = serializers.IntegerField(source="center_id")
    authorizationTypeId = serializers.IntegerField(source="authorization_type_id")
    signatureImage = serializers.CharField(source="signature_image", allow_null=True, required=False, allow_blank=True)
    authorizerPassword = serializers.CharField(source="authorizer_password", write_only=True)
    userId = serializers.IntegerField(source="user_id")
    fileNumber = serializers.CharField(source="file_number", allow_null=True, required=False, allow_blank=True)

    class Meta(CatalogWriteSerializer.Meta):
        model = Autorizadores
        fields = CatalogWriteSerializer.Meta.fields + (
            "centerId", "position", "authorizationTypeId", "signatureImage", "authorizerPassword", "userId", "fileNumber",
        )


# ---------------------------------------------------------------------------
# Permisos (modelo con campos renombrados)
# ---------------------------------------------------------------------------

class PermisosListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_permiso")
    name = serializers.CharField(source="descripcion")
    code = serializers.CharField(source="codigo")
    isActive = serializers.BooleanField(source="is_active")
    isSystem = serializers.BooleanField(source="es_sistema")

    class Meta:
        model = Permisos
        fields = ("id", "name", "code", "isActive", "isSystem")

class PermisosDetailSerializer(AuditFieldsMixin, serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_permiso")
    name = serializers.CharField(source="descripcion")
    code = serializers.CharField(source="codigo")
    description = serializers.CharField(source="descripcion")
    isActive = serializers.BooleanField(source="is_active")
    isSystem = serializers.BooleanField(source="es_sistema")

    class Meta:
        model = Permisos
        fields = ("id", "name", "code", "description", "isActive", "isSystem", "createdAt", "createdBy", "updatedAt", "updatedBy")

class PermisosWriteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="descripcion")
    code = serializers.CharField(source="codigo")
    isActive = serializers.BooleanField(source="is_active", required=False)
    isSystem = serializers.BooleanField(source="es_sistema", required=False)

    class Meta:
        model = Permisos
        fields = ("name", "code", "isActive", "isSystem")

    def validate_code(self, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]*(:[a-z][a-z0-9_]*){1,4}", value):
            raise serializers.ValidationError(
                "El codigo debe seguir el formato modulo:submodulo:accion "
                "(minusculas, numeros y guion bajo, separados por ':')."
            )
        if Permisos.objects.filter(codigo=value).exists():
            raise serializers.ValidationError("Ya existe un permiso con ese codigo.")
        return value


# ---------------------------------------------------------------------------
# Roles (modelo con campos renombrados)
# ---------------------------------------------------------------------------

class RolesListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_rol")
    name = serializers.CharField(source="rol")
    description = serializers.CharField(source="desc_rol")
    isActive = serializers.BooleanField(source="is_active")
    isSystem = serializers.BooleanField(source="es_sistema")
    landingRoute = serializers.CharField(source="landing_route", allow_null=True)

    class Meta:
        model = Roles
        fields = ("id", "name", "description", "isActive", "isSystem", "landingRoute")

class RolesDetailSerializer(AuditFieldsMixin, serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_rol")
    name = serializers.CharField(source="rol")
    description = serializers.CharField(source="desc_rol")
    landingRoute = serializers.CharField(source="landing_route", allow_null=True)
    isActive = serializers.BooleanField(source="is_active")
    isAdmin = serializers.BooleanField(source="is_admin")
    isSystem = serializers.BooleanField(source="es_sistema")

    class Meta:
        model = Roles
        fields = ("id", "name", "description", "landingRoute", "isActive", "isAdmin", "isSystem", "createdAt", "createdBy", "updatedAt", "updatedBy")

class RolesWriteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="rol")
    description = serializers.CharField(source="desc_rol")
    landingRoute = serializers.CharField(source="landing_route", required=False, allow_null=True, allow_blank=True)
    isActive = serializers.BooleanField(source="is_active", required=False)
    isAdmin = serializers.BooleanField(source="is_admin", required=False)
    isSystem = serializers.BooleanField(source="es_sistema", required=False)

    class Meta:
        model = Roles
        fields = ("name", "description", "landingRoute", "isActive", "isAdmin", "isSystem")


# ---------------------------------------------------------------------------
# CatCies
# ---------------------------------------------------------------------------

class CatCiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatCies
        fields = "__all__"
        read_only_fields = ["code"]


# ---------------------------------------------------------------------------
# CatCentroAtencionExcepcion
# ---------------------------------------------------------------------------

class CatCentroAtencionExcepcionListSerializer(serializers.ModelSerializer):
    centerId = serializers.IntegerField(source="center_id")
    date = serializers.DateField()
    tipo = serializers.CharField()
    reason = serializers.CharField()
    openingTime = serializers.TimeField(source="opening_time", allow_null=True)
    closingTime = serializers.TimeField(source="closing_time", allow_null=True)
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = CatCentroAtencionExcepcion
        fields = (
            "id", "centerId", "date", "tipo", "reason",
            "openingTime", "closingTime", "isActive",
        )


class CatCentroAtencionExcepcionDetailSerializer(AuditFieldsMixin, serializers.ModelSerializer):
    centerId = serializers.IntegerField(source="center_id")
    date = serializers.DateField()
    tipo = serializers.CharField()
    reason = serializers.CharField()
    openingTime = serializers.TimeField(source="opening_time", allow_null=True)
    closingTime = serializers.TimeField(source="closing_time", allow_null=True)
    isActive = serializers.BooleanField(source="is_active")

    class Meta:
        model = CatCentroAtencionExcepcion
        fields = (
            "id", "centerId", "date", "tipo", "reason",
            "openingTime", "closingTime", "isActive",
            "createdAt", "createdBy", "updatedAt", "updatedBy",
        )


class CatCentroAtencionExcepcionWriteSerializer(serializers.ModelSerializer):
    centerId = serializers.IntegerField(source="center_id")
    date = serializers.DateField()
    tipo = serializers.ChoiceField(choices=CatCentroAtencionExcepcion.TIPO_CHOICES)
    reason = serializers.CharField(max_length=255)
    openingTime = serializers.TimeField(source="opening_time", required=False, allow_null=True)
    closingTime = serializers.TimeField(source="closing_time", required=False, allow_null=True)
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = CatCentroAtencionExcepcion
        fields = (
            "centerId", "date", "tipo", "reason",
            "openingTime", "closingTime", "isActive",
        )

    def validate(self, attrs):
        tipo = attrs.get("tipo")
        opening = attrs.get("opening_time")
        closing = attrs.get("closing_time")

        if tipo == CatCentroAtencionExcepcion.TIPO_HORARIO_MODIFICADO:
            if not opening or not closing:
                raise serializers.ValidationError(
                    "El tipo Horario modificado requiere hora de apertura y hora de cierre."
                )
            if opening >= closing:
                raise serializers.ValidationError(
                    "La hora de apertura debe ser anterior a la hora de cierre."
                )
        else:
            if opening or closing:
                raise serializers.ValidationError(
                    "Solo el tipo Horario modificado puede incluir horas de apertura y cierre."
                )

        # Delegate to model.clean() for any additional validation
        instance_data = {
            "center_id": attrs.get("center_id"),
            "date": attrs.get("date"),
            "tipo": tipo,
            "reason": attrs.get("reason", ""),
            "opening_time": opening,
            "closing_time": closing,
            "is_active": attrs.get("is_active", True),
        }
        instance = CatCentroAtencionExcepcion(**instance_data)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        return attrs


# ---------------------------------------------------------------------------
# CatAreaClinica
# ---------------------------------------------------------------------------

class CatAreaClinicaListSerializer(CatalogListSerializer):
    class Meta(CatalogListSerializer.Meta):
        model = CatAreaClinica


class CatAreaClinicaDetailSerializer(CatalogDetailSerializer):
    class Meta(CatalogDetailSerializer.Meta):
        model = CatAreaClinica


class CatAreaClinicaWriteSerializer(CatalogWriteSerializer):
    class Meta(CatalogWriteSerializer.Meta):
        model = CatAreaClinica


# ---------------------------------------------------------------------------
# CentroAreaClinica
# ---------------------------------------------------------------------------

class _CentroAreaClinicaReadMixin(serializers.Serializer):
    center = serializers.SerializerMethodField()
    areaClinica = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source="is_active")

    def get_center(self, obj):
        return build_catalog_ref(obj.center_id, CatCentroAtencion.objects)

    def get_areaClinica(self, obj):
        return build_catalog_ref(obj.area_clinica_id, CatAreaClinica.objects)


class CentroAreaClinicaListSerializer(_CentroAreaClinicaReadMixin, serializers.ModelSerializer):
    class Meta:
        model = CentroAreaClinica
        fields = ("center", "areaClinica", "isActive")


class CentroAreaClinicaDetailSerializer(AuditFieldsMixin, _CentroAreaClinicaReadMixin, serializers.ModelSerializer):
    class Meta:
        model = CentroAreaClinica
        fields = ("center", "areaClinica", "isActive", "createdAt", "createdBy", "updatedAt", "updatedBy")


class CentroAreaClinicaWriteSerializer(serializers.ModelSerializer):
    centerId = serializers.IntegerField(source="center_id")
    areaClinicaId = serializers.IntegerField(source="area_clinica_id")
    isActive = serializers.BooleanField(source="is_active", required=False)

    class Meta:
        model = CentroAreaClinica
        fields = ("centerId", "areaClinicaId", "isActive")

    def update(self, instance, validated_data):
        # Django uses only center_id (the declared PK) in the WHERE clause of UPDATE,
        # ignoring area_clinica_id. This causes a UniqueViolation when a center has
        # multiple areas. Filter by both columns explicitly instead.
        validated_data.pop("center_id", None)
        validated_data.pop("area_clinica_id", None)
        CentroAreaClinica.objects.filter(
            center_id=instance.center_id,
            area_clinica_id=instance.area_clinica_id,
        ).update(**validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        return instance