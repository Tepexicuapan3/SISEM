"""Acceso a datos de la configuracion del modulo (tipos, reglas por centro, motivos)."""
from apps.catalogos.models import CatCentroAtencion

from ..models import Motivo, ReglaCentro, TipoAutorizacion


class ConfiguracionRepository:
    @staticmethod
    def tipos():
        return TipoAutorizacion.objects.filter(fecha_baja__isnull=True).order_by("clave")

    @staticmethod
    def tipo(id_tipo):
        if not isinstance(id_tipo, int):
            return None
        return TipoAutorizacion.objects.filter(pk=id_tipo, fecha_baja__isnull=True).first()

    @staticmethod
    def tipo_para_actualizar(id_tipo):
        return TipoAutorizacion.objects.select_for_update().filter(pk=id_tipo, fecha_baja__isnull=True).first()

    @staticmethod
    def existe_centro(id_centro):
        return isinstance(id_centro, int) and CatCentroAtencion.objects.filter(pk=id_centro).exists()

    @staticmethod
    def reglas_vigentes():
        return (
            ReglaCentro.objects.filter(esta_activo=True, fecha_baja__isnull=True)
            .select_related("tipo_autorizacion", "centro_atencion")
            .order_by("tipo_autorizacion__clave", "centro_atencion__name")
        )

    @staticmethod
    def existe_regla_vigente(id_tipo, id_centro):
        return ReglaCentro.objects.filter(
            tipo_autorizacion_id=id_tipo, centro_atencion_id=id_centro, fecha_baja__isnull=True,
        ).exists()

    @staticmethod
    def regla_para_actualizar(id_regla):
        return (
            ReglaCentro.objects.select_for_update(of=("self",))
            .select_related("tipo_autorizacion", "centro_atencion")
            .filter(pk=id_regla, esta_activo=True, fecha_baja__isnull=True)
            .first()
        )

    @staticmethod
    def motivos(ambito=None):
        consulta = Motivo.objects.all()
        if ambito:
            consulta = consulta.filter(ambito=ambito)
        return consulta.order_by("ambito", "-esta_activo", "id_motivo")

    @staticmethod
    def existe_motivo(ambito, clave):
        return Motivo.objects.filter(ambito=ambito, clave=clave).exists()

    @staticmethod
    def motivo_para_actualizar(id_motivo):
        return Motivo.objects.select_for_update().filter(pk=id_motivo).first()

    @staticmethod
    def activos_en_ambito(ambito):
        return Motivo.objects.filter(ambito=ambito, esta_activo=True).count()
