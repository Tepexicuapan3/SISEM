"""
Contrato de ``GET /citas/seguimientos-pendientes``. Mismo setUp de login real
que ``test_checkin_manual_api``.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalogos.models import Consultorios, Turnos
from apps.consulta_medica.models import VisitConsultation
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import MOTIVO_CITA_SEGUIMIENTO, CitaMedica, Visit
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.tests import test_checkin_manual_api as base
from apps.recepcion.uses_case import agendar_cita_usecase


class SeguimientosPendientesApiTests(APITestCase):
    setUp = base.CheckinManualApiTests.setUp
    _create_user_with_role = base.CheckinManualApiTests._create_user_with_role
    _login_as = base.CheckinManualApiTests._login_as
    _csrf_headers = base.CheckinManualApiTests._csrf_headers

    def _get(self, **params):
        with mock.patch(
            "apps.recepcion.uses_case.seguimientos_por_agendar_usecase._nombre_paciente", return_value="PEREZ",
        ):
            return self.client.get("/api/v1/citas/seguimientos-pendientes", params)

    def _seguimiento(self):
        visit = Visit.objects.create(
            folio="VIS-API-S", patient=paciente_de_llave(base.PACIENTE_NO_EXP, 0),
            arrival_type=Visit.ArrivalType.WALK_IN, status="cerrada", fecha_consulta=timezone.localdate(),
            centro=self.centro, doctor=self.medico.id_usuario,
        )
        VisitConsultation.objects.create(
            id_visit=visit, doctor=self.medico.id_usuario, primary_diagnosis="Dx", final_note="Nota",
            follow_up_date=timezone.localdate() + timedelta(days=7),
        )
        return visit

    def _agenda_del_medico(self):
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        consultorio = Consultorios.objects.create(
            name="Consultorio Seg", numero=9, id_turn=turno, id_center=self.centro, is_active=True,
        )
        fecha = timezone.localdate() + timedelta(days=2)
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=consultorio, fecha_inicio=fecha - timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(fecha),
            hora_inicio="09:00", hora_fin="10:00", intervalo_cita_min=20, canal="AMBOS",
        )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=5)
        return fecha, consultorio

    def test_lista_el_seguimiento_sin_cita_del_centro(self):
        self._seguimiento()

        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["visitFolio"], "VIS-API-S")
        self.assertFalse(body["items"][0]["vencido"])

    def test_agendar_el_seguimiento_lo_enlaza_y_sale_de_la_lista(self):
        self._create_user_with_role(
            username="recepcion_seg", email="seg@example.com", password=self.recepcion_password,
            role_code="RECEPCION_SEG", permissions=["recepcion:citas:read", "recepcion:citas:write"],
        )
        self._login_as("recepcion_seg", self.recepcion_password)
        visit = self._seguimiento()
        fecha, consultorio = self._agenda_del_medico()

        with mock.patch.object(agendar_cita_usecase, "tiene_vigencia", return_value=True), \
             mock.patch.object(agendar_cita_usecase, "centro_del_paciente", return_value=None):
            response = self.client.post(
                "/api/v1/citas",
                {"idPaciente": visit.patient_id, "medicoId": self.medico.id, "consultorioId": consultorio.id,
                 "fechaHora": f"{fecha.isoformat()}T09:00:00", "seguimientoVisitId": visit.id_visit},
                format="json", **self._csrf_headers(),
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        cita = CitaMedica.objects.get(pk=response.json()["id"])
        self.assertEqual((cita.motivo, cita.notas), (MOTIVO_CITA_SEGUIMIENTO, f"Consulta {visit.folio}"))
        self.assertEqual(self._get().json()["total"], 0)

    def test_seguimiento_de_otro_paciente_es_422(self):
        self._create_user_with_role(
            username="recepcion_seg2", email="seg2@example.com", password=self.recepcion_password,
            role_code="RECEPCION_SEG2", permissions=["recepcion:citas:read", "recepcion:citas:write"],
        )
        self._login_as("recepcion_seg2", self.recepcion_password)
        visit = self._seguimiento()
        otro = paciente_de_llave("EXP-OTRO", 0)

        response = self.client.post(
            "/api/v1/citas",
            {"idPaciente": otro.pk, "medicoId": self.medico.id,
             "fechaHora": f"{(timezone.localdate() + timedelta(days=2)).isoformat()}T09:00:00",
             "seguimientoVisitId": visit.id_visit},
            format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY, response.content)
        self.assertEqual(response.json()["code"], "SEGUIMIENTO_DE_OTRO_PACIENTE")

    def test_rango_mayor_a_92_dias_es_422(self):
        hoy = timezone.localdate()
        response = self._get(fechaDesde=hoy.isoformat(), fechaHasta=(hoy + timedelta(days=100)).isoformat())
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
