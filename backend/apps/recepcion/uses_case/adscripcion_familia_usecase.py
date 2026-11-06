"""
P-03 · Asignación por familia: el núcleo del expediente en un solo paso.

``consultar_familia`` solo lee: arma lo que la pantalla necesita para asignar
a todo el núcleo (estado de cada miembro, si se puede asignar, opciones del
centro y las citas que se cancelarían con cada opción). No registra a nadie.

``adscribir_familia`` registra a los miembros marcados que todavía no son
pacientes (por la puerta central, ``paciente_de_llave``) y los asigna con el
mismo ``_adscribir`` de un paciente, todo dentro de UNA transacción: cada
asignación ve las anteriores del lote, así que la capacidad cuenta a todo el
núcleo, y si un miembro falla no queda nada escrito.
"""

from dataclasses import dataclass

from django.db import transaction

from apps.consulta_medica.models import Patient
from apps.recepcion.models import AdscripcionPaciente
from apps.recepcion.services.adscripcion_evaluacion import (
    EstadoAdscripcion,
    citas_a_cancelar,
    consultorios_de_la_familia,
    motivo_sin_opciones,
    opciones_de_familia,
)
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.adscripcion_usecase import AdscripcionError, Operador, _adscribir, _auditar

# Miembros que no se pueden asignar: la razón es el estado (OTRA_CLINICA se agrega aparte).
_ESTADOS_NO_ELEGIBLES = frozenset({
    EstadoAdscripcion.NO_VIGENTE,
    EstadoAdscripcion.SIN_DATO_EXPEDIENTE,
    EstadoAdscripcion.CLINICA_SIN_CENTRO,
    EstadoAdscripcion.P03_INACTIVO,
})
OTRA_CLINICA = "OTRA_CLINICA"


@dataclass(frozen=True)
class MiembroFamilia:
    datos: dict  # el miembro de la búsqueda del expediente (noExp, pkNum, nombre, ...)
    estado: str | None
    elegible: bool
    razon: str | None
    preseleccionado: bool
    adscripcion: AdscripcionPaciente | None
    citas_por_consultorio: dict  # {consultorio_id: tuple[CitaMedica]}


@dataclass(frozen=True)
class Familia:
    no_exp: str
    centro_id: int | None
    miembros: tuple
    opciones: list
    motivo_sin_opciones: str | None
    familia_separada: bool


@dataclass(frozen=True)
class Asignacion:
    pk_num: int
    consultorio_id: int
    id_adscripcion_esperada: int | None
    citas_a_cancelar: tuple = ()
    fue_sugerida: bool = False


# ── Consultar (solo lectura) ─────────────────────────────────────────────────

def _centro_de_la_familia(miembros) -> int | None:
    """El centro de SERMED del titular; si no lo trae, el del primer miembro que lo tenga."""
    for miembro in miembros:
        centro = (miembro.get("adscripcion") or {}).get("idCentroSermed")
        if centro is not None:
            return centro
    return None


def _razon(resumen, centro_id) -> str | None:
    if resumen is None:
        return EstadoAdscripcion.SIN_DATO_EXPEDIENTE
    if resumen["idCentroSermed"] is not None and resumen["idCentroSermed"] != centro_id:
        return OTRA_CLINICA
    if resumen["estado"] in _ESTADOS_NO_ELEGIBLES:
        return resumen["estado"]
    return None


def consultar_familia(no_exp, *, turno_id=None) -> Familia:
    from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp
    from apps.recepcion.uses_case.visit_queue_usecase import lookup_patient

    busqueda = lookup_patient(no_exp, historico=True, incluir_fotos=False)
    miembros = [m for m in (busqueda["titular"], *busqueda["dependientes"]) if m is not None]
    centro_id = _centro_de_la_familia(miembros)

    opciones = opciones_de_familia(no_exp, centro_id, turno_id=turno_id) if centro_id else []
    motivo = motivo_sin_opciones(centro_id, turno_id=turno_id) if centro_id and not opciones else None
    # El consultorio donde ya está la familia no se ofrece (lleno, sin médico, inactivo).
    separada = bool(centro_id) and bool(
        consultorios_de_la_familia(normalizar_no_exp(no_exp), centro_id) - {o.consultorio_id for o in opciones}
    )

    ids_adscripcion = [
        m["adscripcion"]["idAdscripcion"] for m in miembros if (m.get("adscripcion") or {}).get("idAdscripcion")
    ]
    adscripciones = AdscripcionPaciente.objects.select_related("centro", "consultorio", "turno").in_bulk(ids_adscripcion)
    pacientes = Patient.objects.in_bulk([a.paciente_id for a in adscripciones.values()])

    resultado = []
    for miembro in miembros:
        resumen = miembro.get("adscripcion")
        razon = _razon(resumen, centro_id)
        adscripcion = adscripciones.get((resumen or {}).get("idAdscripcion"))
        citas = {}
        if adscripcion is not None and razon is None:
            paciente = pacientes[adscripcion.paciente_id]
            citas = {o.consultorio_id: citas_a_cancelar(paciente, o.consultorio_id) for o in opciones}
        resultado.append(MiembroFamilia(
            datos=miembro,
            estado=resumen["estado"] if resumen else None,
            elegible=razon is None,
            razon=razon,
            # Quien ya tiene su consultorio se mueve solo si recepción lo marca.
            preseleccionado=razon is None and resumen["estado"] != EstadoAdscripcion.VIGENTE,
            adscripcion=adscripcion,
            citas_por_consultorio=citas,
        ))

    return Familia(
        no_exp=no_exp, centro_id=centro_id, miembros=tuple(resultado), opciones=opciones,
        motivo_sin_opciones=motivo, familia_separada=separada,
    )


# ── Asignar (una transacción para todo el núcleo) ───────────────────────────

def adscribir_familia(*, no_exp, asignaciones, motivo_cancelacion_id=None, origen, observaciones=None,
                      operador: Operador, request) -> list:
    """Devuelve ``[(pk_num, paciente, ResultadoAdscripcion), ...]`` en el orden recibido."""
    from apps.consulta_medica.services.paciente_entrada import paciente_de_llave

    actual = None
    try:
        with transaction.atomic():
            resultados = []
            for asignacion in asignaciones:
                actual = asignacion
                paciente = paciente_de_llave(no_exp, asignacion.pk_num, crear=True, created_by_id=operador.id_usuario)
                if paciente is None:
                    raise AdscripcionError("PACIENTE_NO_ENCONTRADO", "Ese miembro no está en el expediente.", 404)
                resultado = _adscribir(
                    id_paciente=paciente.pk,
                    consultorio_id=asignacion.consultorio_id,
                    id_adscripcion_esperada=asignacion.id_adscripcion_esperada,
                    citas_a_cancelar_ids=set(asignacion.citas_a_cancelar),
                    motivo_cancelacion_id=motivo_cancelacion_id,
                    origen=origen,
                    fue_sugerida=asignacion.fue_sugerida,
                    observaciones=(observaciones or "").strip() or None,
                    operador=operador,
                    request=request,
                )
                resultados.append((asignacion.pk_num, paciente, resultado))
            return resultados
    except VisitDomainError as exc:
        # Se revirtió todo el núcleo: el rechazo se audita afuera y dice qué miembro falló.
        pk_num = actual.pk_num if actual else None
        _auditar(
            request, operador, "ADSCRIPCION_ASIGNAR", "FAIL", codigo_error=exc.code,
            meta={"noExp": no_exp, "pkNum": pk_num, "familia": True},
        )
        raise AdscripcionError(
            exc.code, exc.message, exc.status_code, details={**(exc.details or {}), "pkNum": pk_num},
        ) from exc
