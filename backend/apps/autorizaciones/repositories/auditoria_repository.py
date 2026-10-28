"""Consultas de la auditoria de solicitudes (solo lectura)."""
from django.db.models import Count, F, Q

from apps.authentication.models import SyUsuario

from ..models import Solicitud, SolicitudDecision, SolicitudDestinatario, SolicitudTransicion


class AuditoriaRepository:
    @staticmethod
    def solicitudes(*, fecha_desde=None, fecha_hasta=None, clave_tipo=None, id_centro=None, estatus=None,
                    id_autorizador=None):
        consulta = (
            Solicitud.objects.select_related("tipo_autorizacion", "centro_atencion", "motivo_cierre")
            .annotate(
                total_items=Count("items", filter=Q(items__esta_activo=True), distinct=True),
                # Solo cuentan las aprobaciones firmadas sobre el contenido vigente.
                total_aprobaciones=Count(
                    "decisiones",
                    filter=Q(decisiones__decision="APROBAR", decisiones__hash_contenido=F("hash_contenido")),
                    distinct=True,
                ),
            )
            .order_by("-fecha_creacion", "-pk")
        )
        if fecha_desde:
            consulta = consulta.filter(fecha_creacion__date__gte=fecha_desde)
        if fecha_hasta:
            consulta = consulta.filter(fecha_creacion__date__lte=fecha_hasta)
        if clave_tipo:
            consulta = consulta.filter(tipo_autorizacion__clave=clave_tipo)
        if id_centro:
            consulta = consulta.filter(centro_atencion_id=id_centro)
        if estatus:
            consulta = consulta.filter(estatus=estatus)
        if id_autorizador:
            consulta = consulta.filter(decisiones__autorizador_id=id_autorizador).distinct()
        return consulta

    @staticmethod
    def solicitud(uuid_publico):
        return (
            Solicitud.objects.select_related("tipo_autorizacion", "centro_atencion", "motivo_cierre")
            .annotate(total_items=Count("items", filter=Q(items__esta_activo=True), distinct=True))
            .filter(uuid_publico=uuid_publico)
            .first()
        )

    @staticmethod
    def transiciones(solicitud):
        return list(SolicitudTransicion.objects.filter(solicitud=solicitud).order_by("fecha_evento", "pk"))

    @staticmethod
    def decisiones(solicitud):
        return list(
            SolicitudDecision.objects.filter(solicitud=solicitud)
            .select_related("motivo")
            .order_by("fecha_firma", "pk")
        )

    @staticmethod
    def destinatarios(solicitud):
        return list(
            SolicitudDestinatario.objects.filter(solicitud=solicitud)
            .select_related("autorizador")
            .order_by("fecha_envio", "pk")
        )

    @staticmethod
    def nombres(ids_usuario) -> dict[int, str]:
        ids = {i for i in ids_usuario if i}
        if not ids:
            return {}
        return {
            u.pk: (getattr(getattr(u, "detalle", None), "nombre_completo", None) or u.usuario)
            for u in SyUsuario.objects.filter(pk__in=ids).select_related("detalle")
        }
