import logging

from apps.authentication.models import SyUsuario
from apps.medicos.models import CatMedico

logger = logging.getLogger(__name__)


class MedicoRepository:
    @staticmethod
    def resolve(value, *, request=None, select_related=None, prefetch_related=None):
        """
        D7 (contrato dual, ventana de compatibilidad): resuelve el parámetro de
        ruta `/medicos/{value}/...` o un payload `medicoId`/`medicoSuplenteId`/
        `medicoTitularId` a un `CatMedico`. Intenta primero por la PK surrogate
        (`CatMedico.pk`); si no hay match, cae a `id_usuario` (comportamiento
        legacy previo al cambio medico-pk-independiente) y loguea el fallback
        -- el contador de ese WARN en logs es la métrica que habilita Fase 5
        (remover el fallback, ver design sección 5).
        """
        if value in (None, ""):
            return None

        qs = CatMedico.objects.all()
        if select_related:
            qs = qs.select_related(*select_related)
        if prefetch_related:
            qs = qs.prefetch_related(*prefetch_related)

        medico = qs.filter(pk=value).first()
        if medico is not None:
            return medico

        medico = qs.filter(id_usuario_id=value).first()
        if medico is not None:
            logger.warning(
                "MEDICO_ID_LEGACY_FALLBACK",
                extra={"value": value, "path": getattr(request, "path", None)},
            )
        return medico

    DETAIL_SELECT_RELATED = ["id_usuario", "id_usuario__detalle", "id_usuario__detalle__id_escuela"]
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
        return SyUsuario.objects.select_related("detalle").filter(id_usuario=usuario_id).first()

    @staticmethod
    def exists_for_usuario(usuario):
        return CatMedico.objects.filter(id_usuario=usuario).exists()

    @staticmethod
    def create(*, usuario=None, nombre_display=None, tipo_medico, servicio, observaciones, created_by_id):
        return CatMedico.objects.create(
            id_usuario=usuario,
            nombre_display=nombre_display,
            tipo_medico=tipo_medico,
            servicio=servicio,
            observaciones=observaciones,
            created_by_id=created_by_id,
        )

    @staticmethod
    def save(medico, *, update_fields=None):
        medico.save(update_fields=update_fields)
