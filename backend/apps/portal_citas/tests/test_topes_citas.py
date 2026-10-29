"""
Topes de citas: una por día por paciente y 3 por expediente por día (reglas
del legado), más el tope de citas futuras del portal. Configurables como
parámetros generales en cat_parametro (0 desactiva).
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, ParametroDefinicion, Turnos
from apps.medicos.disponibilidad import dia_semana
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.portal_citas.models import PortalMiembro, PortalSesion
from apps.portal_citas.services.token_service import issue_portal_access_token
from apps.recepcion.models import CitaMedica, EstatusCita, HorarioDisponible
from apps.recepcion.repositories.citas_repository import CitasRepository
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

DIA = timezone.localdate() + timedelta(days=10)


def _a(dia, hora):
    return timezone.make_aware(datetime.combine(dia, time.fromisoformat(hora)))


class _Base:
    def _crear_entorno(self):
        centro = CatCentroAtencion.objects.create(
            name="Centro Topes", code="CT-TOP",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        self.consultorio = Consultorios.objects.create(
            name="Consultorio Topes", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        usuario = SyUsuario.objects.create(
            usuario="medico.topes", correo="medico.topes@example.com",
            clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno="Topes")
        self.medico = CatMedico.objects.create(id_usuario=usuario)

    def _cita(self, pk_num, fecha_hora, estatus=EstatusCita.AGENDADA):
        return CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), patient=_paciente_de_llave("EXP-TOP", pk_num),
            medico=self.medico, consultorio=self.consultorio, fecha_hora=fecha_hora,
            duracion_min=20, servicio_tipo="medicina_general", estatus=estatus,
        )


class TopesRecepcionTests(_Base, TestCase):
    def setUp(self):
        self._crear_entorno()
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=timezone.localdate() - timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana=dia_semana(DIA),
            hora_inicio="09:00", hora_fin="14:00", intervalo_cita_min=20,
        )
        CitasRepository.generar_slots_medico(medico_id=self.medico.id, dias_adelante=15)

    def _agendar(self, pk_num, hora):
        return CitasRepository.create(
            no_exp="EXP-TOP", pk_num=pk_num, medico_id=self.medico.id,
            fecha_hora=_a(DIA, hora), consultorio_id=self.consultorio.id,
        )

    def test_una_cita_por_dia_por_paciente(self):
        self._agendar(0, "09:00")

        with self.assertRaisesMessage(ValueError, "ya tiene una cita ese día"):
            self._agendar(0, "11:00")

    def test_una_cita_cancelada_no_cuenta(self):
        self._cita(0, _a(DIA, "12:00"), estatus=EstatusCita.CANCELADA)

        self._agendar(0, "09:00")

        self.assertEqual(CitaMedica.objects.filter(estatus=EstatusCita.AGENDADA).count(), 1)

    def test_tres_citas_por_expediente_por_dia(self):
        for pk_num, hora in ((0, "09:00"), (1, "09:20"), (2, "09:40")):
            self._agendar(pk_num, hora)

        with self.assertRaisesMessage(ValueError, "ya tiene 3 citas ese día"):
            self._agendar(3, "10:00")

    def test_tope_en_cero_queda_desactivado(self):
        ParametroDefinicion.objects.filter(key="citas.max_por_paciente_dia").update(general_value="0")
        cache.clear()
        self.addCleanup(cache.clear)  # el valor cacheado no debe filtrarse a otros tests
        self._agendar(0, "09:00")
        self._agendar(0, "11:00")

        self.assertEqual(CitaMedica.objects.count(), 2)


class TopesPortalTests(_Base, APITestCase):
    def setUp(self):
        self._crear_entorno()
        familiares_patcher = mock.patch(
            "apps.portal_citas.services.nucleo_service._familiares_del_nucleo",
            return_value=[],
        )
        familiares_patcher.start()
        self.addCleanup(familiares_patcher.stop)

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-TOP", pk_num=0, nombre_visible="Paciente", es_titular_login=True,
        )
        sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro, expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(sesion)

    def _reservar(self, dia, hora):
        slot = HorarioDisponible.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha=dia, hora=hora, canal="LINEA",
        )
        return self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": slot.id},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_portal_no_deja_dos_citas_el_mismo_dia(self):
        self._cita(0, _a(DIA, "09:00"))

        response = self._reservar(DIA, "12:00")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["code"], "CITA_MISMO_DIA")

    def test_portal_respeta_el_tope_de_citas_futuras(self):
        for dias in (10, 11, 12):
            self._cita(0, _a(timezone.localdate() + timedelta(days=dias), "09:00"))

        response = self._reservar(timezone.localdate() + timedelta(days=13), "09:00")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["code"], "TOPE_CITAS_FUTURAS")

    def test_portal_reserva_si_no_pasa_ningun_tope(self):
        self._cita(0, _a(timezone.localdate() + timedelta(days=11), "09:00"))

        response = self._reservar(DIA, "09:00")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
