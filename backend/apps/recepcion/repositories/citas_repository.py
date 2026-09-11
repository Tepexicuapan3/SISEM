"""
Repositorio de citas médicas.

Encapsula todo acceso a CitaMedica y HorarioDisponible.
"""

import math
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.catalogos.models import MotivoCita
from apps.recepcion.models import CitaEstatusLog, CitaMedica, EstatusCita, HorarioDisponible
from apps.recepcion.uses_case.cita_state_machine_usecase import transition_cita_state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_cita(cita: CitaMedica) -> dict:
    det = getattr(cita.medico.id_usuario, "detalle", None)
    return {
        "id":             cita.id,
        "folio":          cita.folio,
        "noExp":          cita.no_exp,
        "pkNum":          cita.pk_num,
        "medicoId":       cita.medico_id,
        "medicoNombre":   det.nombre_completo if det else str(cita.medico_id),
        "consultorioId":  cita.consultorio_id,
        "consultorioNombre": (
            f"#{cita.consultorio.numero} — {cita.consultorio.name}"
            if cita.consultorio else None
        ),
        "fechaHora":      cita.fecha_hora.isoformat(),
        "duracionMin":    cita.duracion_min,
        "servicioTipo":   cita.servicio_tipo,
        "estatus":        cita.estatus,
        "motivo":         cita.motivo,
        "notas":          cita.notas,
        "createdAt":      cita.created_at.isoformat(),
        # Origen de la cita ("RECEPCION" | "PORTAL") — permite distinguir en
        # el sistema interno las citas agendadas por el paciente desde el
        # portal de citas en línea de las agendadas directamente en recepción.
        "origenCanal":    cita.origen_canal,
    }


# ── Repositorio ───────────────────────────────────────────────────────────────

class CitasRepository:

    # ── Citas ─────────────────────────────────────────────────────────────────

    @staticmethod
    def get_by_id(cita_id: int) -> CitaMedica | None:
        return (
            CitaMedica.objects
            .select_related("medico__id_usuario__detalle", "consultorio")
            .filter(id=cita_id)
            .first()
        )

    @staticmethod
    def get_by_folio(folio: str) -> CitaMedica | None:
        return (
            CitaMedica.objects
            .select_related("medico__id_usuario__detalle", "consultorio")
            .filter(folio=folio)
            .first()
        )

    @staticmethod
    def list_paginated(
        page: int,
        page_size: int,
        medico_id: int | None = None,
        consultorio_id: int | None = None,
        centro_id: int | None = None,
        no_exp: str | None = None,
        folio: str | None = None,
        estatus: str | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
    ) -> tuple[list[dict], int, int]:
        qs = (
            CitaMedica.objects
            .select_related("medico__id_usuario__detalle", "consultorio__id_center")
            .order_by("fecha_hora")
        )

        if medico_id:
            qs = qs.filter(medico_id=medico_id)
        if consultorio_id:
            qs = qs.filter(consultorio_id=consultorio_id)
        if centro_id:
            qs = qs.filter(consultorio__id_center_id=centro_id)
        if no_exp:
            qs = qs.filter(no_exp=no_exp)
        if folio:
            qs = qs.filter(folio__icontains=folio)
        if estatus:
            qs = qs.filter(estatus=estatus)
        if fecha_desde:
            qs = qs.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_hora__date__lte=fecha_hasta)

        total       = qs.count()
        start       = (page - 1) * page_size
        items       = [_serialize_cita(c) for c in qs[start: start + page_size]]
        total_pages = math.ceil(total / page_size) if total else 0

        return items, total, total_pages

    @staticmethod
    def create(
        no_exp: str,
        pk_num: int,
        medico_id: int,
        fecha_hora,
        servicio_tipo: str = "medicina_general",
        consultorio_id: int | None = None,
        duracion_min: int = 20,
        motivo: str | None = None,
        notas: str | None = None,
        created_by_id: int | None = None,
    ) -> dict:
        # Valida disponibilidad del médico (status, horario, excepciones) ANTES de
        # abrir la transacción porque es una consulta más costosa.
        from apps.medicos.models import CatMedico
        from apps.medicos.disponibilidad import get_disponibilidad_medico
        # medico_id acá es la PK de CatMedico (espacio médico) -- CitaMedica.medico
        # es FK a CatMedico. Antes de este fix se buscaba por id_usuario_id,
        # que coincidía con la PK solo por casualidad numérica (R1).
        medico = CatMedico.objects.filter(pk=medico_id).first()
        if medico:
            disp = get_disponibilidad_medico(medico, fecha_hora.date())
            if not disp["disponible"]:
                raise ValueError(f"El médico no está disponible: {disp['motivo']}")
            exc_parcial = disp.get("excepcionParcial")
            if exc_parcial:
                from datetime import time as _time
                exc_inicio = _time.fromisoformat(str(exc_parcial["horaInicio"])[:5])
                exc_fin    = _time.fromisoformat(str(exc_parcial["horaFin"])[:5])
                hora_cita  = fecha_hora.time().replace(second=0, microsecond=0)
                if exc_inicio <= hora_cita < exc_fin:
                    tipo = exc_parcial["tipo"].lower().replace("_", " ")
                    raise ValueError(
                        f"El médico tiene {tipo} de "
                        f"{str(exc_parcial['horaInicio'])[:5]} a "
                        f"{str(exc_parcial['horaFin'])[:5]}."
                    )

        with transaction.atomic():
            # 1. Bloquea la fila del slot con SELECT FOR UPDATE.
            #    Si dos requests llegan al mismo tiempo, el segundo espera
            #    hasta que el primero libere la transacción. Al salir del bloqueo
            #    encontrará disponible=False y fallará correctamente.
            slot = (
                HorarioDisponible.objects
                .select_for_update()
                .filter(
                    medico_id=medico_id,
                    fecha=fecha_hora.date(),
                    hora=fecha_hora.time(),
                    disponible=True,
                )
                .first()
            )
            if not slot:
                raise ValueError("El horario seleccionado no está disponible.")

            # 1.1 Slots con canal="LINEA" son exclusivos del portal de citas en
            #     línea — no se pueden agendar desde recepción, aunque sigan
            #     marcados disponible=True.
            if slot.canal == "LINEA":
                raise ValueError(
                    "Este horario está reservado exclusivamente para citas en "
                    "línea, no se puede agendar desde recepción."
                )

            # 2. El médico no debe tener otra cita activa en ese momento
            if CitaMedica.objects.filter(
                medico_id=medico_id,
                fecha_hora=fecha_hora,
                estatus__in=[EstatusCita.AGENDADA, EstatusCita.CONFIRMADA],
            ).exists():
                raise ValueError("El médico ya tiene una cita agendada en ese horario.")

            # 3. El paciente no debe tener otra cita activa a la misma hora
            if CitaMedica.objects.filter(
                no_exp=no_exp,
                pk_num=pk_num,
                fecha_hora=fecha_hora,
                estatus__in=[EstatusCita.AGENDADA, EstatusCita.CONFIRMADA],
            ).exists():
                raise ValueError("El paciente ya tiene una cita agendada en ese horario.")

            cita = CitaMedica.objects.create(
                folio=CitaMedica.generar_folio(),
                no_exp=no_exp,
                pk_num=pk_num,
                medico_id=medico_id,
                consultorio_id=consultorio_id,
                fecha_hora=fecha_hora,
                duracion_min=duracion_min,
                servicio_tipo=servicio_tipo,
                motivo=motivo,
                notas=notas,
                created_by_id=created_by_id,
            )

            # Marcar el slot como ocupado dentro de la misma transacción
            slot.disponible = False
            slot.cita = cita
            slot.save(update_fields=["disponible", "cita_id"])

        cita.refresh_from_db()
        cita = CitaMedica.objects.select_related(
            "medico__id_usuario__detalle", "consultorio"
        ).get(id=cita.id)
        return _serialize_cita(cita)

    @staticmethod
    def update_estatus(
        cita: CitaMedica,
        estatus: str,
        *,
        motivo_cancelacion=None,
        motivo_detalle: str | None = None,
        changed_by_id: int | None = None,
    ) -> dict:
        """
        ``motivo_cancelacion``: instancia (o PK) de ``catalogos.MotivoCita``
        -- catálogo tipificado, exigido por la máquina de estados para
        cancelar/marcar no asistió (ver cita_state_machine_usecase). Antes
        era un ``str`` libre; ese texto libre complementario ahora es
        ``motivo_detalle`` (opcional, se persiste en ``CitaMedica.motivo_detalle``
        y también queda en la bitácora NOM-024).

        Toma ``select_for_update()`` sobre la fila DENTRO de la transacción
        y re-valida el estatus recién ahí -- mismo patrón que
        ``portal_citas.cancelar_cita_usecase.cancelar_cita`` -- para evitar
        una condición de carrera si dos requests concurrentes (doble
        click/doble pestaña) intentan transicionar la misma cita al mismo
        tiempo. Si el caller (``cancelar_cita_usecase``) ya tomó el lock
        antes de llamar acá, este ``select_for_update()`` es reentrante
        (mismo savepoint de la transacción ya abierta), no un lock nuevo.

        IMPORTANTE: el lock se toma con una query aparte (``values_list``),
        SIN reasignar la variable local ``cita`` a una instancia nueva --
        varios callers (ej. ``cancelar_cita_usecase``) siguen usando su
        propia referencia al objeto ``cita`` que pasaron DESPUÉS de este
        llamado (para leer ``cita.folio``/``cita.estatus`` en la respuesta),
        confiando en que este método lo mute in-place como siempre hizo.
        Reasignar ``cita`` acá adentro rompería esa referencia externa.
        """
        with transaction.atomic():
            estatus_anterior = (
                CitaMedica.objects
                .select_for_update()
                .values_list("estatus", flat=True)
                .get(id=cita.id)
            )
            # Valida que la transición sea una de las permitidas (ver
            # cita_state_machine_usecase) DESPUÉS de tomar el lock -- si
            # otra request ya transicionó la cita entre la lectura sin
            # lock del caller y este punto, la re-validación lo detecta.
            transition_cita_state(estatus_anterior, estatus, motivo=motivo_cancelacion)

            cita.estatus = estatus
            update_fields = ["estatus", "updated_at"]

            if estatus == EstatusCita.CANCELADA:
                cita.cancelado_en = timezone.now()
                cita.cancelado_por_id = changed_by_id
                update_fields += ["cancelado_en", "cancelado_por_id"]

            if motivo_cancelacion is not None:
                # Acepta instancia de MotivoCita o PK cruda (int) -- los
                # callers automáticos (tasks.py, cancelar_cita_usecase) a
                # veces resuelven solo el id.
                if isinstance(motivo_cancelacion, MotivoCita):
                    cita.motivo_cancelacion = motivo_cancelacion
                else:
                    cita.motivo_cancelacion_id = motivo_cancelacion
                update_fields.append("motivo_cancelacion")
            if motivo_detalle is not None:
                cita.motivo_detalle = motivo_detalle
                update_fields.append("motivo_detalle")

            cita.save(update_fields=update_fields)

            # Liberar slot si se cancela o no asistió — dentro de la misma transacción
            if estatus in (EstatusCita.CANCELADA, EstatusCita.NO_ASISTIO):
                HorarioDisponible.objects.filter(cita=cita).update(
                    disponible=True, cita=None
                )

            # Bitácora NOM-024 — mismo patrón que VisitStatusLog. `notes`
            # guarda el nombre del motivo tipificado y/o el detalle libre,
            # lo que haya -- mismo criterio legible que antes.
            motivo_nombre = getattr(motivo_cancelacion, "name", None)
            CitaEstatusLog.objects.create(
                cita=cita,
                from_status=estatus_anterior,
                to_status=estatus,
                changed_by_id=changed_by_id,
                notes=motivo_detalle or motivo_nombre,
            )

        cita = CitaMedica.objects.select_related(
            "medico__id_usuario__detalle", "consultorio"
        ).get(id=cita.id)
        return _serialize_cita(cita)

    # ── Slots ─────────────────────────────────────────────────────────────────

    @staticmethod
    def generar_slots_medico(medico_id: int, dias_adelante: int = 30) -> int:
        """
        Genera HorarioDisponible para un médico basado en su horario semanal.
        Idempotente — usa get_or_create.
        """
        from apps.medicos.models import RelMedicoConsultorio

        dia_nombre_a_weekday = {
            "LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3,
            "VIERNES": 4, "SABADO": 5, "DOMINGO": 6,
        }

        hoy      = date.today()
        creados  = 0

        rmcs = (
            RelMedicoConsultorio.objects
            .prefetch_related("horarios")
            .filter(medico_id=medico_id, is_active=True)
        )

        for rmc in rmcs:
            for horario in rmc.horarios.all():
                weekday = dia_nombre_a_weekday.get(horario.dia_semana)
                if weekday is None:
                    continue

                intervalo = horario.intervalo_cita_min or 20
                inicio    = horario.hora_inicio
                fin       = horario.hora_fin

                for delta in range(dias_adelante):
                    dia = hoy + timedelta(days=delta)
                    if dia.weekday() != weekday:
                        continue

                    # Generar slots dentro del rango hora_inicio→hora_fin
                    from datetime import datetime, time
                    slot_time = datetime.combine(dia, inicio)
                    fin_dt    = datetime.combine(dia, fin)

                    while slot_time < fin_dt:
                        _, created = HorarioDisponible.objects.get_or_create(
                            medico_id=medico_id,
                            fecha=dia,
                            hora=slot_time.time(),
                            defaults={
                                "consultorio_id": rmc.consultorio_id,
                                "duracion_min":   intervalo,
                                "disponible":     True,
                                "canal":          horario.canal,
                            },
                        )
                        if created:
                            creados += 1
                        from datetime import timedelta as td
                        slot_time += td(minutes=intervalo)

        return creados

    @staticmethod
    def get_slots_disponibles(
        medico_id: int,
        fecha: date,
    ) -> list[dict]:
        slots = (
            HorarioDisponible.objects
            .filter(medico_id=medico_id, fecha=fecha, disponible=True)
            .order_by("hora")
        )
        return [
            {
                "fecha":        str(s.fecha),
                "hora":         str(s.hora)[:5],
                "duracionMin":  s.duracion_min,
                "consultorioId": s.consultorio_id,
            }
            for s in slots
        ]
