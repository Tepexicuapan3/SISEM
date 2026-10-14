"""
Vigencia del derechohabiente: sin vigencia no se entra al portal ni se
reserva. Si SERMED no responde no se bloquea (``vigencia_service``).

``buscar_expediente`` se mockea donde lo usa ``vigencia_service``: el alias
de BD "expedientes" no existe bajo ``manage.py test``.
"""

from datetime import date, timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.models import CatMedico
from apps.portal_citas.errors import PortalAuthError
from apps.portal_citas.models import PortalMiembro, PortalSesion
from apps.portal_citas.services.identity_service import IdentidadResuelta
from apps.portal_citas.services.token_service import issue_portal_access_token
from apps.portal_citas.uses_case.iniciar_sesion_usecase import iniciar_sesion
from apps.recepcion.models import CitaMedica, HorarioDisponible
from apps.recepcion.services.vigencia_service import tiene_vigencia

BUSCAR_EXPEDIENTE = "apps.recepcion.services.vigencia_service.buscar_expediente"

EXPEDIENTE = {
    "empleados": [{"NO_EXP": "EXP-VIG", "ESTATUS": "ACTIVO"}],
    "familiares": [
        {"NO_EXPF": "EXP-VIG", "PK_NUM": 1, "ESTATUS": "NO ACTIVO"},
        {"NO_EXPF": "EXP-VIG", "PK_NUM": 2, "ESTATUS": "ACTIVO"},
    ],
}


class TieneVigenciaTests(SimpleTestCase):
    def test_titular_activo(self):
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=EXPEDIENTE):
            self.assertTrue(tiene_vigencia("EXP-VIG", 0))

    def test_titular_de_baja(self):
        expediente = {"empleados": [{"ESTATUS": "BAJA"}], "familiares": []}
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=expediente):
            self.assertFalse(tiene_vigencia("EXP-VIG", 0))

    def test_familiar_segun_su_propia_vigencia(self):
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=EXPEDIENTE):
            self.assertFalse(tiene_vigencia("EXP-VIG", 1))
            self.assertTrue(tiene_vigencia("EXP-VIG", 2))

    def test_si_no_se_puede_verificar_no_bloquea(self):
        vacio = {"empleados": [], "familiares": []}
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=vacio):
            self.assertTrue(tiene_vigencia("EXP-VIG", 0))
            self.assertTrue(tiene_vigencia("EXP-VIG", 9))


class LoginSinVigenciaTests(TestCase):
    def test_login_sin_vigencia_responde_sin_vigencia_y_no_crea_miembro(self):
        identidad = IdentidadResuelta(
            no_exp="EXP-VIG", pk_num=0, nombre_visible="Titular de Baja",
            fe_nac=date(1980, 1, 1), es_titular=True,
        )
        expediente = {"empleados": [{"ESTATUS": "BAJA"}], "familiares": []}
        with mock.patch(
            "apps.portal_citas.uses_case.iniciar_sesion_usecase.resolve_identity",
            return_value=identidad,
        ), mock.patch(BUSCAR_EXPEDIENTE, return_value=expediente):
            with self.assertRaises(PortalAuthError) as ctx:
                iniciar_sesion("EXP-VIG", "Titular de Baja", date(1980, 1, 1))

        self.assertEqual(ctx.exception.code, "SIN_VIGENCIA")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse(PortalMiembro.objects.exists())


class ReservaSinVigenciaTests(APITestCase):
    def setUp(self):
        familiares_patcher = mock.patch(
            "apps.portal_citas.services.nucleo_service._familiares_del_nucleo",
            return_value=[],
        )
        familiares_patcher.start()
        self.addCleanup(familiares_patcher.stop)

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-VIG", pk_num=0,
            nombre_visible="Titular Vigencia", es_titular_login=True,
        )
        sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro,
            expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(sesion)

        centro = CatCentroAtencion.objects.create(
            name="Centro Vigencia", code="CT-VIG",
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        turno = Turnos.objects.create(name="Matutino", is_active=True)
        consultorio = Consultorios.objects.create(
            name="Consultorio Vigencia", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        usuario = SyUsuario.objects.create(
            usuario="medico.vigencia", correo="medico.vigencia@example.com",
            clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno="Vigencia")
        medico = CatMedico.objects.create(id_usuario=usuario)
        self.slot = HorarioDisponible.objects.create(
            medico=medico, consultorio=consultorio,
            fecha=(timezone.now() + timedelta(days=30)).date(), hora="09:00", canal="LINEA",
        )

    def _reservar(self):
        return self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": self.slot.id},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_reservar_sin_vigencia_responde_403(self):
        expediente = {"empleados": [{"ESTATUS": "BAJA"}], "familiares": []}
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=expediente):
            response = self._reservar()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "SIN_VIGENCIA")
        self.assertFalse(CitaMedica.objects.exists())

    def test_reservar_con_vigencia_crea_la_cita(self):
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=EXPEDIENTE):
            response = self._reservar()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
