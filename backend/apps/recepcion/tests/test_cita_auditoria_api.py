"""
Auditoría central de las citas (``AuditoriaEvento`` vía ``log_event``): al
agendar y al cambiar el estatus queda el actor, el request, la IP y el antes y
después, como en las visitas. Mismo setUp de login real que
``test_checkin_manual_api``.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import Consultorios, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import EstatusCita
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.tests import test_checkin_manual_api as base
from apps.recepcion.uses_case import agendar_cita_usecase


class CitaAuditoriaApiTests(APITestCase):
    _create_user_with_role = base.CheckinManualApiTests._create_user_with_role
    _login_as = base.CheckinManualApiTests._login_as
    _csrf_headers = base.CheckinManualApiTests._csrf_headers
    _cita_hoy = base.CheckinManualApiTests._cita_hoy

    def setUp(self):
        base.CheckinManualApiTests.setUp(self)
        self._create_user_with_role(
            username="recepcion_agenda", email="agenda@example.com", password=self.recepcion_password,
            role_code="RECEPCION_AGENDA", permissions=["recepcion:citas:read", "recepcion:citas:write"],
        )
        self._login_as("recepcion_agenda", self.recepcion_password)
        mock.patch.object(agendar_cita_usecase, "tiene_vigencia", return_value=True).start()
        mock.patch.object(agendar_cita_usecase, "centro_del_paciente", return_value=None).start()
        self.addCleanup(mock.patch.stopall)

    def _evento(self, accion):
        return AuditoriaEvento.objects.get(accion=accion)

    def test_agendar_queda_en_la_auditoria(self):
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        consultorio = Consultorios.objects.create(
            name="Consultorio Aud", numero=7, id_turn=turno, id_center=self.centro, is_active=True,
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

        response = self.client.post(
            "/api/v1/citas",
            {"noExp": base.PACIENTE_NO_EXP, "medicoId": self.medico.id, "consultorioId": consultorio.id,
             "fechaHora": f"{fecha.isoformat()}T09:00:00"},
            format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        evento = self._evento("CitaAgendada")
        self.assertEqual((evento.recurso_tipo, evento.recurso_id, evento.resultado), ("cita", response.json()["id"], "SUCCESS"))
        self.assertEqual(evento.actor_usuario.usuario, "recepcion_agenda")
        self.assertEqual(evento.datos_despues["folio"], response.json()["folio"])
        self.assertEqual(evento.datos_despues["estatus"], EstatusCita.AGENDADA)

    def test_agendar_rechazado_tambien_queda(self):
        response = self.client.post(
            "/api/v1/citas",
            {"noExp": base.PACIENTE_NO_EXP, "medicoId": self.medico.id,
             "fechaHora": f"{(timezone.localdate() + timedelta(days=2)).isoformat()}T09:00:00"},
            format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        evento = self._evento("CitaAgendada")
        self.assertEqual((evento.resultado, evento.codigo_error), ("FAILED", "CITA_NOT_AVAILABLE"))

    def test_cambiar_estatus_guarda_el_antes_y_despues(self):
        cita = self._cita_hoy()

        response = self.client.patch(
            f"/api/v1/citas/{cita.id}/estatus", {"estatus": "confirmada"}, format="json", **self._csrf_headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        evento = self._evento("CitaEstatusCambiado")
        self.assertEqual((evento.recurso_tipo, evento.recurso_id), ("cita", cita.id))
        self.assertEqual(evento.datos_antes, {"estatus": "agendada"})
        self.assertEqual(evento.datos_despues["estatus"], "confirmada")
