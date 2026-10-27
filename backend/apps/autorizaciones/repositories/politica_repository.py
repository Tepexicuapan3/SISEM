"""Lectura del estado vigente para la politica de autorizacion. Solo lectura:
usuarios, cedulas y centros se consultan en sus modulos dueños sin tocarlos."""
from django.db.models import F, Prefetch, Q

from apps.authentication.models import DetUsuarioCedula, SyUsuario
from apps.catalogos.models import CatCentroAtencion

from ..domain.politica import DatosAutorizador, DatosTipoAsignado
from ..models import Autorizador, AutorizadorAlcance, AutorizadorTipo

_ALCANCES_ACTIVOS = Prefetch(
    "alcances",
    queryset=AutorizadorAlcance.objects.filter(esta_activo=True, fecha_baja__isnull=True),
    to_attr="alcances_activos",
)


def _tipos_activos():
    return AutorizadorTipo.objects.filter(esta_activo=True, fecha_baja__isnull=True)


def _datos_tipo(autorizador_tipo) -> DatosTipoAsignado:
    return DatosTipoAsignado(
        id_autorizador_tipo=autorizador_tipo.pk,
        requiere_cedula=autorizador_tipo.tipo_autorizacion.requiere_cedula,
        fecha_inicio_vigencia=autorizador_tipo.fecha_inicio_vigencia,
        fecha_fin_vigencia=autorizador_tipo.fecha_fin_vigencia,
        alcances=tuple(
            (a.tipo_alcance, a.centro_atencion_id, a.tipo_centro) for a in autorizador_tipo.alcances_activos
        ),
    )


def _datos_autorizador(autorizador, autorizador_tipo, *, usuario_activo, tiene_cedula) -> DatosAutorizador:
    return DatosAutorizador(
        id_autorizador=autorizador.pk,
        estatus=autorizador.estatus,
        fecha_inicio_vigencia=autorizador.fecha_inicio_vigencia,
        fecha_fin_vigencia=autorizador.fecha_fin_vigencia,
        usuario_activo=usuario_activo,
        tiene_cedula=tiene_cedula,
        tipo=_datos_tipo(autorizador_tipo) if autorizador_tipo else None,
    )


class PoliticaRepository:
    @staticmethod
    def tipo_de_centro(id_centro):
        return CatCentroAtencion.objects.filter(pk=id_centro).values_list("center_type", flat=True).first()

    @staticmethod
    def cedula_con_la_que_firma(id_usuario):
        """La principal; si no hay principal, la primera capturada."""
        cedula = (
            DetUsuarioCedula.objects.filter(id_usuario_id=id_usuario)
            .order_by("-es_principal", "orden")
            .first()
        )
        return cedula.numero if cedula else None

    @staticmethod
    def datos_de_usuario(id_usuario, clave_tipo) -> DatosAutorizador | None:
        # El registro vigente; si solo hay registros dados de baja, el mas reciente
        # (asi la negativa dice "dado de baja" y no "no es autorizador").
        autorizador = (
            Autorizador.objects.filter(usuario_id=id_usuario)
            .order_by(F("fecha_baja").asc(nulls_first=True), "-id_autorizador")
            .first()
        )
        if autorizador is None:
            return None
        autorizador_tipo = (
            _tipos_activos()
            .filter(autorizador=autorizador, tipo_autorizacion__clave=clave_tipo)
            .select_related("tipo_autorizacion")
            .prefetch_related(_ALCANCES_ACTIVOS)
            .first()
        )
        usuario_activo = SyUsuario.objects.filter(pk=id_usuario, est_activo=True).exists()
        tiene_cedula = DetUsuarioCedula.objects.filter(id_usuario_id=id_usuario).exists()
        return _datos_autorizador(
            autorizador, autorizador_tipo, usuario_activo=usuario_activo, tiene_cedula=tiene_cedula,
        )

    @staticmethod
    def candidatos(clave_tipo, id_centro, tipo_centro, fecha):
        """Prefiltro en BD de quienes podrian cubrir el centro. La decision final
        la toma la politica sobre cada candidato (misma regla que puede_autorizar)."""
        tipos = list(
            _tipos_activos()
            .filter(
                tipo_autorizacion__clave=clave_tipo,
                autorizador__estatus=Autorizador.Estatus.ACTIVO,
                autorizador__fecha_baja__isnull=True,
                autorizador__fecha_inicio_vigencia__lte=fecha,
                autorizador__fecha_fin_vigencia__gte=fecha,
                autorizador__usuario__est_activo=True,
                alcances__esta_activo=True,
                alcances__fecha_baja__isnull=True,
            )
            .filter(
                Q(alcances__tipo_alcance="CENTRO", alcances__centro_atencion_id=id_centro)
                | Q(alcances__tipo_alcance="TIPO_CENTRO", alcances__tipo_centro=tipo_centro)
                | Q(alcances__tipo_alcance="GLOBAL")
            )
            .distinct()
            .select_related("tipo_autorizacion", "autorizador")
            .prefetch_related(_ALCANCES_ACTIVOS)
        )
        con_cedula = set(
            DetUsuarioCedula.objects.filter(
                id_usuario_id__in=[t.autorizador.usuario_id for t in tipos],
            ).values_list("id_usuario_id", flat=True)
        )
        return [
            (
                t.autorizador.usuario_id,
                _datos_autorizador(
                    t.autorizador, t, usuario_activo=True, tiene_cedula=t.autorizador.usuario_id in con_cedula,
                ),
            )
            for t in tipos
        ]
