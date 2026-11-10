"""
``POST /citas/{id}/reprogramar``: permiso de escritura, alcance por centro y
auditoría central (``CitaReprogramada``). Mismo setUp de login real que
``test_checkin_manual_api``.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.recepcion.models import CitaMedica, EstatusCita
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.recepcion.tests import test_checkin_manual_api as base
from apps.recepcion.uses_case import agendar_cita_usecase


class ReprogramarCitaApiTests(APITestCase):
    _create_user_with_role = base.CheckinManualApiTests._create_user_with_role
    _login_as = base.CheckinManualApiTests._login_as
    _csrf_headers = base.CheckinManualApiTests._csrf_headers
    _cita_hoy = base.CheckinManualApiTests._cita_hoy

    def setUp(self):
        base.CheckinManualApiTests.setUp(self)
        self._create_user_with_role(
            username="recepcion_reprog", email="reprog@example.com", password=self.recepcion_password,
            role_code="RECEPCION_REPROG", permissions=["recepcion:citas:read", "recepcion:citas:write"],
        )
        self._login_as("recepcion_reprog", self.recepcion_password)
        mock.patch.object(agendar_cita_usecase, "tiene_vigencia", return_value=True).start()
        mock.patch.object(agendar_cita_usecase, "centro_del_paciente", return_value=None).start()
        self.addCleanup(mock.patch.stopall)

        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.consultorio = Consultorios.objects.create(
            name="Consultorio Rep", numero=8, id_turn=turno, id_center=self.centro, is_active=True,
        )
        self.fecha = timezone.localdate() + timedelta(days=2)
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=self.fecha - timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(self.fecha),
            hora_inicio="09:00", hora_fin="10:00", intervalo_cita_min=20, canal="AMBOS",
        )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=5)

    def _post(self, cita, hora="09:40", **extra):
        return self.client.post(
            f"/api/v1/citas/{cita.id}/reprogramar",
            {"fechaHora": f"{self.fecha.isoformat()}T{hora}:00", "motivoDetalle": "Lo pidió el paciente", **extra},
            format="json", **self._csrf_headers(),
        )

    def test_reprograma_y_queda_en_la_auditoria(self):
        cita = self._cita_hoy(consultorio=self.consultorio)

        response = self._post(cita)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(response.json()["reprogramadaDeId"], cita.id)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.CANCELADA)
        evento = AuditoriaEvento.objects.get(accion="CitaReprogramada")
        self.assertEqual((evento.recurso_id, evento.resultado), (response.json()["id"], "SUCCESS"))
        self.assertEqual(evento.datos_antes["folio"], cita.folio)
        self.assertEqual(evento.datos_despues["folio"], response.json()["folio"])

    def test_rechazo_queda_en_la_auditoria_y_la_cita_sigue(self):
        cita = self._cita_hoy(consultorio=self.consultorio, estatus=EstatusCita.CANCELADA)

        response = self._post(cita)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        evento = AuditoriaEvento.objects.get(accion="CitaReprogramada")
        self.assertEqual((evento.resultado, evento.codigo_error), ("FAILED", "CITA_NO_REPROGRAMABLE"))

    def test_cita_de_otro_centro_no_existe(self):
        otro = CatCentroAtencion.objects.create(
            name="Otro", code="CT-OTRO-R", center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        cita = self._cita_hoy(centro=otro)

        self.assertEqual(self._post(cita).status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CitaMedica.objects.filter(reprogramada_de=cita).exists())

    def test_sin_fecha_es_422(self):
        cita = self._cita_hoy(consultorio=self.consultorio)
        response = self.client.post(f"/api/v1/citas/{cita.id}/reprogramar", {}, format="json", **self._csrf_headers())
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
