"""
P-03 · Adscripción a consultorio familiar: evaluación y sugerencia.

Solo lee. Compara la clínica que SERMED le marca a la persona (``cd_clinica``
de ``cat_empleados`` / ``cat_familiar``, leída en vivo con
``buscar_fila_paciente``) con su adscripción en SIRES y devuelve un estado.
La confirmación (escrituras, bloqueos, auditoría) vive en el caso de uso.

Los códigos V0..V10 y S0..S6 de los comentarios son las validaciones del
diseño (docs/plans/p03-consultorio-familiar.md).
"""

from dataclasses import dataclass, replace

from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.medicos.models import RelMedicoConsultorio
from apps.recepcion.models import (
    AdscripcionClinicaCentro,
    AdscripcionConsultorio,
    AdscripcionPaciente,
    CitaMedica,
    EstatusCita,
)
from apps.recepcion.services.clinica_paciente_service import centro_de_fila
from apps.recepcion.services.vigencia_service import buscar_fila_paciente, fila_tiene_vigencia


class EstadoAdscripcion:
    VIGENTE = "VIGENTE"
    SIN_ADSCRIPCION = "SIN_ADSCRIPCION"
    NO_COINCIDE = "NO_COINCIDE"
    CONSULTORIO_INACTIVO = "CONSULTORIO_INACTIVO"
    CLINICA_SIN_CENTRO = "CLINICA_SIN_CENTRO"
    P03_INACTIVO = "P03_INACTIVO"
    NO_VIGENTE = "NO_VIGENTE"
    SIN_DATO_EXPEDIENTE = "SIN_DATO_EXPEDIENTE"


# Estados en los que hay que reasignar y advertir de las citas que se cancelan.
REQUIEREN_REASIGNAR = frozenset({EstadoAdscripcion.NO_COINCIDE, EstadoAdscripcion.CONSULTORIO_INACTIVO})

ESTATUS_CITA_ACTIVA = (EstatusCita.AGENDADA, EstatusCita.CONFIRMADA)


@dataclass(frozen=True)
class EvaluacionAdscripcion:
    estado: str
    clave_clinica_sermed: str | None = None
    centro_sermed_id: int | None = None
    adscripcion: AdscripcionPaciente | None = None
    sin_medico_activo: bool = False
    citas_futuras: tuple = ()

    @property
    def requiere_reasignar(self) -> bool:
        return self.estado in REQUIEREN_REASIGNAR


@dataclass(frozen=True)
class OpcionConsultorio:
    consultorio_id: int
    nombre: str
    numero: int
    turno_id: int
    turno: str
    carga: int
    capacidad_maxima: int | None
    es_de_la_familia: bool
    sugerida: bool = False


# ── Consultas compartidas ────────────────────────────────────────────────────

def consultorios_familiares(centro_id, turno_id=None):
    """Consultorios configurados como familiares, activos, de un centro (S1, S2, S5)."""
    qs = AdscripcionConsultorio.objects.filter(
        esta_activo=True,
        consultorio__id_center_id=centro_id,
        consultorio__is_active=True,
        consultorio__deleted_at__isnull=True,
    )
    if turno_id:
        qs = qs.filter(consultorio__id_turn_id=turno_id)
    return qs


def medicos_activos(hoy=None):
    """Relaciones médico-consultorio vigentes hoy (V9, S3)."""
    hoy = hoy or timezone.localdate()
    return RelMedicoConsultorio.objects.filter(is_active=True, fecha_inicio__lte=hoy).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy)
    )


def adscripcion_activa(paciente):
    return (
        AdscripcionPaciente.objects.select_related("consultorio", "turno", "centro")
        .filter(paciente=paciente, estatus=AdscripcionPaciente.Estatus.ACTIVA)
        .first()
    )


def _citas_futuras_mg(paciente):
    return CitaMedica.objects.filter(
        patient=paciente,
        servicio_tipo="medicina_general",
        estatus__in=ESTATUS_CITA_ACTIVA,
        fecha_hora__gte=timezone.now(),
    )


def citas_futuras_medicina_general(paciente) -> tuple:
    """V10: citas futuras de medicina general del paciente (para la advertencia)."""
    return tuple(
        _citas_futuras_mg(paciente).select_related("medico", "consultorio").order_by("fecha_hora")
    )


def citas_a_cancelar(paciente, consultorio_destino_id, *, bloquear=False) -> tuple:
    """
    V10 al reasignar: las citas futuras de medicina general que no son del
    consultorio destino (las que ya son del destino se conservan). Con
    ``bloquear`` toma SELECT FOR UPDATE; sin select_related, porque PostgreSQL
    no bloquea el lado nulo de un outer join (consultorio es nullable).
    """
    qs = _citas_futuras_mg(paciente).exclude(consultorio_id=consultorio_destino_id)
    if bloquear:
        qs = qs.select_for_update()
    return tuple(qs.order_by("fecha_hora", "id"))


# ── Evaluación (V0 a V10) ────────────────────────────────────────────────────

def _clinica_sermed(paciente) -> tuple[str | None, str | None]:
    """
    Clave de clínica de SERMED de la persona, o el estado que impide seguir.
    Devuelve ``(clave, None)`` o ``(None, estado)``.
    """
    if paciente.provisional_code is not None:
        # V0: recién nacido provisional. Su vigencia es la del provisional y su
        # clínica la del titular, leída en vivo (no la copia del registro).
        from apps.consulta_medica.services import newborn_service

        provisional = getattr(paciente, "provisional", None)
        if provisional is None or not newborn_service.vigente(provisional):
            return None, EstadoAdscripcion.NO_VIGENTE
        fila = buscar_fila_paciente(provisional.holder_no_exp, 0)
        if fila is None:
            return None, EstadoAdscripcion.SIN_DATO_EXPEDIENTE
    else:
        if paciente.pk_num is None:
            # Familiar del legado sin PK_NUM: no hay fila de SERMED que leer.
            return None, EstadoAdscripcion.SIN_DATO_EXPEDIENTE
        fila = buscar_fila_paciente(paciente.no_exp, paciente.pk_num)  # V1
        if fila is None:
            return None, EstadoAdscripcion.SIN_DATO_EXPEDIENTE
        if not fila_tiene_vigencia(fila, paciente.no_exp, paciente.pk_num):  # V2
            return None, EstadoAdscripcion.NO_VIGENTE
    clave = centro_de_fila(fila)  # V3
    if clave is None:
        return None, EstadoAdscripcion.SIN_DATO_EXPEDIENTE
    return clave, None


def evaluar_adscripcion(paciente) -> EvaluacionAdscripcion:
    clave, estado = _clinica_sermed(paciente)
    if estado:
        return EvaluacionAdscripcion(estado=estado)
    return evaluar_clave(paciente.pk, clave)


def estado_de_miembro(*, id_paciente, clave_clinica, vigente) -> EvaluacionAdscripcion:
    """
    Evaluación con datos de SERMED ya leídos (la búsqueda del expediente los
    trae por miembro): no vuelve a consultar SERMED. ``id_paciente`` es None si
    la persona nunca se atendió en SIRES (no puede tener adscripción).
    """
    if not vigente:  # V2
        return EvaluacionAdscripcion(estado=EstadoAdscripcion.NO_VIGENTE)
    clave = centro_de_fila({"CD_CLINICA": clave_clinica})  # V3
    if clave is None:
        return EvaluacionAdscripcion(estado=EstadoAdscripcion.SIN_DATO_EXPEDIENTE)
    return evaluar_clave(id_paciente, clave)


def evaluar_clave(id_paciente, clave) -> EvaluacionAdscripcion:
    """V4 a V10 a partir de la clave de clínica de SERMED, ya vigente."""
    equivalencia = AdscripcionClinicaCentro.objects.filter(  # V4
        clave_clinica_sermed=clave, esta_activo=True,
    ).first()
    if equivalencia is None:
        return EvaluacionAdscripcion(estado=EstadoAdscripcion.CLINICA_SIN_CENTRO, clave_clinica_sermed=clave)

    centro_id = equivalencia.centro_id
    base = {"clave_clinica_sermed": clave, "centro_sermed_id": centro_id}
    if not consultorios_familiares(centro_id).exists():  # V5
        return EvaluacionAdscripcion(estado=EstadoAdscripcion.P03_INACTIVO, **base)

    adscripcion = adscripcion_activa(id_paciente) if id_paciente else None  # V6
    if adscripcion is None:
        return EvaluacionAdscripcion(estado=EstadoAdscripcion.SIN_ADSCRIPCION, **base)

    if adscripcion.centro_id != centro_id:  # V7
        return EvaluacionAdscripcion(
            estado=EstadoAdscripcion.NO_COINCIDE, adscripcion=adscripcion,
            citas_futuras=citas_futuras_medicina_general(id_paciente), **base,
        )

    if not consultorios_familiares(centro_id).filter(consultorio_id=adscripcion.consultorio_id).exists():  # V8
        return EvaluacionAdscripcion(
            estado=EstadoAdscripcion.CONSULTORIO_INACTIVO, adscripcion=adscripcion,
            citas_futuras=citas_futuras_medicina_general(id_paciente), **base,
        )

    sin_medico = not medicos_activos().filter(consultorio_id=adscripcion.consultorio_id).exists()  # V9
    return EvaluacionAdscripcion(
        estado=EstadoAdscripcion.VIGENTE, adscripcion=adscripcion, sin_medico_activo=sin_medico, **base,
    )


def resumen_para_busqueda(evaluacion: EvaluacionAdscripcion) -> dict:
    """Lo que la búsqueda del expediente muestra por miembro (camelCase)."""
    adscripcion = evaluacion.adscripcion
    return {
        "estado": evaluacion.estado,
        "requiereReasignar": evaluacion.requiere_reasignar,
        "idCentroSermed": evaluacion.centro_sermed_id,
        "idAdscripcion": adscripcion.id if adscripcion else None,
        "idConsultorio": adscripcion.consultorio_id if adscripcion else None,
        "consultorio": adscripcion.consultorio.name if adscripcion else None,
        "numeroConsultorio": adscripcion.consultorio.numero if adscripcion else None,
        "turno": adscripcion.turno.name if adscripcion else None,
        "idCentroAdscripcion": adscripcion.centro_id if adscripcion else None,
        "sinMedicoActivo": evaluacion.sin_medico_activo,
        "citasFuturas": len(evaluacion.citas_futuras),
    }


# ── Sugerencia (S0 a S6) ─────────────────────────────────────────────────────

def sugerir_consultorios(paciente, centro_id, *, turno_id=None) -> list[OpcionConsultorio]:
    """
    Consultorios en los que se puede adscribir a la persona, del más
    recomendable al menos; el primero va marcado como sugerido.
    """
    from apps.consulta_medica.models import ProvisionalPatient

    # Carga: adscripciones activas, sin contar recién nacidos ya vinculados a
    # SERMED (su adscripción provisional quedó de más).
    carga = (
        AdscripcionPaciente.objects.filter(
            consultorio_id=OuterRef("consultorio_id"), estatus=AdscripcionPaciente.Estatus.ACTIVA,
        )
        .exclude(paciente__provisional__status=ProvisionalPatient.Status.LINKED)
        .order_by()
        .values("consultorio_id")
        .annotate(total=Count("pk"))
        .values("total")
    )
    configs = (
        consultorios_familiares(centro_id, turno_id)  # S1, S2, S5
        .select_related("consultorio", "consultorio__id_turn")
        .annotate(
            carga=Coalesce(Subquery(carga, output_field=IntegerField()), Value(0)),
            con_medico=Exists(medicos_activos().filter(consultorio_id=OuterRef("consultorio_id"))),
        )
        .filter(con_medico=True)  # S3
    )
    # S0: consultorios donde ya está adscrito alguien del mismo expediente.
    de_la_familia = set(
        AdscripcionPaciente.objects.filter(
            estatus=AdscripcionPaciente.Estatus.ACTIVA, centro_id=centro_id, paciente__no_exp=paciente.no_exp,
        )
        .exclude(paciente=paciente)
        .values_list("consultorio_id", flat=True)
    )
    opciones = [
        OpcionConsultorio(
            consultorio_id=config.consultorio_id,
            nombre=config.consultorio.name,
            numero=config.consultorio.numero,
            turno_id=config.consultorio.id_turn_id,
            turno=config.consultorio.id_turn.name,
            carga=config.carga,
            capacidad_maxima=config.capacidad_maxima,
            es_de_la_familia=config.consultorio_id in de_la_familia,
        )
        for config in configs
        if config.capacidad_maxima is None or config.carga < config.capacidad_maxima  # S4
    ]
    opciones.sort(key=lambda o: (not o.es_de_la_familia, o.carga, o.numero, o.consultorio_id))  # S0, S6
    if opciones:
        opciones[0] = replace(opciones[0], sugerida=True)
    return opciones
