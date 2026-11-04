"""
Alcance por centro de atención en Recepción.

Cada visita y cada cita guardan el centro donde se registraron (del
consultorio; sin consultorio, el de quien la registra) y ese dato no cambia.
Recepción solo ve y trabaja lo de su centro:
- fila de visitas, citas, agenda y check-in filtran por centro;
- un registro de otro centro responde 404, como si no existiera;
- registrar una visita en otro centro se rechaza (403 CENTRO_NO_PERMITIDO);
- agendar en otro centro solo con recepcion:citas:agendar_otros_centros;
- sin centro asignado no se ve nada; alcance:centros:todos ve todo.
"""

from datetime import time, timedelta

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Permisos, Roles
from apps.recepcion.models import CitaMedica, HorarioDisponible, Visit
from apps.recepcion.tests._adscripcion_base import AdscripcionTestBase, fila_sermed

FICHAS = "recepcion:fichas:medicina_general:create"
CITAS_LEER = "recepcion:citas:read"
CITAS_ESCRIBIR = "recepcion:citas:write"
AGENDAR_OTROS = "recepcion:citas:agendar_otros_centros"
TODOS = "alcance:centros:todos"
RECEPCION = [FICHAS, CITAS_LEER, CITAS_ESCRIBIR]


class AlcanceCentroBase(AdscripcionTestBase):
    client_class = APIClient

    def setUp(self):
        super().setUp()
        self.ticoman = self._centro("TICOMAN", "CT-T", "3")
        self.cuauhtemoc = self._centro("CUAUHTEMOC", "CT-C", "1")
        self.cons_ticoman = self._consultorio(self.ticoman, 1, familiar=False)
        self.cons_cuauhtemoc = self._consultorio(self.cuauhtemoc, 1, familiar=False)
        self.paciente_t = self._paciente("EXP-T")
        self.paciente_c = self._paciente("EXP-C")
        self.visita_t = self._visita(self.paciente_t, self.cons_ticoman)
        self.visita_c = self._visita(self.paciente_c, self.cons_cuauhtemoc)
        self.cita_t = self._cita(self.paciente_t, self.cons_ticoman)
        self.cita_c = self._cita(self.paciente_c, self.cons_cuauhtemoc)

    def _visita(self, paciente, consultorio, created_by_id=None):
        return Visit.objects.create(
            folio=f"V-{Visit.objects.count() + 1}", patient=paciente,
            arrival_type=Visit.ArrivalType.WALK_IN, consultorio=consultorio,
            status="en_espera", created_by_id=created_by_id,
        )

    def _usuario(self, username, permisos, centro):
        user = SyUsuario.objects.create(
            usuario=username, correo=f"{username}@example.com",
            clave_hash=make_password("Clave_123456"), est_activo=True,
            cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="User", id_centro_atencion=centro,
        )
        rol = Roles.objects.create(rol=f"ROL_{username}", desc_rol="Rol", landing_route="/recepcion")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=rol, is_primary=True)
        for codigo in permisos:
            permiso, _ = Permisos.objects.get_or_create(codigo=codigo, defaults={"descripcion": codigo, "is_active": True})
            RelRolPermiso.objects.get_or_create(id_rol=rol, id_permiso=permiso)
        return user

    def _login(self, username, permisos=RECEPCION, centro="ticoman"):
        user = self._usuario(username, permisos, getattr(self, centro) if centro else None)
        self.client.cookies.clear()
        PolicyStore().clear_active_session(user.id_usuario)
        response = self.client.post(
            "/api/v1/auth/login", {"username": username, "password": "Clave_123456"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.cookies = response.cookies
        return user

    def _csrf(self):
        token = self.client.cookies.get("csrf_token")
        if token is None:
            self.client.cookies["csrf_token"] = "csrf-token-test"
            return {"HTTP_X_CSRF_TOKEN": "csrf-token-test"}
        return {"HTTP_X_CSRF_TOKEN": token.value}

    def _post(self, url, data):
        return self.client.post(url, data, format="json", **self._csrf())

    def _patch(self, url, data):
        return self.client.patch(url, data, format="json", **self._csrf())


class CentroDelRegistroTests(AlcanceCentroBase):
    def test_visita_y_cita_guardan_el_centro_del_consultorio(self):
        self.assertEqual(self.visita_c.centro_id, self.cuauhtemoc.pk)
        self.assertEqual(self.cita_c.centro_id, self.cuauhtemoc.pk)

    def test_sin_consultorio_toman_el_centro_de_quien_registra(self):
        recepcion = self._usuario("rcp.sin.consultorio", [], self.ticoman)

        visita = self._visita(self.paciente_t, None, created_by_id=recepcion.pk)
        cita = CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), patient=self.paciente_t, medico=self.medico,
            fecha_hora=timezone.now() + timedelta(days=3), created_by_id=recepcion.pk,
        )

        self.assertEqual(visita.centro_id, self.ticoman.pk)
        self.assertEqual(cita.centro_id, self.ticoman.pk)

    def test_el_centro_no_cambia_despues_de_creado(self):
        self.visita_c.consultorio = self.cons_ticoman
        self.visita_c.save()

        self.visita_c.refresh_from_db()
        self.assertEqual(self.visita_c.centro_id, self.cuauhtemoc.pk)


class FilaDeVisitasTests(AlcanceCentroBase):
    def _ids(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item["id"] for item in response.data["items"]}

    def test_solo_ve_las_visitas_de_su_centro(self):
        self._login("rcp.ticoman")

        self.assertEqual(self._ids(self.client.get("/api/v1/visits")), {self.visita_t.pk})

    def test_sin_centro_asignado_no_ve_nada(self):
        self._login("rcp.sin.centro", centro=None)

        self.assertEqual(self._ids(self.client.get("/api/v1/visits")), set())

    def test_con_alcance_de_todos_los_centros_ve_todo(self):
        self._login("supervision", RECEPCION + [TODOS], centro=None)

        self.assertEqual(self._ids(self.client.get("/api/v1/visits")), {self.visita_t.pk, self.visita_c.pk})

    def test_visita_de_otro_centro_es_404(self):
        self._login("rcp.ticoman")

        bitacora = self.client.get(f"/api/v1/visits/{self.visita_c.pk}/status-log")
        estatus = self._patch(f"/api/v1/visits/{self.visita_c.pk}/status", {"targetStatus": "no_show"})

        self.assertEqual(bitacora.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(estatus.status_code, status.HTTP_404_NOT_FOUND)
        self.visita_c.refresh_from_db()
        self.assertEqual(self.visita_c.status, "en_espera")

    def test_no_registra_visitas_en_consultorios_de_otro_centro(self):
        self._login("rcp.ticoman")

        response = self._post("/api/v1/visits", {
            "noExp": "EXP-C", "pkNum": 0, "arrivalType": "walk_in",
            "consultorioId": self.cons_cuauhtemoc.pk,
        })

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CENTRO_NO_PERMITIDO")

    def test_sin_centro_asignado_no_registra_visitas(self):
        self._login("rcp.sin.centro", centro=None)

        response = self._post("/api/v1/visits", {"noExp": "EXP-T", "pkNum": 0, "arrivalType": "walk_in"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CENTRO_NO_ASIGNADO")


class CitasTests(AlcanceCentroBase):
    def _cita_nueva(self, consultorio):
        return {
            "idPaciente": self.paciente_c.pk, "medicoId": self.medico.pk,
            "consultorioId": consultorio.pk,
            "fechaHora": (timezone.now() + timedelta(days=5)).isoformat(),
        }

    def test_solo_ve_las_citas_de_su_centro(self):
        self._login("rcp.ticoman")

        response = self.client.get("/api/v1/citas")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({c["id"] for c in response.data["items"]}, {self.cita_t.pk})

    def test_filtrar_por_otro_centro_no_amplia_el_alcance(self):
        self._login("rcp.ticoman")

        response = self.client.get("/api/v1/citas", {"centroId": self.cuauhtemoc.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])

    def test_cita_de_otro_centro_es_404(self):
        self._login("rcp.ticoman")

        detalle = self.client.get(f"/api/v1/citas/{self.cita_c.pk}")
        estatus = self._patch(f"/api/v1/citas/{self.cita_c.pk}/estatus", {"estatus": "confirmada"})

        self.assertEqual(detalle.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(estatus.status_code, status.HTTP_404_NOT_FOUND)
        self.cita_c.refresh_from_db()
        self.assertEqual(self.cita_c.estatus, "agendada")

    def test_no_agenda_en_otro_centro_sin_permiso(self):
        self._login("rcp.ticoman")

        response = self._post("/api/v1/citas", self._cita_nueva(self.cons_cuauhtemoc))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CENTRO_NO_PERMITIDO")

    def test_con_permiso_agenda_en_otro_centro(self):
        self._login("rcp.ticoman", RECEPCION + [AGENDAR_OTROS])

        with self._sermed(fila_sermed(cd_clinica="1")):
            response = self._post("/api/v1/citas", self._cita_nueva(self.cons_cuauhtemoc))

        self.assertNotEqual(response.data.get("code"), "CENTRO_NO_PERMITIDO")

    def test_agendar_en_otros_centros_no_amplia_lo_que_ve(self):
        self._login("rcp.ticoman", RECEPCION + [AGENDAR_OTROS])

        response = self.client.get("/api/v1/citas")

        self.assertEqual({c["id"] for c in response.data["items"]}, {self.cita_t.pk})


class AgendaTests(AlcanceCentroBase):
    def setUp(self):
        super().setUp()
        self.dia = timezone.localdate() + timedelta(days=10)
        HorarioDisponible.objects.create(medico=self.medico, consultorio=self.cons_ticoman, fecha=self.dia, hora=time(9, 0))
        HorarioDisponible.objects.create(medico=self.medico, consultorio=self.cons_cuauhtemoc, fecha=self.dia, hora=time(12, 0))

    def _consultorios_en_agenda(self):
        response = self.client.get("/api/v1/citas/agenda", {
            "medicoId": self.medico.pk, "fechaDesde": self.dia.isoformat(), "fechaHasta": self.dia.isoformat(),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {slot["consultorioId"] for slot in response.data["agenda"][self.dia.isoformat()]}

    def test_agenda_solo_muestra_horarios_de_su_centro(self):
        self._login("rcp.ticoman")

        self.assertEqual(self._consultorios_en_agenda(), {self.cons_ticoman.pk})

    def test_con_permiso_de_agendar_en_otros_centros_ve_sus_horarios(self):
        self._login("rcp.ticoman", RECEPCION + [AGENDAR_OTROS])

        self.assertEqual(self._consultorios_en_agenda(), {self.cons_ticoman.pk, self.cons_cuauhtemoc.pk})


class CheckinTests(AlcanceCentroBase):
    def setUp(self):
        super().setUp()
        CitaMedica.objects.filter(pk__in=[self.cita_t.pk, self.cita_c.pk]).update(fecha_hora=timezone.now())

    def test_candidato_por_folio_de_otro_centro_no_aparece(self):
        self._login("rcp.ticoman")

        response = self.client.get("/api/v1/citas/checkin/candidatos", {"folio": self.cita_c.folio})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["candidatos"], [])

    def test_check_in_de_cita_de_otro_centro_es_404(self):
        self._login("rcp.ticoman")

        response = self._post("/api/v1/citas/checkin/confirmar-folio", {"folio": self.cita_c.folio})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Visit.objects.filter(appointment_id=self.cita_c.folio).exists())
