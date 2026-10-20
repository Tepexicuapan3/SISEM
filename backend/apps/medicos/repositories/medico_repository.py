from apps.authentication.models import SyUsuario
from apps.medicos import identity
from apps.medicos.models import CatMedico, LegacyMedico


class MedicoRepository:
    @staticmethod
    def resolve(value, *, request=None, select_related=None, prefetch_related=None):
        """
        Resuelve el parámetro de ruta `/medicos/{value}/...` o un payload
        `medicoId`/`medicoSuplenteId`/`medicoTitularId` a un `CatMedico`.

        Contrato unificado (medicos-id-no-medico): `value` es SIEMPRE
        `CatMedico.pk` (No. Médico). NO hay fallback a `id_usuario`: un id de
        usuario que no sea además pk de médico devuelve None (404).
        """
        if value in (None, ""):
            return None
        try:
            pk = int(value)
        except (TypeError, ValueError):
            return None

        qs = CatMedico.objects.all()
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch_related:
            qs = qs.prefetch_related(*prefetch_related)

        return qs.filter(pk=pk).first()

    DETAIL_SELECT_RELATED = [
        "id_usuario", "id_usuario__detalle", "id_usuario__detalle__id_escuela",
    ]
    DETAIL_PREFETCH_RELATED = [
        "id_usuario__cedulas",
        "especialidades__especialidad",
        "centros__centro",
        "consultorios__consultorio__id_center",
    ]

    @classmethod
    def resolve_with_detail(cls, value, *, request=None):
        return cls.resolve(
            value,
            request=request,
            select_related=cls.DETAIL_SELECT_RELATED,
            prefetch_related=cls.DETAIL_PREFETCH_RELATED,
        )

    @staticmethod
    def list_queryset():
        return CatMedico.objects.select_related(
            "id_usuario", "id_usuario__detalle", "id_usuario__detalle__id_escuela"
        ).prefetch_related(
            "id_usuario__cedulas",
            "especialidades__especialidad",
            "centros__centro",
            "consultorios__consultorio__id_center",
        )

    @staticmethod
    def get_usuario_candidato(usuario_id):
        return SyUsuario.objects.select_related("detalle__id_tipo_personal").filter(id_usuario=usuario_id).first()

    @staticmethod
    def usuario_es_medico(usuario) -> bool:
        """Regla única: el usuario debe tener tipo_personal "Médico" (alta manual)."""
        det = getattr(usuario, "detalle", None)
        return bool(det and det.id_tipo_personal and det.id_tipo_personal.name == "Médico")

    @staticmethod
    def exists_for_usuario(usuario):
        return CatMedico.objects.filter(id_usuario=usuario).exists()

    @staticmethod
    def create(
        *,
        usuario,
        tipo_medico,
        servicio,
        observaciones,
        created_by_id,
        estatus_medico=None,
    ):
        # `usuario` es obligatorio: todo médico nace con cuenta de usuario
        # (la identidad vive en DetUsuario / DetUsuarioCedula). `id` lo asigna
        # la secuencia. `estatus_medico=None` deja el default del modelo.
        if usuario is None:
            raise ValueError("Un médico no puede crearse sin usuario.")
        kwargs = {}
        if estatus_medico is not None:
            kwargs["estatus_medico"] = estatus_medico

        return CatMedico.objects.create(
            id_usuario=usuario,
            tipo_medico=tipo_medico,
            servicio=servicio,
            observaciones=observaciones,
            created_by_id=created_by_id,
            **kwargs,
        )

    @staticmethod
    def save(medico, *, update_fields=None):
        medico.save(update_fields=update_fields)


class LegacyMedicoRepository:
    """Acceso de SOLO LECTURA al archivo `legacy_medico` (SIRES nunca escribe)."""

    @staticmethod
    def list_queryset():
        # `with_identity` trae usuario+detalle del médico vigente en el mismo
        # JOIN: evita N+1 al calcular `display_name`.
        qs = LegacyMedico.objects.select_related("medico_actual")
        return identity.with_identity(qs, prefix="medico_actual__")
