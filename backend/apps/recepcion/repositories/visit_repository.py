import math
import uuid
from apps.consulta_medica.services.paciente_entrada import llave_publica, paciente_de_llave, q_pk_registro
from apps.consulta_medica.services.patient_registry_service import normalizar_no_exp
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import OuterRef, Q, Subquery

from apps.authentication.models import DetUsuario
from apps.catalogos.models import MotivoCita
from apps.recepcion.models import Visit, VisitStatusLog
from apps.somatometria.repositories.vitals_repository import VitalsRepository


class VisitRepository:

    @staticmethod
    def create(
        no_exp: str,
        pk_num: int = 0,
        nombre_paciente: str | None = None,
        arrival_type: str = Visit.ArrivalType.WALK_IN,
        service_type: str = Visit.ServiceType.MEDICINA_GENERAL,
        appointment_id: str | None = None,
        doctor_id: int | None = None,
        consultorio_id: int | None = None,
        tipo_cita_id: int | None = None,
        notes: str | None = None,
        hora_consulta=None,
        fecha_consulta=None,
        num_ficha: int | None = None,
        turno_nombre: str | None = None,
        created_by_id: int | None = None,
    ) -> Visit:
        return Visit.objects.create(
            folio=VisitRepository._build_folio(),
            # Solo id_paciente (plan contraer la llave vieja): el registro se
            # resuelve, o se abre, por la puerta central.
            patient=paciente_de_llave(no_exp, pk_num, created_by_id=created_by_id),
            nombre_paciente=nombre_paciente,
            arrival_type=arrival_type,
            service_type=service_type,
            appointment_id=appointment_id,
            doctor_id=doctor_id,
            consultorio_id=consultorio_id,
            tipo_cita_id=tipo_cita_id,
            notes=notes,
            hora_consulta=hora_consulta,
            fecha_consulta=fecha_consulta,
            num_ficha=num_ficha,
            turno_nombre=turno_nombre,
            created_by_id=created_by_id,
            status="en_espera",
        )

    @staticmethod
    def log_status_change(
        visit: Visit,
        from_status: str | None,
        to_status: str,
        changed_by_id: int | None = None,
        notes: str | None = None,
    ) -> VisitStatusLog:
        return VisitStatusLog.objects.create(
            visit=visit,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=changed_by_id,
            notes=notes,
        )

    @staticmethod
    def get_status_log(visit_id: int) -> list[VisitStatusLog]:
        return list(
            VisitStatusLog.objects
            .filter(visit_id=visit_id)
            .order_by("changed_at")
        )

    @staticmethod
    def get_by_id(visit_id: int) -> Visit | None:
        return (
            Visit.objects
            .select_related(
                "consultorio__id_center",
                "tipo_cita",
                "vital_signs",
                # Detalle de la visita ORIGEN cuando `vital_signs` es un
                # reuso (`reused_from_visit`), + los vitales DE ESA visita
                # origen (su propio `fch_alta`) -- evita 2 queries extra
                # por visita al armar `reusedFrom` en `to_contract`.
                "vital_signs__reused_from_visit__vital_signs",
            )
            .annotate(en_somatometria_at=VisitRepository._en_somatometria_at_subquery())
            .filter(id_visit=visit_id)
            .first()
        )

    @staticmethod
    def exists_open_visit_for_patient(no_exp: str, pk_num: int) -> bool:
        """Verifica que el paciente no tenga ya una visita activa en el mismo día."""
        from apps.consulta_medica.services.paciente_entrada import q_registro

        return Visit.objects.filter(
            q_registro(no_exp, pk_num),
            fch_baja__isnull=True,
            status__in=("en_espera", "en_somatometria", "lista_para_doctor", "en_consulta"),
        ).exists()

    @staticmethod
    def get_for_update(visit_id: int) -> Visit | None:
        """
        Lookup mínimo (sin select_related de FKs nullable -- Postgres no
        permite FOR UPDATE del lado nullable de un outer join) bloqueando
        la fila con select_for_update(). Debe llamarse DENTRO de un
        transaction.atomic() ya abierto por el caller -- mismo patrón que
        ``CitasRepository.update_estatus``/``portal_citas.cancelar_cita_usecase``
        para evitar una condición de carrera si dos requests concurrentes
        transicionan la misma visita al mismo tiempo.
        """
        return Visit.objects.select_for_update().filter(id_visit=visit_id).first()

    @staticmethod
    def update_status(
        visit: Visit,
        status_value: str,
        motivo_cancelacion=None,
        motivo_detalle: str | None = None,
    ) -> Visit:
        """
        ``motivo_cancelacion``: instancia (o PK) de ``catalogos.MotivoCita``
        -- catálogo tipificado, exigido por la máquina de estados para
        cancelar (ver visit_state_machine_usecase). El texto libre
        complementario ahora es ``motivo_detalle`` (antes ocupaba el mismo
        campo `motivo_cancelacion`, que era un TextField).
        """
        visit.status = status_value
        update_fields = ["status", "fch_modf"]
        if motivo_cancelacion is not None:
            if isinstance(motivo_cancelacion, MotivoCita):
                visit.motivo_cancelacion = motivo_cancelacion
            else:
                visit.motivo_cancelacion_id = motivo_cancelacion
            update_fields.append("motivo_cancelacion")
        if motivo_detalle is not None:
            visit.motivo_detalle = motivo_detalle
            update_fields.append("motivo_detalle")
        visit.save(update_fields=update_fields)
        return visit

    @staticmethod
    def list_paginated(
        page: int,
        page_size: int,
        status_filter: str | None = None,
        date_filter=None,
        doctor_id: int | None = None,
        consultorio_id: int | None = None,
        centro_id: int | None = None,
        service_type: str | None = None,
        no_exp: str | None = None,
        fecha_desde=None,
        fecha_hasta=None,
        folio: str | None = None,
        q: str | None = None,
        pk_num: int | None = None,
    ) -> tuple[list[Visit], int, int]:
        queryset = (
            Visit.objects
            .select_related(
                "patient",
                "consultorio__id_center",
                "tipo_cita",
                "vital_signs",
                # Ver comentario en `get_by_id`: precarga la visita origen
                # del reuso + sus propios vitales para toda la pagina de la
                # cola, sin N+1 por fila.
                "vital_signs__reused_from_visit__vital_signs",
            )
            .annotate(en_somatometria_at=VisitRepository._en_somatometria_at_subquery())
            .order_by("-id_visit")
        )

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_filter:
            queryset = queryset.filter(fch_alta__date=date_filter)
        if fecha_desde:
            queryset = queryset.filter(fch_alta__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fch_alta__date__lte=fecha_hasta)
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        if consultorio_id:
            queryset = queryset.filter(consultorio_id=consultorio_id)
        if centro_id:
            queryset = queryset.filter(consultorio__id_center_id=centro_id)
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        # Plan contraer la llave vieja: el expediente se busca en cns_paciente.
        if no_exp:
            queryset = queryset.filter(patient__no_exp=normalizar_no_exp(no_exp))
        if folio:
            queryset = queryset.filter(folio__icontains=folio)
        if q:
            queryset = queryset.filter(
                Q(nombre_paciente__icontains=q)
                | Q(folio__icontains=q)
                | Q(patient__no_exp__icontains=q)
            )
        # `pk_num` es el índice del integrante familiar (0 = titular): filtro
        # EXACTO, siempre separado de `q`. Debe ser `is not None` — `pk_num=0`
        # es el titular y `if pk_num:` lo descartaría en silencio (D13).
        if pk_num is not None:
            queryset = queryset.filter(q_pk_registro(pk_num))

        total       = queryset.count()
        start       = (page - 1) * page_size
        visits      = list(queryset[start: start + page_size])
        total_pages = math.ceil(total / page_size) if total else 0

        # Enriquecer con nombre del médico (batch lookup, evita N+1)
        doctor_ids = {v.doctor_id for v in visits if v.doctor_id}
        doctor_nombres: dict[int, str] = {}
        if doctor_ids:
            dets = DetUsuario.objects.filter(id_usuario_id__in=doctor_ids)
            doctor_nombres = {d.id_usuario_id: d.nombre_completo for d in dets}

        # Batch-fetch fecha_hora de citas vinculadas (evita N+1)
        from django.utils import timezone as tz
        from apps.recepcion.models import CitaMedica
        appointment_ids = {v.appointment_id for v in visits if v.appointment_id}
        cita_fechas: dict[str, str] = {}
        if appointment_ids:
            citas = CitaMedica.objects.filter(folio__in=appointment_ids).only("folio", "fecha_hora")
            cita_fechas = {c.folio: tz.localtime(c.fecha_hora).isoformat() for c in citas}

        return visits, total, total_pages, doctor_nombres, cita_fechas

    @staticmethod
    def to_contract(
        visit: Visit,
        doctor_nombres: dict | None = None,
        cita_fechas: dict | None = None,
        *,
        include_vitals_values: bool = True,
    ) -> dict:
        try:
            vital_signs = visit.vital_signs
        except ObjectDoesNotExist:
            vital_signs = None

        doctor_nombre = None
        if visit.doctor_id and doctor_nombres:
            doctor_nombre = doctor_nombres.get(visit.doctor_id)

        # Fecha+hora ISO de la cita vinculada (para mostrar en frontend)
        fecha_cita = None
        if visit.appointment_id:
            if cita_fechas is not None:
                fecha_cita = cita_fechas.get(visit.appointment_id)
            else:
                try:
                    from django.utils import timezone as tz
                    from apps.recepcion.models import CitaMedica
                    cita = CitaMedica.objects.filter(folio=visit.appointment_id).only("fecha_hora").first()
                    if cita:
                        fecha_cita = tz.localtime(cita.fecha_hora).isoformat()
                except Exception:
                    pass

        consultorio_nombre = None
        centro_nombre      = None
        centro_id          = None
        if visit.consultorio_id:
            try:
                if visit.consultorio:
                    consultorio_nombre = f"#{visit.consultorio.numero} — {visit.consultorio.name}"
                    if visit.consultorio.id_center:
                        centro_nombre = visit.consultorio.id_center.name
                        centro_id     = visit.consultorio.id_center.id
            except Exception:
                pass

        tipo_cita_nombre = None
        if visit.tipo_cita_id:
            try:
                if visit.tipo_cita:
                    tipo_cita_nombre = visit.tipo_cita.name
            except Exception:
                pass

        return {
            "id":                visit.id_visit,
            "folio":             visit.folio,
            # Salen de cns_paciente (plan contraer la llave vieja).
            "noExp":             llave_publica(visit)[0] or "",
            "pkNum":             llave_publica(visit)[1],
            "nombrePaciente":    visit.nombre_paciente,
            "arrivalType":       visit.arrival_type,
            "serviceType":       visit.service_type,
            "appointmentId":     visit.appointment_id,
            "doctorId":          visit.doctor_id,
            "doctorNombre":      doctor_nombre,
            "consultorioId":     visit.consultorio_id,
            "consultorioNombre": consultorio_nombre,
            "tipoCitaId":        visit.tipo_cita_id,
            "tipoCitaNombre":    tipo_cita_nombre,
            "centroId":          centro_id,
            "centroNombre":      centro_nombre,
            "notes":             visit.notes,
            "horaConsulta":      VisitRepository._resolve_hora_consulta(visit, fecha_cita),
            "fechaConsulta":     visit.fecha_consulta.isoformat() if visit.fecha_consulta else None,
            "fechaCita":         fecha_cita,
            "numFicha":          visit.num_ficha,
            "turnoNombre":       visit.turno_nombre or "",
            "status":            visit.status,
            "fechaAlta":         visit.fch_alta.isoformat() if visit.fch_alta else None,
            "fechaModf":         visit.fch_modf.isoformat() if visit.fch_modf else None,
            "enSomatometriaAt":  VisitRepository._resolve_en_somatometria_at(visit),
            "createdById":       visit.created_by_id,
            "vitals": (
                (
                    VitalsRepository.to_contract(vital_signs)
                    if include_vitals_values
                    # Narrowing de recepcion (D3, somatometria-modulo-integral):
                    # solo estado, jamas peso/talla/presion/glucosa. Afecta
                    # UNICAMENTE al LIST -- el detalle de una visita individual
                    # siempre llama a `to_contract` con el default `True`.
                    else VitalsRepository.to_status_contract(vital_signs)
                )
                if vital_signs is not None
                else None
            ),
        }

    @staticmethod
    def status_log_to_contract(log: VisitStatusLog, user_nombres: dict | None = None) -> dict:
        usuario_nombre = None
        if log.changed_by_id and user_nombres:
            usuario_nombre = user_nombres.get(log.changed_by_id)
        return {
            "id":             log.id,
            "fromStatus":     log.from_status,
            "toStatus":       log.to_status,
            "changedById":    log.changed_by_id,
            "changedByNombre": usuario_nombre,
            "changedAt":      log.changed_at.isoformat() if log.changed_at else None,
            "notes":          log.notes,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _en_somatometria_at_subquery() -> Subquery:
        """
        Subquery (evita N+1) que resuelve el `changed_at` MAS RECIENTE del
        log de auditoria NOM-024 (`VisitStatusLog`) donde la visita
        transiciono a `en_somatometria`. Se usa como `.annotate(...)` en
        `get_by_id` y `list_paginated`, siguiendo el mismo patron de
        `select_related` ya usado en este archivo para evitar 1 query extra
        por fila.

        Se toma el ultimo registro (no el primero) por seguridad: si el
        state machine algun dia permitiera volver a pasar por
        `en_somatometria` mas de una vez, queremos la transicion mas
        reciente, no la primera.
        """
        return Subquery(
            VisitStatusLog.objects
            .filter(visit_id=OuterRef("pk"), to_status="en_somatometria")
            .order_by("-changed_at")
            .values("changed_at")[:1]
        )

    @staticmethod
    def _resolve_en_somatometria_at(visit: Visit) -> str | None:
        # Si `visit` viene de una queryset anotada (get_by_id / list_paginated),
        # usamos el valor ya resuelto en bulk. Si no esta anotado (ej. un Visit
        # armado a mano en un test o en otro flujo), resolvemos on-demand como
        # fallback para no romper el contrato.
        if hasattr(visit, "en_somatometria_at"):
            changed_at = visit.en_somatometria_at
        else:
            log = (
                VisitStatusLog.objects
                .filter(visit_id=visit.id_visit, to_status="en_somatometria")
                .order_by("-changed_at")
                .first()
            )
            changed_at = log.changed_at if log else None
        return changed_at.isoformat() if changed_at else None

    @staticmethod
    def _resolve_hora_consulta(visit: Visit, fecha_cita: str | None) -> str | None:
        """
        Hora a mostrar en "HORA CITA" (frontend) / ficha impresa.

        Para check-in manual/walk-in, `visit.hora_consulta` se captura de forma
        explícita. Para citas agendadas desde el portal en línea (check-in QR,
        ver `qr_checkin_usecase.py`), ese campo se deja `None` a propósito
        (el slot ya fue reservado por `CitasRepository.create`), así que hay
        que resolver la hora a partir de la cita vinculada (`fecha_cita`).

        Reusa la misma cascada de 3 niveles (hora explícita → cita vinculada
        → `fch_alta`) que `ficha_service._get_hora_consulta`, vía el helper
        compartido `hora_consulta_resolver`. `fecha_cita` ya viene resuelto
        en batch por `list_paginated` (evita N+1), por eso se parsea el ISO
        en vez de volver a consultar `CitaMedica`.
        """
        from django.utils import timezone as tz
        from apps.recepcion.services.hora_consulta_resolver import resolve_hora_consulta

        cita_dt = datetime.fromisoformat(fecha_cita) if fecha_cita else None
        fch_alta_local = tz.localtime(visit.fch_alta) if visit.fch_alta else None
        return resolve_hora_consulta(visit.hora_consulta, cita_dt, fch_alta_local) or None

    @staticmethod
    def _build_folio() -> str:
        return f"VIS-{uuid.uuid4().hex[:12].upper()}"
