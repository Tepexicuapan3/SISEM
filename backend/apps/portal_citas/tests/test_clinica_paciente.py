"""
El paciente solo agenda en consultorios de su clínica (``CD_CLINICA`` de
SERMED = id del centro del consultorio), igual que en recepción. Los
listados se filtran por la clínica del paciente elegido y la reserva lo
vuelve a validar. Sin dato de clínica no se filtra ni se bloquea.
"""

from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import CatCentroAtencion, Consultorios, Turnos
from apps.medicos.models import CatMedico, RelMedicoConsultorio, RelMedicoConsultorioHorario
from apps.portal_citas.models import PortalMiembro, PortalSesion
from apps.portal_citas.services.token_service import issue_portal_access_token
from apps.recepcion.models import CitaMedica, HorarioDisponible

BUSCAR_EXPEDIENTE = "apps.recepcion.services.vigencia_service.buscar_expediente"


class ClinicaPacientePortalTests(APITestCase):
    def setUp(self):
        cache.clear()
        familiares_patcher = mock.patch(
            "apps.portal_citas.services.nucleo_service._familiares_del_nucleo",
            return_value=[],
        )
        familiares_patcher.start()
        self.addCleanup(familiares_patcher.stop)

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-CLI", pk_num=0, nombre_visible="Paciente", es_titular_login=True,
        )
        sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro, expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(sesion)

        turno = Turnos.objects.create(name="Matutino", is_active=True)
        usuario = SyUsuario.objects.create(
            usuario="medico.clinica", correo="medico.clinica@example.com",
            clave_hash="x", est_activo=True,
        )
        DetUsuario.objects.create(id_usuario=usuario, nombre="Dr", paterno="Clinica")
        self.medico = CatMedico.objects.create(id_usuario=usuario)

        self.mi_centro, self.mi_consultorio = self._centro_con_consultorio("Mi Clínica", "CT-MIA", turno)
        self.otro_centro, self.otro_consultorio = self._centro_con_consultorio("Otra Clínica", "CT-OTRA", turno)

    def _centro_con_consultorio(self, nombre, code, turno):
        centro = CatCentroAtencion.objects.create(
            name=nombre, code=code,
            center_type=CatCentroAtencion.TipoCentro.CLINICA, is_active=True,
        )
        consultorio = Consultorios.objects.create(
            name=f"Consultorio {nombre}", numero=1, id_turn=turno, id_center=centro, is_active=True,
        )
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=consultorio,
            fecha_inicio=timezone.localdate() - timedelta(days=30), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana="LUNES",
            hora_inicio="09:00", hora_fin="10:00", canal="LINEA",
        )
        return centro, consultorio

    def _expediente(self, cd_clinica):
        return mock.patch(
            BUSCAR_EXPEDIENTE,
            return_value={
                "empleados": [{"ESTATUS": "ACTIVO", "CD_CLINICA": cd_clinica}],
                "familiares": [],
            },
        )

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def _reservar_en(self, consultorio):
        slot = HorarioDisponible.objects.create(
            medico=self.medico, consultorio=consultorio,
            fecha=timezone.localdate() + timedelta(days=10), hora="09:00", canal="LINEA",
        )
        return self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": slot.id},
            format="json", **self._auth(),
        )

    def test_no_reserva_en_un_consultorio_de_otra_clinica(self):
        with self._expediente(str(self.mi_centro.id)):
            response = self._reservar_en(self.otro_consultorio)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "CLINICA_NO_CORRESPONDE")
        self.assertFalse(CitaMedica.objects.exists())

    def test_reserva_en_un_consultorio_de_su_clinica(self):
        with self._expediente(str(self.mi_centro.id)):
            response = self._reservar_en(self.mi_consultorio)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_listados_solo_muestran_su_clinica(self):
        params = {"miembroId": str(self.miembro.id)}
        with self._expediente(str(self.mi_centro.id)):
            centros = self.client.get("/api/v1/portal/centros", params, **self._auth())
            consultorios = self.client.get("/api/v1/portal/consultorios", params, **self._auth())

        self.assertEqual([c["centroId"] for c in centros.data["centros"]], [self.mi_centro.id])
        self.assertEqual(
            [c["consultorioId"] for c in consultorios.data["consultorios"]],
            [self.mi_consultorio.id],
        )

    def test_sin_dato_de_clinica_no_se_filtra(self):
        params = {"miembroId": str(self.miembro.id)}
        with self._expediente(None):
            centros = self.client.get("/api/v1/portal/centros", params, **self._auth())

        self.assertEqual(len(centros.data["centros"]), 2)

    def test_miembro_ajeno_responde_403(self):
        ajeno = PortalMiembro.objects.create(
            no_exp="EXP-AJENO", pk_num=0, nombre_visible="Ajeno", es_titular_login=True,
        )

        response = self.client.get(
            "/api/v1/portal/centros", {"miembroId": str(ajeno.id)}, **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
