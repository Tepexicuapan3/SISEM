"""Acceso a datos de solicitudes. La bandeja de cada autorizador se arma con
sus tipos y centros asignados (mismo criterio de cobertura que la politica)."""
from django.db.models import Q

from apps.catalogos.models import CatCentroAtencion

from ..models import (
    Autorizador,
    AutorizadorAlcance,
    AutorizadorTipo,
    ReglaCentro,
    Solicitud,
    SolicitudDecision,
    SolicitudDestinatario,
    SolicitudItem,
    TipoAutorizacion,
)


class SolicitudRepository:
    @staticmethod
    def tipo_por_clave(clave):
        return TipoAutorizacion.objects.filter(clave=clave, esta_activo=True, fecha_baja__isnull=True).first()

    @staticmethod
    def centro(id_centro):
        return CatCentroAtencion.objects.filter(pk=id_centro).first()

    @staticmethod
    def regla_centro(tipo_autorizacion, id_centro):
        return ReglaCentro.objects.filter(
            tipo_autorizacion=tipo_autorizacion, centro_atencion_id=id_centro, esta_activo=True, fecha_baja__isnull=True,
        ).first()

    @staticmethod
    def pendiente_por_origen_para_actualizar(tipo_origen, id_origen):
        return (
            Solicitud.objects.select_for_update(of=("self",))
            .filter(tipo_origen=tipo_origen, id_origen=id_origen, estatus=Solicitud.Estatus.PENDIENTE)
            .first()
        )

    @staticmethod
    def para_actualizar(uuid_publico):
        return (
            Solicitud.objects.select_for_update(of=("self",))
            .select_related("tipo_autorizacion")
            .filter(uuid_publico=uuid_publico)
            .first()
        )

    @staticmethod
    def obtener(uuid_publico):
        return (
            Solicitud.objects.select_related("tipo_autorizacion", "centro_atencion", "motivo_cierre")
            .filter(uuid_publico=uuid_publico)
            .first()
        )

    @staticmethod
    def ids_pendientes_vencidas(ahora):
        return list(
            Solicitud.objects.filter(estatus=Solicitud.Estatus.PENDIENTE, fecha_limite__lt=ahora)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

    @staticmethod
    def items_activos(solicitud):
        return list(SolicitudItem.objects.filter(solicitud=solicitud, esta_activo=True).order_by("pk"))

    @staticmethod
    def ids_aprobaron_contenido_vigente(solicitud):
        return set(
            SolicitudDecision.objects.filter(
                solicitud=solicitud, decision="APROBAR", hash_contenido=solicitud.hash_contenido,
            ).values_list("autorizador_id", flat=True)
        )

    @staticmethod
    def ids_obligatorios(solicitud):
        return set(
            SolicitudDestinatario.objects.filter(solicitud=solicitud, es_obligatorio=True)
            .values_list("autorizador_id", flat=True)
        )

    @staticmethod
    def ya_decidio(solicitud, id_autorizador):
        return SolicitudDecision.objects.filter(
            solicitud=solicitud, autorizador_id=id_autorizador, hash_contenido=solicitud.hash_contenido,
        ).exists()

    # ------------------------------------------------------------------ #
    # Visibilidad                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def autorizador_vigente(id_usuario):
        return Autorizador.objects.filter(usuario_id=id_usuario, fecha_baja__isnull=True).first()

    @staticmethod
    def filtro_visibles(id_usuario) -> Q:
        """Lo que un usuario puede ver: lo que origino, lo que se le envio y lo
        que cubren sus tipos y centros asignados (aunque este suspendido, para
        consulta; decidir lo vuelve a validar la politica)."""
        filtro = Q(id_usuario_solicitante=id_usuario)
        autorizador = SolicitudRepository.autorizador_vigente(id_usuario)
        if autorizador is None:
            return filtro
        filtro |= Q(destinatarios__autorizador=autorizador)
        tipos = AutorizadorTipo.objects.filter(autorizador=autorizador, esta_activo=True, fecha_baja__isnull=True)
        alcances = AutorizadorAlcance.objects.filter(
            autorizador_tipo__in=tipos, esta_activo=True, fecha_baja__isnull=True,
        ).values_list("autorizador_tipo__tipo_autorizacion_id", "tipo_alcance", "centro_atencion_id", "tipo_centro")
        for id_tipo, tipo_alcance, id_centro, tipo_centro in alcances:
            if tipo_alcance == "GLOBAL":
                filtro |= Q(tipo_autorizacion_id=id_tipo)
            elif tipo_alcance == "CENTRO":
                filtro |= Q(tipo_autorizacion_id=id_tipo, centro_atencion_id=id_centro)
            else:
                filtro |= Q(tipo_autorizacion_id=id_tipo, centro_atencion__center_type=tipo_centro)
        return filtro

    @staticmethod
    def listar_visibles(id_usuario, *, estatus=None, clave_tipo=None, id_centro=None, folio=None,
                        desde=None, hasta=None):
        ids = (
            Solicitud.objects.filter(SolicitudRepository.filtro_visibles(id_usuario))
            .values("pk")
        )
        consulta = Solicitud.objects.filter(pk__in=ids).select_related("tipo_autorizacion", "centro_atencion")
        if estatus:
            consulta = consulta.filter(estatus=estatus)
        if clave_tipo:
            consulta = consulta.filter(tipo_autorizacion__clave=clave_tipo)
        if id_centro:
            consulta = consulta.filter(centro_atencion_id=id_centro)
        if folio:
            consulta = consulta.filter(Q(folio__icontains=folio) | Q(folio_origen__icontains=folio))
        if desde:
            consulta = consulta.filter(fecha_creacion__date__gte=desde)
        if hasta:
            consulta = consulta.filter(fecha_creacion__date__lte=hasta)
        return consulta.order_by("-fecha_creacion", "-pk")

    @staticmethod
    def es_visible(solicitud, id_usuario):
        return Solicitud.objects.filter(
            Q(pk=solicitud.pk) & SolicitudRepository.filtro_visibles(id_usuario)
        ).exists()
