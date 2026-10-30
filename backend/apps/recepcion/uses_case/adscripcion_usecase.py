"""
P-03 · Caso de uso de la adscripción a consultorio familiar.

``adscribir`` confirma una adscripción nueva o una reasignación en UNA sola
transacción: revalida con datos frescos, bloquea, cierra la adscripción
anterior, crea la nueva, cancela las citas del consultorio anterior con el
camino que ya existe (``CitasRepository.update_estatus``: máquina de estados,
libera el horario, bitácora NOM-024) y las deja por reagendar. Si algo falla
no queda nada escrito, y el rechazo se audita como FAIL.

Los códigos C1..C10 y R1..R4 de los comentarios son las validaciones del
diseño (docs/plans/p03-consultorio-familiar.md). C1 (sesión, CSRF, permiso)
es de la vista.
"""

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.authentication.services.audit_service import log_event
from apps.catalogos.models import MotivoCita
from apps.consulta_medica.models import Patient
from apps.recepcion.models import (
    AdscripcionCitaAfectada,
    AdscripcionConsultorio,
    AdscripcionPaciente,
    CitaMedica,
    EstatusCita,
)
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.adscripcion_evaluacion import (
    EstadoAdscripcion,
    EvaluacionAdscripcion,
    adscripcion_activa,
    citas_a_cancelar,
    consultorios_familiares,
    evaluar_adscripcion,
    medicos_activos,
    sugerir_consultorios,
)
from apps.recepcion.services.errors import VisitDomainError

RECURSO_AUDITORIA = "adscripcion_paciente"
MOTIVO_DETALLE_CANCELACION = "Cambio de consultorio familiar"


class AdscripcionError(VisitDomainError):
    """Rechazo de negocio de P-03; las vistas lo responden con error_response."""


# Estados con los que no se puede adscribir: (código, mensaje, HTTP).
_ESTADOS_QUE_IMPIDEN = {
    EstadoAdscripcion.NO_VIGENTE: (
        "PACIENTE_NO_VIGENTE", "El paciente no tiene vigencia activa.", 409,
    ),
    EstadoAdscripcion.SIN_DATO_EXPEDIENTE: (
        "SIN_DATO_EXPEDIENTE",
        "SERMED no trae la clínica del paciente o no respondió; no se puede adscribir.", 409,
    ),
    EstadoAdscripcion.CLINICA_SIN_CENTRO: (
        "CLINICA_SIN_CENTRO",
        "La clínica del paciente en SERMED no está registrada en SIRES. Avise al administrador.", 409,
    ),
    EstadoAdscripcion.P03_INACTIVO: (
        "P03_INACTIVO", "El centro del paciente todavía no tiene consultorios familiares configurados.", 409,
    ),
}

_MOTIVO_CIERRE_POR_ESTADO = {
    EstadoAdscripcion.NO_COINCIDE: AdscripcionPaciente.MotivoCierre.CAMBIO_CLINICA,
    EstadoAdscripcion.CONSULTORIO_INACTIVO: AdscripcionPaciente.MotivoCierre.CONSULTORIO_INACTIVO,
}


@dataclass(frozen=True)
class Operador:
    """Quién opera. La vista lo arma con el usuario, su centro y sus permisos."""

    usuario: object  # authentication.SyUsuario
    id_centro_atencion: int | None
    todos_centros: bool = False
    puede_excepcion: bool = False

    @property
    def id_usuario(self) -> int:
        return self.usuario.pk


@dataclass(frozen=True)
class ResultadoAdscripcion:
    adscripcion: AdscripcionPaciente
    sin_cambios: bool = False
    citas_canceladas: tuple = ()


@dataclass(frozen=True)
class Previsualizacion:
    evaluacion: EvaluacionAdscripcion
    sin_cambios: bool
    citas_a_cancelar: tuple


# ── Apoyo ────────────────────────────────────────────────────────────────────

def _foto(adscripcion) -> dict | None:
    if adscripcion is None:
        return None
    return {
        "idAdscripcion": adscripcion.id,
        "idPaciente": adscripcion.paciente_id,
        "idCentroAtencion": adscripcion.centro_id,
        "claveClinicaSermed": adscripcion.clave_clinica_sermed,
        "idConsultorio": adscripcion.consultorio_id,
        "idTurno": adscripcion.turno_id,
        "estatus": adscripcion.estatus,
        "motivoCierre": adscripcion.motivo_cierre,
    }


def _resumen_cita(cita) -> dict:
    return {
        "idCita": cita.id,
        "folio": cita.folio,
        "fechaHora": cita.fecha_hora.isoformat(),
        "idConsultorio": cita.consultorio_id,
        "idMedico": cita.medico_id,
    }


def _auditar(request, operador, accion, resultado, *, recurso_id=None, antes=None, despues=None,
             meta=None, codigo_error=None, estricto=False):
    log_event(
        request, accion, resultado,
        actor_user=operador.usuario,
        error_code=codigo_error,
        meta={"module": "recepcion", **(meta or {})},
        resource_type=RECURSO_AUDITORIA,
        resource_id=recurso_id,
        datos_antes=antes,
        datos_despues=despues,
        raise_on_error=estricto,
    )


def _paciente(id_paciente):
    paciente = Patient.objects.filter(pk=id_paciente).first()
    if paciente is None:
        raise AdscripcionError("PACIENTE_NO_ENCONTRADO", "Paciente no encontrado.", 404)
    return paciente


def _exigir_consultorio_elegible(paciente, centro_id, consultorio_id, config) -> None:
    """C6 y C7: del centro de SERMED, familiar, activo, con médico y con lugar."""
    elegibles = {o.consultorio_id for o in sugerir_consultorios(paciente, centro_id)}
    if consultorio_id in elegibles:
        return
    lleno = (
        config is not None
        and config.capacidad_maxima is not None
        and consultorios_familiares(centro_id).filter(consultorio_id=consultorio_id).exists()
        and medicos_activos().filter(consultorio_id=consultorio_id).exists()
    )
    if lleno:
        raise AdscripcionError("CONSULTORIO_LLENO", "El consultorio ya llegó a su capacidad. Elija otro.", 409)
    raise AdscripcionError(
        "CONSULTORIO_NO_ELEGIBLE", "Ese consultorio no recibe pacientes familiares del centro del paciente.", 422,
    )


def _motivo_cancelacion(motivo_cancelacion_id):
    """C9: motivo tipificado, activo y que aplique a cancelación."""
    motivo = None
    if motivo_cancelacion_id:
        motivo = MotivoCita.objects.filter(
            pk=motivo_cancelacion_id, is_active=True, deleted_at__isnull=True,
            aplica_a__in=(MotivoCita.AplicaA.CANCELACION, MotivoCita.AplicaA.AMBOS),
        ).first()
    if motivo is None:
        raise AdscripcionError("MOTIVO_REQUERIDO", "Elija el motivo de cancelación de las citas.", 422)
    return motivo


# ── Previsualizar (solo lectura) ─────────────────────────────────────────────

def previsualizar(*, id_paciente, consultorio_id) -> Previsualizacion:
    paciente = _paciente(id_paciente)
    evaluacion = evaluar_adscripcion(paciente)
    activa = evaluacion.adscripcion
    sin_cambios = (
        activa is not None
        and activa.consultorio_id == consultorio_id
        and evaluacion.estado == EstadoAdscripcion.VIGENTE
    )
    citas = citas_a_cancelar(paciente, consultorio_id) if activa is not None and not sin_cambios else ()
    return Previsualizacion(evaluacion=evaluacion, sin_cambios=sin_cambios, citas_a_cancelar=citas)


# ── Adscribir o reasignar ────────────────────────────────────────────────────

def adscribir(*, id_paciente, consultorio_id, id_adscripcion_esperada, citas_a_cancelar_ids=(),
              motivo_cancelacion_id=None, origen, fue_sugerida=False, observaciones=None,
              operador: Operador, request) -> ResultadoAdscripcion:
    try:
        return _adscribir(
            id_paciente=id_paciente,
            consultorio_id=consultorio_id,
            id_adscripcion_esperada=id_adscripcion_esperada,
            citas_a_cancelar_ids=set(citas_a_cancelar_ids or ()),
            motivo_cancelacion_id=motivo_cancelacion_id,
            origen=origen,
            fue_sugerida=fue_sugerida,
            observaciones=(observaciones or "").strip() or None,
            operador=operador,
            request=request,
        )
    except VisitDomainError as exc:
        # La transacción ya se revirtió: el rechazo se registra afuera para que perdure.
        _auditar(
            request, operador, "ADSCRIPCION_ASIGNAR", "FAIL", codigo_error=exc.code,
            meta={"idPaciente": id_paciente, "idConsultorio": consultorio_id},
        )
        raise


def _adscribir(*, id_paciente, consultorio_id, id_adscripcion_esperada, citas_a_cancelar_ids,
               motivo_cancelacion_id, origen, fue_sugerida, observaciones, operador, request):
    if origen not in AdscripcionPaciente.Origen.values:
        raise AdscripcionError("ORIGEN_INVALIDO", "Origen de la adscripción inválido.", 422)
    paciente = _paciente(id_paciente)

    with transaction.atomic():
        evaluacion = evaluar_adscripcion(paciente)  # C3: datos frescos, no los de la vista previa
        impide = _ESTADOS_QUE_IMPIDEN.get(evaluacion.estado)
        if impide:
            raise AdscripcionError(*impide)
        centro_id = evaluacion.centro_sermed_id

        if not operador.todos_centros and operador.id_centro_atencion != centro_id:  # C2
            raise AdscripcionError(
                "CENTRO_NO_PERMITIDO", "El paciente pertenece a otro centro de atención.", 403,
            )

        activa = (  # C4
            AdscripcionPaciente.objects.select_for_update()
            .filter(paciente=paciente, estatus=AdscripcionPaciente.Estatus.ACTIVA)
            .first()
        )
        if (activa.id if activa else None) != id_adscripcion_esperada:
            raise AdscripcionError(
                "ADSCRIPCION_MODIFICADA",
                "La adscripción del paciente cambió mientras la revisaba. Vuelva a cargarla.", 409,
            )

        if (  # C5
            activa is not None
            and activa.consultorio_id == consultorio_id
            and evaluacion.estado == EstadoAdscripcion.VIGENTE
        ):
            return ResultadoAdscripcion(adscripcion=activa, sin_cambios=True)

        # C6 y C7: se bloquea la configuración antes de contar la carga.
        config = AdscripcionConsultorio.objects.select_for_update().filter(consultorio_id=consultorio_id).first()
        _exigir_consultorio_elegible(paciente, centro_id, consultorio_id, config)

        citas = citas_a_cancelar(paciente, consultorio_id, bloquear=True) if activa else ()  # C8
        if {c.id for c in citas} != citas_a_cancelar_ids:
            raise AdscripcionError(
                "CITAS_MODIFICADAS", "Las citas del paciente cambiaron. Revise la lista y confirme otra vez.",
                409, details={"citas": [_resumen_cita(c) for c in citas]},
            )
        motivo = _motivo_cancelacion(motivo_cancelacion_id) if citas else None  # C9

        ahora = timezone.now()
        antes = _foto(activa)
        if activa is not None:
            activa.estatus = AdscripcionPaciente.Estatus.CERRADA
            activa.fecha_fin = ahora
            activa.id_usuario_cierre = operador.id_usuario
            activa.motivo_cierre = _MOTIVO_CIERRE_POR_ESTADO.get(
                evaluacion.estado, AdscripcionPaciente.MotivoCierre.REASIGNACION,
            )
            activa.save(update_fields=["estatus", "fecha_fin", "id_usuario_cierre", "motivo_cierre"])

        try:
            with transaction.atomic():
                nueva = AdscripcionPaciente.objects.create(
                    paciente=paciente,
                    centro_id=centro_id,
                    clave_clinica_sermed=evaluacion.clave_clinica_sermed,
                    consultorio_id=consultorio_id,
                    turno_id=config.consultorio.id_turn_id,
                    origen=origen,
                    fue_sugerida=fue_sugerida,
                    observaciones=observaciones,
                    fecha_inicio=ahora,
                    id_usuario_creacion=operador.id_usuario,
                )
        except IntegrityError as exc:  # C10: otra confirmación ganó la carrera
            raise AdscripcionError(
                "ADSCRIPCION_MODIFICADA",
                "La adscripción del paciente cambió mientras la revisaba. Vuelva a cargarla.", 409,
            ) from exc

        for cita in citas:  # C10: transición válida o se revierte todo
            CitasRepository.update_estatus(
                cita, EstatusCita.CANCELADA,
                motivo_cancelacion=motivo,
                motivo_detalle=MOTIVO_DETALLE_CANCELACION,
                changed_by_id=operador.id_usuario,
            )
            AdscripcionCitaAfectada.objects.create(
                adscripcion=nueva, cita_cancelada=cita, id_usuario_creacion=operador.id_usuario,
            )

        _auditar(
            request, operador,
            "ADSCRIPCION_REASIGNAR" if activa is not None else "ADSCRIPCION_ASIGNAR", "SUCCESS",
            recurso_id=nueva.id, antes=antes, despues=_foto(nueva),
            meta={"estadoEvaluado": evaluacion.estado, "citasCanceladas": [c.id for c in citas]},
            estricto=True,
        )
        return ResultadoAdscripcion(adscripcion=nueva, citas_canceladas=tuple(citas))


# ── Atención en el consultorio familiar (A1 a A3) ────────────────────────────

def paciente_por_llave(*, id_paciente=None, no_exp=None, pk_num=None):
    """El registro de cns_paciente que se atiende, o None si nunca se abrió."""
    from apps.consulta_medica.services.paciente_entrada import q_pk_registro
    from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp

    if id_paciente:
        return Patient.objects.filter(pk=id_paciente).first()
    if not no_exp:
        return None
    return Patient.objects.filter(no_exp=normalizar_no_exp(no_exp)).filter(
        q_pk_registro(pk_num if pk_num is not None else 0, prefijo=""),
    ).first()


def validar_consultorio_familiar(*, paciente, consultorio_id, servicio_tipo, excepcion_motivo=None,
                                 operador, request, recurso) -> None:
    """
    A1/A2: la medicina general se atiende en el consultorio familiar. Si la
    persona no tiene adscripción, o P-03 no aplica, no se detiene nada (la
    pantalla muestra el aviso). A3: con permiso y motivo se atiende igual y
    queda auditado; la adscripción no cambia.

    ``operador`` puede ser un Operador o una función que lo arma: solo se
    llama si hace falta (excepción), para no agregar consultas a cada cita.
    """
    if servicio_tipo != "medicina_general" or paciente is None or not consultorio_id:
        return
    evaluacion = evaluar_adscripcion(paciente)
    adscripcion = evaluacion.adscripcion
    distinto = evaluacion.requiere_reasignar or (
        evaluacion.estado == EstadoAdscripcion.VIGENTE and adscripcion.consultorio_id != consultorio_id
    )
    if not distinto:
        return

    motivo = (excepcion_motivo or "").strip()
    if not motivo:
        raise AdscripcionError(
            "CONSULTORIO_FAMILIAR_DIFERENTE",
            "Este paciente tiene otro consultorio familiar. Reasígnelo o atiéndalo con excepción.",
            409,
            details={
                "estado": evaluacion.estado,
                "idAdscripcion": adscripcion.id if adscripcion else None,
                "idConsultorioFamiliar": adscripcion.consultorio_id if adscripcion else None,
                "idConsultorioSolicitado": consultorio_id,
                "idCentroSermed": evaluacion.centro_sermed_id,
                "citasFuturas": [_resumen_cita(c) for c in evaluacion.citas_futuras],
            },
        )
    if callable(operador):
        operador = operador()
    if not operador.puede_excepcion:
        raise AdscripcionError(
            "EXCEPCION_NO_PERMITIDA", "No tiene permiso para atender en otro consultorio.", 403,
        )
    _auditar(
        request, operador, "ADSCRIPCION_EXCEPCION", "SUCCESS",
        recurso_id=adscripcion.id if adscripcion else None,
        meta={
            "idPaciente": paciente.pk, "idConsultorio": consultorio_id, "estado": evaluacion.estado,
            "motivo": motivo[:255], "recurso": recurso,
        },
        estricto=True,
    )


def validar_cita_en_checkin(*, folio, excepcion_motivo=None, operador, request) -> None:
    """A2 en el check-in: si la cita no existe, el flujo actual responde su propio error."""
    cita = CitaMedica.objects.select_related("patient").filter(folio=folio).first()
    if cita is None:
        return
    validar_consultorio_familiar(
        paciente=cita.patient, consultorio_id=cita.consultorio_id, servicio_tipo=cita.servicio_tipo,
        excepcion_motivo=excepcion_motivo, operador=operador, request=request, recurso="checkin",
    )


# ── Citas por reagendar (R1 a R4) ────────────────────────────────────────────

def _cita_afectada_pendiente(id_cita_afectada):
    afectada = (  # R1
        AdscripcionCitaAfectada.objects.select_for_update()
        .filter(pk=id_cita_afectada)
        .first()
    )
    if afectada is None:
        raise AdscripcionError("CITA_AFECTADA_NO_ENCONTRADA", "Cita por reagendar no encontrada.", 404)
    if afectada.estatus != AdscripcionCitaAfectada.Estatus.PENDIENTE:
        raise AdscripcionError("CITA_AFECTADA_RESUELTA", "Esa cita ya se reagendó o se descartó.", 409)
    return afectada


def descartar_cita_afectada(*, id_cita_afectada, motivo, operador: Operador, request) -> AdscripcionCitaAfectada:
    motivo = (motivo or "").strip()
    if not motivo:
        raise AdscripcionError("MOTIVO_REQUERIDO", "Escriba por qué ya no se reagenda la cita.", 422)
    with transaction.atomic():
        afectada = _cita_afectada_pendiente(id_cita_afectada)
        afectada.estatus = AdscripcionCitaAfectada.Estatus.DESCARTADA
        afectada.motivo_descarte = motivo[:255]
        afectada.fecha_resolucion = timezone.now()
        afectada.id_usuario_resolucion = operador.id_usuario
        afectada.save(update_fields=["estatus", "motivo_descarte", "fecha_resolucion", "id_usuario_resolucion"])
        _auditar(
            request, operador, "ADSCRIPCION_DESCARTAR_CITA", "SUCCESS", recurso_id=afectada.adscripcion_id,
            despues={"idCitaAfectada": afectada.id, "motivo": afectada.motivo_descarte}, estricto=True,
        )
        return afectada


def vincular_reagenda(*, id_cita_afectada, cita_nueva, operador: Operador, request) -> AdscripcionCitaAfectada:
    """
    Marca como reagendada una cita afectada. La cita nueva la crea antes el
    flujo de citas (que ya valida el horario libre, R2); aquí se exige que sea
    del mismo paciente (R3), del consultorio de su adscripción activa y que no
    se use dos veces (R4).
    """
    with transaction.atomic():
        afectada = _cita_afectada_pendiente(id_cita_afectada)
        cancelada = afectada.cita_cancelada
        if cita_nueva.patient_id != cancelada.patient_id:  # R3
            raise AdscripcionError("CITA_DE_OTRO_PACIENTE", "La cita nueva es de otro paciente.", 422)
        activa = adscripcion_activa(cancelada.patient)
        if activa is None or cita_nueva.consultorio_id != activa.consultorio_id:
            raise AdscripcionError(
                "CONSULTORIO_FAMILIAR_DIFERENTE",
                "La cita nueva tiene que ser en el consultorio familiar actual del paciente.", 409,
            )
        afectada.estatus = AdscripcionCitaAfectada.Estatus.REAGENDADA
        afectada.cita_nueva = cita_nueva
        afectada.fecha_resolucion = timezone.now()
        afectada.id_usuario_resolucion = operador.id_usuario
        try:
            with transaction.atomic():
                afectada.save(update_fields=["estatus", "cita_nueva", "fecha_resolucion", "id_usuario_resolucion"])
        except IntegrityError as exc:  # R4
            raise AdscripcionError("CITA_YA_USADA", "Esa cita nueva ya reagenda otra cita.", 409) from exc
        _auditar(
            request, operador, "ADSCRIPCION_REAGENDAR", "SUCCESS", recurso_id=afectada.adscripcion_id,
            despues={"idCitaAfectada": afectada.id, "idCitaNueva": cita_nueva.id}, estricto=True,
        )
        return afectada
