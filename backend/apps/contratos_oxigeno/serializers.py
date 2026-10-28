from rest_framework import serializers

from apps.administracion.services.fecha_service import calcular_edad
from apps.catalogos.models import CatSucursal, Especialidades
from apps.consulta_medica.services.paciente_entrada import llave_publica
from .models import ContratoOxigeno


class SucursalNombreField(serializers.SlugRelatedField):
    """Lee/escribe la sucursal por nombre (no por id) para no romper el
    contrato de API que el frontend ya conoce -- por dentro sigue siendo
    una FK real a catalogos.CatSucursal."""

    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "name")
        kwargs.setdefault("queryset", CatSucursal.objects.all())
        super().__init__(**kwargs)


class EspecialidadNombreField(serializers.SlugRelatedField):
    """Mismo patrón que SucursalNombreField, pero opcional: especialidad es
    blank/null (a diferencia de sucursal). El combobox del frontend manda
    "" al limpiar la selección -- eso debe resolver a None, no disparar un
    lookup contra el catálogo con nombre vacío."""

    def __init__(self, **kwargs):
        kwargs.setdefault("slug_field", "name")
        kwargs.setdefault("queryset", Especialidades.objects.all())
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not data:
            return None
        return super().to_internal_value(data)


class ContratoOxigenoSerializer(serializers.ModelSerializer):
    # ── camelCase para el frontend ────────────────────────────────────────────
    sucursal      = SucursalNombreField()
    especialidad  = EspecialidadNombreField()
    numContrato   = serializers.CharField(source="num_contrato")
    tpDer         = serializers.CharField(source="tp_der")
    servicio2     = serializers.CharField(source="servicio_2", allow_blank=True, allow_null=True, required=False)
    servicio3     = serializers.CharField(source="servicio_3", allow_blank=True, allow_null=True, required=False)
    tpDerLabel    = serializers.SerializerMethodField()
    fechaSoporte  = serializers.DateField(source="fecha_soporte",  allow_null=True, required=False)
    vigenciaMeses = serializers.IntegerField(source="vigencia_meses", allow_null=True, required=False)
    vigenciaDias  = serializers.IntegerField(source="vigencia_dias",  allow_null=True, required=False)
    fechaRenovar  = serializers.DateField(source="fecha_renovar",  allow_null=True, required=False)
    diasFaltan    = serializers.IntegerField(source="dias_faltan",  read_only=True,  allow_null=True)
    statusLabel   = serializers.SerializerMethodField()
    fchAlta       = serializers.DateTimeField(source="fch_alta", read_only=True)
    fchModf       = serializers.DateTimeField(source="fch_modf", read_only=True)
    pkNum             = serializers.IntegerField(source="pk_num", required=False)
    # Plan contraer la llave vieja: el derechohabiente elegido llega por idPaciente.
    idPaciente        = serializers.IntegerField(min_value=1, required=False, write_only=True)
    fechaNacimiento   = serializers.DateField(source="fecha_nacimiento", allow_null=True, required=False)
    vigenciaDh        = serializers.SerializerMethodField()
    edadDh            = serializers.SerializerMethodField()

    # ── Domicilio desglosado / teléfonos / datos médicos (formato de oxígeno) ──
    numExt           = serializers.CharField(source="num_ext", allow_blank=True, required=False)
    numInt           = serializers.CharField(source="num_int", allow_blank=True, required=False)
    entreCalle1      = serializers.CharField(source="entre_calle_1", allow_blank=True, required=False)
    entreCalle2      = serializers.CharField(source="entre_calle_2", allow_blank=True, required=False)
    telOficina       = serializers.CharField(source="tel_oficina", allow_blank=True, required=False)
    extTel           = serializers.CharField(source="ext_tel", allow_blank=True, required=False)
    hospitalAzura    = serializers.CharField(source="hospital_azura", allow_blank=True, required=False)
    medicoTratante   = serializers.CharField(source="medico_tratante", allow_blank=True, required=False)
    tercerNivel      = serializers.BooleanField(source="tercer_nivel", required=False)
    institucionReferencia     = serializers.CharField(source="institucion_referencia", allow_blank=True, required=False)
    medicoTratanteReferencia  = serializers.CharField(source="medico_tratante_referencia", allow_blank=True, required=False)
    tramiteSubsecuente        = serializers.BooleanField(source="tramite_subsecuente", required=False)

    def get_tpDerLabel(self, obj) -> str:        # noqa: N802
        try:
            return ContratoOxigeno.TpDer(obj.tp_der).label
        except ValueError:
            return obj.tp_der

    def get_statusLabel(self, obj) -> str:        # noqa: N802
        return obj.get_status_display()

    def _dh_info(self, obj) -> dict:
        return self.context.get("dh_info", {}).get(llave_publica(obj), {})

    def get_vigenciaDh(self, obj) -> str | None:        # noqa: N802
        return self._dh_info(obj).get("vigencia")

    def get_edadDh(self, obj):        # noqa: N802
        """Edad calculada siempre a partir de fecha_nacimiento (persistida al
        seleccionar el derechohabiente), no del no_edad del catálogo, que
        puede quedar desactualizado."""
        return calcular_edad(obj.fecha_nacimiento)

    class Meta:
        model  = ContratoOxigeno
        fields = [
            "id", "sucursal", "numContrato", "nombre", "expediente", "pkNum", "idPaciente",
            "fechaNacimiento",
            "tpDer", "tpDerLabel", "clinica", "servicio", "servicio2", "servicio3",
            "telefono",
            "fechaSoporte", "vigenciaMeses", "vigenciaDias",
            "fechaRenovar", "diasFaltan", "status", "statusLabel",
            "diagnostico", "fchAlta", "fchModf",
            "vigenciaDh", "edadDh",
            "calle", "numExt", "numInt", "colonia", "alcaldia", "cp",
            "entreCalle1", "entreCalle2", "telOficina", "celular", "extTel",
            "hospitalAzura", "medicoTratante", "especialidad", "tercerNivel",
            "institucionReferencia", "medicoTratanteReferencia", "tramiteSubsecuente",
        ]
        read_only_fields = (
            "id", "diasFaltan", "status",
            "tpDerLabel", "statusLabel",
            "fchAlta", "fchModf",
            "vigenciaDh", "edadDh",
        )
        extra_kwargs = {"expediente": {"required": False}}

    def validate(self, attrs):
        """idPaciente -> expediente + pk_num desde cns_paciente (transitorio: tambien
        se acepta el expediente directo). Un contrato nuevo necesita uno de los dos."""
        from apps.consulta_medica.services.paciente_entrada import llave_de_paciente

        attrs = super().validate(attrs)
        id_paciente = attrs.pop("idPaciente", None)
        if id_paciente is not None:
            llave = llave_de_paciente(id_paciente)
            if llave is None:
                raise serializers.ValidationError({"idPaciente": ["Paciente no encontrado."]})
            attrs["expediente"], attrs["pk_num"] = llave
        elif self.instance is None and not attrs.get("expediente"):
            raise serializers.ValidationError({"idPaciente": ["Indica el derechohabiente."]})
        return attrs
