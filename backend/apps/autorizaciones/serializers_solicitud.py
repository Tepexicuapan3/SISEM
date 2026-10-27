"""Transporte de la API de solicitudes. Nunca expone la identidad del paciente:
solo folios, tipo, centro, fechas y los elementos a autorizar."""
from rest_framework import serializers

from apps.catalogos.serializers import build_user_ref

from .models import Solicitud, SolicitudDecision, SolicitudDestinatario, SolicitudItem
from .repositories.solicitud_repository import SolicitudRepository as Repo
from .uses_case.solicitud_use_case import acciones_para


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=SolicitudDecision.Decision.values)
    motivoId = serializers.IntegerField(required=False, allow_null=True, default=None)
    descripcionMotivo = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    version = serializers.IntegerField()
    # Contrasena propia para firmar: sin recortar espacios.
    credencial = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, default="")


class NotificarSerializer(serializers.Serializer):
    autorizadorIds = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    todosElegibles = serializers.BooleanField(required=False, default=False)


def construir_elegibles(solicitud: Solicitud, elegibles) -> list[dict]:
    notificados = set(
        SolicitudDestinatario.objects.filter(solicitud=solicitud).values_list("autorizador_id", flat=True)
    )
    return [
        {
            "idAutorizador": e.id_autorizador,
            "nombre": (build_user_ref(e.id_usuario) or {}).get("name", ""),
            "alcanceAplicado": e.alcance_aplicado,
            "yaNotificado": e.id_autorizador in notificados,
        }
        for e in elegibles
    ]


def _iso(valor):
    return valor.isoformat() if valor else None


def _nombre_autorizador(autorizador):
    ref = build_user_ref(autorizador.usuario_id) or {}
    return {"id": autorizador.pk, "nombre": ref.get("name", "")}


def construir_solicitud(solicitud: Solicitud, *, id_usuario: int, detalle: bool = False) -> dict:
    datos = {
        "uuid": str(solicitud.uuid_publico),
        "folio": solicitud.folio,
        "tipo": {"clave": solicitud.tipo_autorizacion.clave, "nombre": solicitud.tipo_autorizacion.nombre},
        "centro": {
            "id": solicitud.centro_atencion_id,
            "nombre": solicitud.centro_atencion.name,
            "clues": solicitud.clues,
        },
        "tipoOrigen": solicitud.tipo_origen,
        "folioOrigen": solicitud.folio_origen,
        "motivos": solicitud.motivos,
        "estatus": solicitud.estatus,
        "prioridad": solicitud.prioridad,
        "modalidad": solicitud.modalidad,
        "aprobacionesRequeridas": solicitud.aprobaciones_requeridas,
        "aprobacionesVigentes": len(Repo.ids_aprobaron_contenido_vigente(solicitud)),
        "sinElegibles": solicitud.sin_elegibles,
        "resumen": solicitud.resumen_minimo,
        "solicitadaPor": build_user_ref(solicitud.id_usuario_solicitante),
        "fechaCreacion": _iso(solicitud.fecha_creacion),
        "fechaLimite": _iso(solicitud.fecha_limite),
        "resueltaPor": build_user_ref(solicitud.id_usuario_resolucion),
        "fechaResolucion": _iso(solicitud.fecha_resolucion),
        "motivoCierre": (
            {"clave": solicitud.motivo_cierre.clave, "descripcion": solicitud.motivo_cierre.descripcion}
            if solicitud.motivo_cierre_id
            else None
        ),
        "descripcionMotivoCierre": solicitud.descripcion_motivo_cierre,
        "version": solicitud.version,
    }
    if not detalle:
        return datos

    datos["items"] = [
        {
            "tipoItem": item.tipo_item,
            "descripcion": item.descripcion,
            "cantidad": float(item.cantidad) if item.cantidad is not None else None,
            "motivo": item.motivo,
        }
        for item in SolicitudItem.objects.filter(solicitud=solicitud, esta_activo=True).order_by("pk")
    ]
    datos["destinatarios"] = [
        {
            "autorizador": _nombre_autorizador(d.autorizador),
            "estatus": d.estatus,
            "esObligatorio": d.es_obligatorio,
            "tipoSeleccion": d.tipo_seleccion,
        }
        for d in SolicitudDestinatario.objects.filter(solicitud=solicitud).select_related("autorizador").order_by("pk")
    ]
    datos["decisiones"] = [
        {
            "autorizador": _nombre_autorizador(d.autorizador),
            "decision": d.decision,
            "motivo": {"clave": d.motivo.clave, "descripcion": d.motivo.descripcion} if d.motivo_id else None,
            "descripcionMotivo": d.descripcion_motivo,
            "fechaFirma": _iso(d.fecha_firma),
            "vigente": d.hash_contenido == solicitud.hash_contenido,
        }
        for d in SolicitudDecision.objects.filter(solicitud=solicitud)
        .select_related("autorizador", "motivo")
        .order_by("pk")
    ]
    datos["acciones"] = acciones_para(solicitud, id_usuario)
    return datos
