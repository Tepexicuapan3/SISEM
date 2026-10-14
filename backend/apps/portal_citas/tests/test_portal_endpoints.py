"""
Tests de integración de los endpoints del Portal de Citas —
Disponibilidad por Consultorio + filtro por Clínica y privacidad del
médico (portal-citas-filtro-clinica):

  - GET /portal/consultorios
  - GET /portal/slots (regresión: cliente legado con solo especialidadId)
  - GET /portal/consultorios/{id}/disponibilidad-mensual
  - GET /portal/centros (NUEVO)
  - GET /portal/consultorios?centroId= (NUEVO query param)
  - GET/POST /portal/citas, PATCH /portal/citas/{folio}/cancelar
    (regresión de privacidad: medicoNombre NUNCA se expone en el portal
    público, ni antes ni después de reservar)

Cubre: 401 sin Bearer, 422 en validación de rango (mes/año), y que un
``consultorioId`` inexistente en la disponibilidad mensual responda 200
con ``dias: []`` (nunca 404, para no habilitar enumeración).
"""

from datetime import date, timedelta
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
from apps.recepcion.models import HorarioDisponible


class PortalEndpointsTests(APITestCase):
    def setUp(self):
        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-001",
            pk_num=0,
            nombre_visible="Paciente de Prueba",
            es_titular_login=True,
        )
        self.sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro,
            expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(self.sesion)

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    # ── GET /portal/consultorios ────────────────────────────────────────

    def test_consultorios_sin_bearer_devuelve_401(self):
        response = self.client.get("/api/v1/portal/consultorios")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_consultorios_con_bearer_devuelve_200(self):
        response = self.client.get("/api/v1/portal/consultorios", **self._auth())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("consultorios", response.data)

    # ── GET /portal/slots ────────────────────────────────────────────────

    def test_slots_sin_bearer_devuelve_401(self):
        response = self.client.get("/api/v1/portal/slots", {"fecha": "2026-08-03"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_slots_cliente_legado_solo_especialidad_id_sigue_funcionando(self):
        """Regresión: el frontend viejo manda ?fecha&especialidadId sin
        consultorioId — el endpoint no debe cambiar de shape ni fallar."""
        response = self.client.get(
            "/api/v1/portal/slots",
            {"fecha": "2026-08-03", "especialidadId": 1},
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("slots", response.data)

    # ── GET /portal/consultorios/{id}/disponibilidad-mensual ────────────

    def test_disponibilidad_mensual_sin_bearer_devuelve_401(self):
        response = self.client.get(
            "/api/v1/portal/consultorios/1/disponibilidad-mensual", {"anio": 2026, "mes": 8},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_disponibilidad_mensual_mes_invalido_devuelve_422(self):
        response = self.client.get(
            "/api/v1/portal/consultorios/1/disponibilidad-mensual",
            {"anio": 2026, "mes": 13},
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_disponibilidad_mensual_anio_fuera_de_rango_devuelve_422(self):
        response = self.client.get(
            "/api/v1/portal/consultorios/1/disponibilidad-mensual",
            {"anio": 1900, "mes": 8},
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_disponibilidad_mensual_consultorio_inexistente_devuelve_200_dias_vacio(self):
        """No 404: un consultorioId inexistente no debe distinguirse de uno
        sin cupo, para no habilitar enumeración de IDs."""
        response = self.client.get(
            "/api/v1/portal/consultorios/999999/disponibilidad-mensual",
            {"anio": 2026, "mes": 8},
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dias"], [])
        self.assertEqual(response.data["consultorioId"], 999999)


class PortalCentrosYFiltroClinicaTests(APITestCase):
    """
    GET /portal/centros (NUEVO) y GET /portal/consultorios?centroId=
    (REQ-1/REQ-2 de portal-citas-filtro-clinica).
    """

    def setUp(self):
        # El catálogo de consultorios/centros online se sirve desde
        # ``cache`` (TTL 300s, LocMemCache en tests) -- sin esto, un valor
        # cacheado por OTRA clase de test dentro del mismo proceso (mismo
        # backend LocMemCache compartido) contaminaría estas aserciones
        # sobre contenido exacto.
        cache.clear()

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-002",
            pk_num=0,
            nombre_visible="Paciente Filtro",
            es_titular_login=True,
        )
        self.sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro,
            expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(self.sesion)

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Endpoint",
            code="CT-EP-01",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_active=True,
        )
        self.turno = Turnos.objects.create(name="Matutino", is_active=True)

        usuario = SyUsuario.objects.create(
            usuario="medico.endpoint",
            correo="medico.endpoint@example.com",
            clave_hash="x",
            est_activo=True,
        )
        DetUsuario.objects.create(
            id_usuario=usuario,
            nombre="Bea",
            paterno="Soto",
        )
        self.medico = CatMedico.objects.create(id_usuario=usuario)

        self.consultorio = Consultorios.objects.create(
            name="Consultorio Endpoint", numero=1, id_turn=self.turno,
            id_center=self.centro, is_active=True,
        )
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=date(2026, 1, 1), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana="LUNES",
            hora_inicio="08:00", hora_fin="12:00", canal="LINEA",
        )

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    # ── GET /portal/centros ──────────────────────────────────────────────

    def test_centros_sin_bearer_devuelve_401(self):
        response = self.client.get("/api/v1/portal/centros")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_centros_con_bearer_devuelve_200_con_datos(self):
        response = self.client.get("/api/v1/portal/centros", **self._auth())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("centros", response.data)
        self.assertEqual(
            response.data["centros"],
            [{"centroId": self.centro.id, "nombre": self.centro.name}],
        )

    # ── GET /portal/consultorios?centroId= ──────────────────────────────

    def test_consultorios_centro_id_no_numerico_devuelve_422(self):
        response = self.client.get(
            "/api/v1/portal/consultorios", {"centroId": "abc"}, **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_consultorios_centro_id_cero_devuelve_422(self):
        response = self.client.get(
            "/api/v1/portal/consultorios", {"centroId": 0}, **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_consultorios_centro_id_inexistente_devuelve_200_lista_vacia(self):
        """Un centroId numérico pero que no matchea ningún centro no debe
        distinguirse de uno sin consultorios online (anti-enumeración,
        mismo criterio que disponibilidad-mensual)."""
        response = self.client.get(
            "/api/v1/portal/consultorios", {"centroId": 999999}, **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["consultorios"], [])

    def test_consultorios_centro_id_valido_filtra(self):
        response = self.client.get(
            "/api/v1/portal/consultorios", {"centroId": self.centro.id}, **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["consultorios"]), 1)
        self.assertEqual(
            response.data["consultorios"][0]["consultorioId"], self.consultorio.id,
        )
        self.assertEqual(response.data["consultorios"][0]["centroId"], self.centro.id)

    # ── GET /portal/slots — JSON crudo sin medicoNombre ─────────────────

    def test_slots_json_crudo_no_incluye_medico_nombre(self):
        # Fecha futura: los horarios que ya pasaron no se listan.
        fecha = (timezone.now() + timedelta(days=30)).date()
        HorarioDisponible.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha=fecha, hora="09:00", canal="LINEA",
        )

        response = self.client.get(
            "/api/v1/portal/slots",
            {"fecha": fecha.isoformat(), "consultorioId": self.consultorio.id},
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slots = response.json()["slots"]
        self.assertTrue(slots)
        for slot in slots:
            self.assertNotIn("medicoNombre", slot)


class PortalCitasPrivacidadMedicoRegresionTests(APITestCase):
    """
    Regresión: el portal público de pacientes NO debe exponer el nombre
    del médico en NINGÚN punto del flujo. La decisión original de
    ``portal-citas-filtro-clinica`` (REQ-5) dejaba ``medicoNombre`` en
    ``POST /portal/citas`` y ``GET /portal/citas`` a propósito, porque en
    ese momento el ocultamiento pedido aplicaba solo a la selección de
    horario (``GET /portal/slots``). Esa decisión se corrigió: ahora
    ``medicoNombre`` tampoco debe aparecer en la respuesta de reserva ni
    en el historial de "Mis citas" -- el nombre del médico solo se
    muestra en la ficha del check-in por QR del sistema interno
    (``apps.recepcion.uses_case.qr_checkin_usecase``), operado por
    personal de recepción, nunca directamente al paciente.
    """

    def setUp(self):
        # ``nucleo_service._familiares_del_nucleo`` consulta CatFamiliar en
        # el alias de BD "expedientes" (ExpedientesRouter) -- ese alias NO
        # existe bajo `manage.py test` (config/settings.py reemplaza
        # DATABASES por un único sqlite ":memory:" cuando "test" está en
        # sys.argv). Se mockea para devolver "sin familiares": el titular
        # de la sesión igual se gestiona a sí mismo (obtener_nucleo lo
        # incluye siempre primero), que es exactamente lo que necesita este
        # test de regresión de privacidad -- no se está probando la regla
        # de negocio de núcleo familiar acá, esa es responsabilidad de
        # otros tests (inexistentes hoy por la misma limitación de entorno).
        familiares_patcher = mock.patch(
            "apps.portal_citas.services.nucleo_service._familiares_del_nucleo",
            return_value=[],
        )
        self.addCleanup(familiares_patcher.stop)
        familiares_patcher.start()

        self.miembro = PortalMiembro.objects.create(
            no_exp="EXP-003",
            pk_num=0,
            nombre_visible="Paciente Regresion",
            es_titular_login=True,
        )
        self.sesion = PortalSesion.objects.create(
            portal_miembro=self.miembro,
            expira_en=timezone.now() + timedelta(minutes=25),
        )
        self.token = issue_portal_access_token(self.sesion)

        self.centro = CatCentroAtencion.objects.create(
            name="Centro Regresion",
            code="CT-REG-01",
            center_type=CatCentroAtencion.TipoCentro.CLINICA,
            is_active=True,
        )
        self.turno = Turnos.objects.create(name="Matutino", is_active=True)

        usuario = SyUsuario.objects.create(
            usuario="medico.regresion",
            correo="medico.regresion@example.com",
            clave_hash="x",
            est_activo=True,
        )
        DetUsuario.objects.create(
            id_usuario=usuario,
            nombre="Carla",
            paterno="Nunez",
        )
        self.medico = CatMedico.objects.create(id_usuario=usuario)

        self.consultorio = Consultorios.objects.create(
            name="Consultorio Regresion", numero=1, id_turn=self.turno,
            id_center=self.centro, is_active=True,
        )
        rel = RelMedicoConsultorio.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha_inicio=date(2026, 1, 1), is_active=True,
        )
        RelMedicoConsultorioHorario.objects.create(
            rel_medico_consultorio=rel, dia_semana="LUNES",
            hora_inicio="08:00", hora_fin="12:00", canal="LINEA",
        )

        # Bien en el futuro para no chocar con la ventana mínima de
        # cancelación (PORTAL_CANCELACION_VENTANA_HORAS).
        self.fecha_slot = (timezone.now() + timedelta(days=30)).date()
        self.slot = HorarioDisponible.objects.create(
            medico=self.medico, consultorio=self.consultorio,
            fecha=self.fecha_slot, hora="09:00", canal="LINEA",
        )

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_post_citas_no_devuelve_medico_nombre(self):
        response = self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": self.slot.id},
            format="json",
            **self._auth(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("medicoNombre", response.data)

    def test_get_citas_no_devuelve_medico_nombre(self):
        self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": self.slot.id},
            format="json",
            **self._auth(),
        )

        response = self.client.get("/api/v1/portal/citas", **self._auth())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["citas"]), 1)
        self.assertNotIn("medicoNombre", response.data["citas"][0])

    def test_cancelacion_no_rompe_el_flujo_ni_expone_el_medico_nombre(self):
        """La cancelación en sí (``cancelar_cita_usecase``) nunca devolvió
        ``medicoNombre`` -- su contrato de respuesta es solo
        ``{folio, estatus}``, y este change no lo toca. La regresión que
        importa acá es que cancelar sigue funcionando y que el historial
        (``GET /portal/citas``) sigue sin exponer ``medicoNombre`` para esa
        cita después de cancelarla."""
        post_response = self.client.post(
            "/api/v1/portal/citas",
            {"miembroId": str(self.miembro.id), "slotId": self.slot.id},
            format="json",
            **self._auth(),
        )
        folio = post_response.data["folio"]

        cancel_response = self.client.patch(
            f"/api/v1/portal/citas/{folio}/cancelar",
            {},
            format="json",
            **self._auth(),
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["estatus"], "cancelada")

        get_response = self.client.get("/api/v1/portal/citas", **self._auth())
        self.assertNotIn("medicoNombre", get_response.data["citas"][0])
