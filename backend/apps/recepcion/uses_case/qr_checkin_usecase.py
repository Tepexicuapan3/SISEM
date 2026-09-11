"""
Verificación del comprobante QR (Fase 5 del portal "Citas en Línea") y
confirmación del check-in en recepción — Fase 7.

Flujo:
1. ``verificar_qr(payload)`` — valida la firma HMAC del payload leído del QR
   (reusando ``apps.portal_citas.services.comprobante_service.verificar_payload_qr``,
   NO se reimplementa la validación acá), busca la ``CitaMedica`` por el folio
   devuelto y arma los datos de la ficha para que recepción confirme
   visualmente que es la persona correcta.
2. ``confirmar_checkin(payload, verificado_por_id)`` — repite la misma
   validación (nunca se confía en un folio "suelto" enviado por el cliente,
   siempre se re-deriva del payload firmado) y, si la cita sigue en un
   estado agendable y ese folio todavía no tiene un ``Visit`` creado (evita
   duplicar el check-in si el mismo QR se reescanea), crea el check-in
   reusando el mecanismo YA EXISTENTE de creación de ``Visit`` (``apps.recepcion.uses_case.visit_queue_usecase.create_visit``,
   el mismo que usa ``VisitsView.post`` para cualquier llegada con
   ``arrivalType=appointment``) y marca la cita como verificada.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.administracion.use_cases.expedientes.buscar_expediente import buscar_expediente
from apps.medicos.identity import usuario_id_for_medico
from apps.portal_citas.services.comprobante_service import verificar_payload_qr
from apps.recepcion.models import CitaMedica, EstatusCita, Visit
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.services.errors import VisitDomainError
from apps.recepcion.uses_case.visit_queue_usecase import (
    RECEPCION_WRITE_CAPABILITY,
    create_visit,
)

logger = logging.getLogger(__name__)

# Misma capability que ya usa CitaDetailView/CitasListCreateView (recepcion/views/citas_views.py)
# para lectura de citas — se reusa el mismo literal por consistencia con ese archivo,
# que tampoco la importa de ningún lado compartido.
CITAS_READ_CAPABILITY = "recepcion:citas:read"

# Reexportada para que las vistas de este módulo no tengan que conocer que la
# capability de "crear visita" vive en visit_queue_usecase.
__all__ = [
    "CITAS_READ_CAPABILITY",
    "RECEPCION_WRITE_CAPABILITY",
    "verificar_qr",
    "confirmar_checkin",
    "checkin_por_folio",
    "buscar_candidatos_checkin",
]

# Estados de CitaMedica en los que YA NO se puede hacer check-in.
_ESTATUS_NO_CHECKIN = (EstatusCita.CANCELADA, EstatusCita.ATENDIDA, EstatusCita.NO_ASISTIO)

_ESTATUS_LABELS = {
    EstatusCita.CANCELADA:  "cancelada",
    EstatusCita.ATENDIDA:   "atendida",
    EstatusCita.NO_ASISTIO: "no asistió",
}


def _validar_estatus_checkin(cita: CitaMedica) -> None:
    if cita.estatus in _ESTATUS_NO_CHECKIN:
        label = _ESTATUS_LABELS.get(cita.estatus, cita.estatus)
        raise VisitDomainError(
            "CITA_ESTADO_NO_VALIDO",
            f"No se puede hacer check-in: la cita ya está marcada como {label}.",
            409,
        )


def _validar_checkin_no_duplicado(cita: CitaMedica) -> None:
    """
    Un QR puede reescanearse (recepción vuelve a apuntar la cámara, el
    paciente insiste, un supervisor reintenta, etc.). ``create_visit`` ->
    ``VisitRepository.exists_open_visit_for_patient`` NO cubre este caso:
    ese método solo bloquea una visita ABIERTA por paciente/día, pensado
    para el check-in manual (``VisitsView.post``), no para "este folio
    puntual ya generó un Visit alguna vez". Si ya existe un ``Visit`` para
    este ``appointment_id`` -- sin importar su estatus, abierto o cerrado --
    reescanear el mismo QR crearía un ``Visit`` duplicado para la misma cita.

    Se consulta directo sobre el modelo (mismo patrón que el
    ``CitaMedica.objects.filter(...).update(...)`` más abajo en este mismo
    archivo) en vez de forzar ``exists_open_visit_for_patient`` a resolver
    algo para lo que no fue pensado.
    """
    visita_previa = (
        Visit.objects
        .filter(appointment_id=cita.folio)
        .order_by("-fch_alta")
        .first()
    )
    if visita_previa is not None:
        cuando = timezone.localtime(visita_previa.fch_alta).isoformat()
        raise VisitDomainError(
            "CHECKIN_YA_REGISTRADO",
            f"Esta cita ya tuvo su check-in el {cuando}.",
            409,
        )


def _resolver_nombre_paciente(no_exp: str, pk_num: int) -> str:
    """
    Resuelve el nombre completo del paciente desde SERMED.

    Mismo patrón que ``ficha_service._get_nombre_components`` y
    ``visit_queue_usecase._build_member`` (no se reusan directo porque son
    funciones privadas de otros módulos — es la misma duplicación que ya
    existe entre esos dos archivos en el proyecto).

    ``incluir_fotos=False``: ninguno de los llamadores de esta función usa
    el campo ``FOTO`` (ver ``_serializar_ficha``/``_serializar_candidato``),
    así que evita la query ``SQL_FOTOS`` + ``optimizar_imagen`` de
    ``buscar_expediente``. Esto importa especialmente en
    ``buscar_candidatos_checkin``, que llama a esta función una vez por
    cada cita candidata del día -- en cada tecla que escribe recepción en
    el buscador por nombre.
    """
    try:
        resultado  = buscar_expediente(no_exp, incluir_fotos=False)
        empleados  = resultado.get("empleados", [])
        familiares = resultado.get("familiares", [])

        fuente = None
        if pk_num == 0 and empleados:
            fuente = empleados[0]
        elif pk_num > 0:
            fuente = next((f for f in familiares if f.get("PK_NUM") == pk_num), None)

        if fuente:
            partes = [
                fuente.get("DS_PATERNO", ""),
                fuente.get("DS_MATERNO", ""),
                fuente.get("DS_NOMBRE", ""),
            ]
            return " ".join(p for p in partes if p).strip()
    except Exception:
        logger.exception("Error consultando expediente %s para check-in por QR", no_exp)

    return ""


def _nombre_medico(cita: CitaMedica) -> str:
    det = getattr(cita.medico.id_usuario, "detalle", None)
    return det.nombre_completo if det else str(cita.medico_id)


def _nombre_consultorio(cita: CitaMedica) -> str | None:
    if not cita.consultorio:
        return None
    return f"#{cita.consultorio.numero} — {cita.consultorio.name}"


def _serializar_ficha(cita: CitaMedica, nombre_paciente: str) -> dict:
    return {
        "folio":              cita.folio,
        "paciente":           nombre_paciente,
        "medico":             _nombre_medico(cita),
        "consultorio":        _nombre_consultorio(cita),
        "fechaHora":          timezone.localtime(cita.fecha_hora).isoformat(),
        "servicioTipo":       cita.servicio_tipo,
        "motivo":             cita.motivo,
        "estatus":            cita.estatus,
        "yaVerificada":       cita.verificado_en is not None,
        # Origen de la cita ("RECEPCION" | "PORTAL") — la ficha de check-in
        # por QR solo la usa el portal (Fase 7), pero se expone igual para
        # que recepción vea explícitamente que es una cita "en línea".
        "origenCanal":        cita.origen_canal,
    }


def _serializar_candidato(cita: CitaMedica, nombre_paciente: str) -> dict:
    """
    Shape reducido de ``_serializar_ficha`` para la lista de candidatos de
    check-in (buscador por nombre/folio) — mismos nombres de campo donde
    aplica (``folio``, ``origenCanal``, ``estatus``) para consistencia con
    la ficha de check-in por QR.
    """
    return {
        "folio":             cita.folio,
        "pacienteNombre":    nombre_paciente,
        "fechaHora":         timezone.localtime(cita.fecha_hora).isoformat(),
        "consultorioNombre": _nombre_consultorio(cita),
        "medicoNombre":      _nombre_medico(cita),
        "origenCanal":       cita.origen_canal,
        "estatus":           cita.estatus,
    }


def _citas_candidatas_checkin_hoy() -> list[CitaMedica]:
    """
    Citas del día de HOY (hora local — ``TIME_ZONE = "America/Mexico_City"``)
    elegibles para check-in manual (búsqueda por nombre): mismo criterio de
    estatus que ``_validar_estatus_checkin`` (excluye cancelada/atendida/no
    asistió) más ``verificado_en__isnull=True`` para no volver a listar una
    cita que ya tuvo su check-in (evita duplicados, mismo espíritu que
    ``_validar_checkin_no_duplicado`` pero resuelto acá con un filtro de
    query en vez de una excepción, porque esto es una lista, no una
    confirmación puntual).
    """
    hoy = timezone.localdate()
    return list(
        CitaMedica.objects
        .select_related("medico__id_usuario__detalle", "consultorio")
        .filter(fecha_hora__date=hoy, verificado_en__isnull=True)
        .exclude(estatus__in=_ESTATUS_NO_CHECKIN)
        .order_by("fecha_hora")
    )


def buscar_candidatos_checkin(nombre: str | None, folio: str | None) -> list[dict]:
    """
    Busca citas de HOY elegibles para check-in manual (sin QR), por nombre
    del paciente (substring, case-insensitive) o por folio exacto.

    El llamador (la vista) ya garantiza que viene exactamente uno de los dos
    parámetros -- acá no se revalida esa regla, solo se prioriza ``folio``
    si por algún motivo llegaran ambos.
    """
    if folio:
        cita = CitasRepository.get_by_folio(folio)
        candidatas = [cita] if cita else []
    else:
        candidatas = _citas_candidatas_checkin_hoy()

    nombre_buscado = (nombre or "").strip().lower()

    resultado = []
    for cita in candidatas:
        # Re-aplica el mismo criterio de elegibilidad que
        # ``_citas_candidatas_checkin_hoy`` también para el camino de
        # ``folio`` (``get_by_folio`` no filtra por estatus/verificado_en):
        # un folio que ya hizo check-in o está cancelado no es un
        # "candidato" válido, sin importar por qué parámetro se buscó.
        if cita.estatus in _ESTATUS_NO_CHECKIN or cita.verificado_en is not None:
            continue

        nombre_paciente = _resolver_nombre_paciente(cita.no_exp, cita.pk_num)
        if nombre_buscado and nombre_buscado not in nombre_paciente.lower():
            continue

        resultado.append(_serializar_candidato(cita, nombre_paciente))

    return resultado


def verificar_qr(payload: str) -> dict:
    """
    Valida el payload del QR y retorna los datos de la ficha para que
    recepción confirme visualmente al paciente antes del check-in.
    No tiene efectos secundarios (no crea Visit, no toca la cita).
    """
    folio = verificar_payload_qr(payload)
    if folio is None:
        raise VisitDomainError("QR_INVALIDO", "Código QR inválido o alterado.", 400)

    cita = CitasRepository.get_by_folio(folio)
    if not cita:
        raise VisitDomainError(
            "CITA_NO_ENCONTRADA", "No se encontró ninguna cita con este código.", 404
        )

    _validar_estatus_checkin(cita)

    nombre_paciente = _resolver_nombre_paciente(cita.no_exp, cita.pk_num)
    return _serializar_ficha(cita, nombre_paciente)


def confirmar_checkin(payload: str, verificado_por_id: int | None) -> dict:
    """
    Wrapper delgado para el check-in vía QR: re-valida la firma HMAC del
    payload (nunca confía en el resultado de una llamada previa a
    ``verificar_qr`` — se re-verifica acá) y delega el resto de la lógica de
    negocio a ``checkin_por_folio``, que no sabe ni le importa de dónde salió
    el folio (QR, folio tipeado a mano, búsqueda por nombre, etc.).
    """
    folio = verificar_payload_qr(payload)
    if folio is None:
        raise VisitDomainError("QR_INVALIDO", "Código QR inválido o alterado.", 400)

    return checkin_por_folio(folio, verificado_por_id)


def checkin_por_folio(folio: str, verificado_por_id: int | None) -> dict:
    """
    Confirma el check-in de una cita a partir de un folio YA RESUELTO (por
    QR, por folio tipeado/buscado directo, o por selección de un candidato
    en la búsqueda por nombre — a este punto da igual, acá ya no hay QR de
    por medio):
    1. Busca la cita y valida su estatus.
    2. Crea el ``Visit`` reusando ``create_visit`` (mismo mecanismo que
       ``VisitsView.post`` usa para cualquier llegada con cita agendada:
       ``arrival_type=appointment``, ``appointment_id=folio``). Se deja
       ``hora_consulta``/``fecha_consulta`` en ``None`` a propósito -- igual
       que hace hoy el check-in manual de citas -- porque el slot de esa
       cita YA fue reservado en ``CitasRepository.create`` y volver a pasar
       la hora dispararía una revalidación de slot innecesaria en
       ``_check_and_reserve_slot`` (pensada para fichas walk-in, no para
       citas ya agendadas).
    3. Marca la cita como verificada (``verificado_en``/``verificado_por_id``).

    La deduplicación de check-ins concurrentes para la misma cita/paciente ya
    la resuelve ``create_visit`` -> ``VisitRepository.exists_open_visit_for_patient``
    (levanta ``VISIT_DUPLICATE_SUBMIT`` si ya hay una visita abierta), pero
    eso NO cubre el reescaneo del mismo QR (o un segundo intento de check-in
    por folio/nombre para la misma cita): si la visita original ya se
    cerró, ``exists_open_visit_for_patient`` no la ve y se generaría un
    ``Visit`` duplicado para la misma cita. Por eso ``_validar_checkin_no_duplicado``
    verifica -- sin importar el estatus -- si este folio puntual ya generó un
    ``Visit`` alguna vez.

    Ese chequeo se ejecuta DENTRO de la transacción, después de tomar
    ``select_for_update()`` sobre la fila de la ``CitaMedica``: hacerlo con
    una lectura plana antes de la transacción (como se hacía originalmente)
    es una condición de carrera -- dos requests casi simultáneos para el
    mismo folio pueden pasar ambos el chequeo porque ninguno ve todavía el
    ``Visit`` del otro (que aún no se commiteó), y terminar creando dos
    ``Visit`` duplicados. Con el lock, un segundo request para el mismo
    folio espera a que el primero termine (commit o rollback) antes de
    poder leer el estado real y decidir.
    """
    cita = CitasRepository.get_by_folio(folio)
    if not cita:
        raise VisitDomainError(
            "CITA_NO_ENCONTRADA", "No se encontró ninguna cita con este código.", 404
        )

    _validar_estatus_checkin(cita)

    nombre_paciente = _resolver_nombre_paciente(cita.no_exp, cita.pk_num)

    with transaction.atomic():
        # Lockea la fila de la cita: un segundo request concurrente para el
        # MISMO folio queda bloqueado acá hasta que este bloque termine
        # (commit o rollback), así el chequeo de abajo ve el estado real.
        # Se descarta el resultado a propósito: el resto del método sigue
        # usando `cita` (folio/no_exp/etc. no cambian), acá solo interesa
        # el efecto de lockear la fila mientras dura la transacción.
        cita_lock = CitaMedica.objects.select_for_update().get(pk=cita.pk)  # noqa: F841

        _validar_checkin_no_duplicado(cita)

        visit = create_visit(
            no_exp=cita.no_exp,
            pk_num=cita.pk_num,
            nombre_paciente=nombre_paciente or None,
            arrival_type=Visit.ArrivalType.APPOINTMENT,
            service_type=cita.servicio_tipo,
            appointment_id=cita.folio,
            # cita.medico_id es espacio médico (FK a CatMedico) -- Visit.doctor
            # es FK a SyUsuario (espacio usuario). Antes de este fix se pasaba
            # cita.medico_id directo como doctor_id (R1: conflación de ids,
            # metía una PK de CatMedico en una FK a SyUsuario). Visit.doctor
            # es null=True/on_delete=SET_NULL (verificado, recepcion/models.py),
            # así que None es seguro si el médico no tiene usuario asociado.
            doctor_id=usuario_id_for_medico(cita.medico_id),
            medico_id=cita.medico_id,
            consultorio_id=cita.consultorio_id,
            notes=cita.motivo,
            created_by_id=verificado_por_id,
        )

        ahora = timezone.now()
        CitaMedica.objects.filter(pk=cita.pk).update(
            verificado_en=ahora,
            verificado_por_id=verificado_por_id,
            updated_at=ahora,
        )

    return {
        "folio":        cita.folio,
        "paciente":     nombre_paciente,
        "verificadoEn": ahora.isoformat(),
        "visit":        visit,
    }
