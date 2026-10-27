"""Transporte de la API de autorizadores: valida la FORMA de la entrada y arma
la salida en camelCase. Las reglas de negocio viven en el caso de uso."""
from django.utils import timezone
from rest_framework import serializers

from apps.catalogos.serializers import build_user_ref

from .domain.vigencia import estado_vigencia
from .models import AutorizadorAlcance
from .repositories.autorizador_repository import AutorizadorRepository as Repo


# ---------------------------------------------------------------------- #
# Entrada                                                                #
# ---------------------------------------------------------------------- #

class TipoAsignadoSerializer(serializers.Serializer):
    claveTipo = serializers.CharField(max_length=3)
    fechaInicioVigencia = serializers.DateField(required=False, allow_null=True, default=None)
    fechaFinVigencia = serializers.DateField(required=False, allow_null=True, default=None)
    # {"centros": [ids], "tiposCentro": [...], "global": bool}; el caso de uso valida el contenido.
    alcance = serializers.DictField(required=False, default=dict)


class AutorizadorAltaSerializer(serializers.Serializer):
    usuarioId = serializers.IntegerField()
    cargo = serializers.CharField(max_length=80, required=False, allow_blank=True, allow_null=True)
    numeroOficio = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    fechaInicioVigencia = serializers.DateField()
    fechaFinVigencia = serializers.DateField()
    tipos = TipoAsignadoSerializer(many=True)


class AutorizadorEdicionSerializer(serializers.Serializer):
    cargo = serializers.CharField(max_length=80, required=False, allow_blank=True, allow_null=True)
    numeroOficio = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    tipos = TipoAsignadoSerializer(many=True)
    version = serializers.IntegerField()


class CambioEstatusSerializer(serializers.Serializer):
    motivoId = serializers.IntegerField(required=False, allow_null=True, default=None)
    descripcionMotivo = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    fechaFinSuspension = serializers.DateField(required=False, allow_null=True, default=None)
    version = serializers.IntegerField()


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField()


class RenovacionSerializer(serializers.Serializer):
    fechaFinVigencia = serializers.DateField()
    version = serializers.IntegerField()


# ---------------------------------------------------------------------- #
# Salida                                                                 #
# ---------------------------------------------------------------------- #

def _iso(valor):
    return valor.isoformat() if valor else None


def _nombre_completo(usuario):
    detalle = getattr(usuario, "detalle", None)
    if detalle is None:
        return usuario.usuario
    return " ".join(filter(None, [detalle.nombre, detalle.paterno, detalle.materno])).strip() or usuario.usuario


def _cedula(cedula):
    return {"numero": cedula.numero, "tipo": cedula.tipo, "esPrincipal": cedula.es_principal}


def _motivo(motivo):
    if motivo is None:
        return None
    return {"id": motivo.id_motivo, "clave": motivo.clave, "descripcion": motivo.descripcion}


def construir_autorizadores(autorizadores, hoy=None) -> list[dict]:
    hoy = hoy or timezone.localdate()
    ids = [a.pk for a in autorizadores]
    tipos_por_autorizador = {i: [] for i in ids}
    for autorizador in autorizadores:
        tipos_por_autorizador[autorizador.pk] = Repo.tipos_activos(autorizador.pk)
    todos_los_tipos = [t for lista in tipos_por_autorizador.values() for t in lista]
    alcances = Repo.alcances_activos([t.pk for t in todos_los_tipos])
    cedulas = Repo.cedulas_por_usuario([a.usuario_id for a in autorizadores])

    resultado = []
    for autorizador in autorizadores:
        tipos = []
        for autorizador_tipo in tipos_por_autorizador[autorizador.pk]:
            propios = [a for a in alcances if a.autorizador_tipo_id == autorizador_tipo.pk]
            tipos.append({
                "id": autorizador_tipo.pk,
                "clave": autorizador_tipo.tipo_autorizacion.clave,
                "nombre": autorizador_tipo.tipo_autorizacion.nombre,
                "fechaInicioVigencia": _iso(autorizador_tipo.fecha_inicio_vigencia),
                "fechaFinVigencia": _iso(autorizador_tipo.fecha_fin_vigencia),
                "alcance": {
                    "centros": [
                        {
                            "id": a.centro_atencion_id,
                            "nombre": a.centro_atencion.name,
                            "clues": a.centro_atencion.code,
                        }
                        for a in propios if a.tipo_alcance == AutorizadorAlcance.TipoAlcance.CENTRO
                    ],
                    "tiposCentro": [
                        a.tipo_centro for a in propios
                        if a.tipo_alcance == AutorizadorAlcance.TipoAlcance.TIPO_CENTRO
                    ],
                    "global": any(a.tipo_alcance == AutorizadorAlcance.TipoAlcance.GLOBAL for a in propios),
                },
            })
        resultado.append({
            "id": autorizador.pk,
            "usuario": {
                "id": autorizador.usuario_id,
                "usuario": autorizador.usuario.usuario,
                "nombreCompleto": _nombre_completo(autorizador.usuario),
                "cedulas": [_cedula(c) for c in cedulas.get(autorizador.usuario_id, [])],
            },
            "cargo": autorizador.cargo,
            "numeroOficio": autorizador.numero_oficio,
            "estatus": autorizador.estatus,
            "estadoVigencia": estado_vigencia(
                autorizador.fecha_inicio_vigencia, autorizador.fecha_fin_vigencia, hoy,
            ).value,
            "fechaInicioVigencia": _iso(autorizador.fecha_inicio_vigencia),
            "fechaFinVigencia": _iso(autorizador.fecha_fin_vigencia),
            "motivoEstatus": _motivo(autorizador.motivo_estatus),
            "descripcionMotivoEstatus": autorizador.descripcion_motivo_estatus,
            "fechaFinSuspension": _iso(autorizador.fecha_fin_suspension),
            "tipos": tipos,
            "version": autorizador.version,
            "creadoPor": build_user_ref(autorizador.id_usuario_creacion),
            "fechaCreacion": _iso(autorizador.fecha_creacion),
            "modificadoPor": build_user_ref(autorizador.id_usuario_modificacion),
            "fechaModificacion": _iso(autorizador.fecha_modificacion),
            "fechaBaja": _iso(autorizador.fecha_baja),
        })
    return resultado


def construir_movimiento(movimiento) -> dict:
    return {
        "id": movimiento.id_movimiento,
        "tipoMovimiento": movimiento.tipo_movimiento,
        "motivo": _motivo(movimiento.motivo),
        "descripcionMotivo": movimiento.descripcion_motivo,
        "datosAnteriores": movimiento.datos_anteriores,
        "datosNuevos": movimiento.datos_nuevos,
        "responsable": build_user_ref(movimiento.id_usuario_responsable),
        "fechaMovimiento": _iso(movimiento.fecha_movimiento),
    }


def construir_usuario_elegible(usuario) -> dict:
    return {
        "id": usuario.id_usuario,
        "usuario": usuario.usuario,
        "nombreCompleto": _nombre_completo(usuario),
        "tieneCedula": bool(usuario.tiene_cedula),
    }
