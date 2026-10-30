"""
P-03: API de la adscripción a consultorio familiar (/api/v1/adscripcion/...).
Sesión por cookie, CSRF en escrituras y permisos atómicos, como el resto de
recepción.
"""

from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APIClient

from apps.administracion.models import RelRolPermiso, RelUsuarioRol
from apps.authentication.infrastructure.policy_store import PolicyStore
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import MotivoCita, Permisos, Roles
from apps.recepcion.models import (
    AdscripcionCitaAfectada,
    AdscripcionClinicaCentro,
    AdscripcionConsultorio,
    AdscripcionPaciente,
)
from apps.recepcion.tests._adscripcion_base import AdscripcionTestBase, fila_sermed

BASE = "/api/v1/adscripcion"
LEER = "recepcion:consultorio_familiar:read"
ESCRIBIR = "recepcion:consultorio_familiar:write"
TODOS = "recepcion:consultorio_familiar:todos_centros"
CONFIG = "admin:catalogos:consultorio_familiar:config"
LEER_CENTROS = "admin:catalogos:centros_atencion:read"  # dependencia de CONFIG
LEER_CONSULTORIOS = "admin:catalogos:consultorios:read"  # dependencia de CONFIG


class AdscripcionApiBase(AdscripcionTestBase):
    client_class = APIClient

    def setUp(self):
        super().setUp()
        self.cons5a = self._consultorio(self.clinica5, 1)
        self.cons5b = self._consultorio(self.clinica5, 2)
        self.paciente = self._paciente()

    def _usuario(self, username, permisos, centro=None):
        user = SyUsuario.objects.create(
            usuario=username, correo=f"{username}@example.com",
            clave_hash=make_password("Clave_123456"), est_activo=True,
            cambiar_clave=False, terminos_acept=True,
        )
        DetUsuario.objects.create(
            id_usuario=user, nombre=username, paterno="Test", materno="User",
            id_centro_atencion=centro if centro is not None else self.clinica5,
        )
        rol = Roles.objects.create(rol=f"ROL_{username}", desc_rol="Rol", landing_route="/recepcion")
        RelUsuarioRol.objects.create(id_usuario=user, id_rol=rol, is_primary=True)
        for codigo in permisos:
            permiso, _ = Permisos.objects.get_or_create(codigo=codigo, defaults={"descripcion": codigo, "is_active": True})
            RelRolPermiso.objects.get_or_create(id_rol=rol, id_permiso=permiso)
        return user

    def _login(self, username, permisos, centro=None):
        user = self._usuario(username, permisos, centro)
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


class MigracionesDeDatosTests(AdscripcionApiBase):
    def test_crean_los_permisos_y_el_motivo(self):
        codigos = set(
            Permisos.objects.filter(codigo__contains="consultorio_familiar").values_list("codigo", flat=True)
        )
        self.assertEqual(codigos, {LEER, ESCRIBIR, TODOS, CONFIG, "recepcion:consultorio_familiar:excepcion"})
        self.assertTrue(MotivoCita.objects.filter(name="Cambio de consultorio familiar", aplica_a="CANCELACION").exists())


class ConsultaApiTests(AdscripcionApiBase):
    def test_sin_permiso_responde_403(self):
        self._login("sin_p03", ["recepcion:citas:read"])
        response = self.client.get(f"{BASE}/pacientes/{self.paciente.pk}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_estado_del_paciente(self):
        self._login("lector", [LEER])
        cita = self._cita(self.paciente, self.cons5a)
        self._adscribir(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed(cd_clinica="7")):
            self._consultorio(self.clinica7, 1)
            response = self.client.get(f"{BASE}/pacientes/{self.paciente.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["estado"], "NO_COINCIDE")
        self.assertTrue(response.data["requiereReasignar"])
        self.assertEqual(response.data["idCentroSermed"], self.clinica7.id)
        self.assertEqual(response.data["adscripcion"]["idConsultorio"], self.cons5a.id)
        self.assertEqual([c["idCita"] for c in response.data["citasFuturas"]], [cita.id])

    def test_paciente_inexistente(self):
        self._login("lector", [LEER])
        with self._sermed(titular=fila_sermed()):
            response = self.client.get(f"{BASE}/pacientes/999999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_opciones_con_la_sugerida(self):
        self._login("lector", [LEER])
        self._adscribir(self._paciente(no_exp="EXP-OTRO"), self.cons5a)
        with self._sermed(titular=fila_sermed()):
            response = self.client.get(f"{BASE}/opciones", {"idPaciente": self.paciente.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["estado"], "SIN_ADSCRIPCION")
        opciones = response.data["opciones"]
        self.assertEqual([o["consultorioId"] for o in opciones], [self.cons5b.id, self.cons5a.id])
        self.assertTrue(opciones[0]["sugerida"])

    def test_previsualizar(self):
        self._login("lector", [LEER])
        actual = self._adscribir(self.paciente, self.cons5a)
        cita = self._cita(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed()):
            response = self._post(f"{BASE}/previsualizar", {"idPaciente": self.paciente.pk, "consultorioId": self.cons5b.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["sinCambios"])
        self.assertEqual(response.data["idAdscripcionActual"], actual.id)
        self.assertEqual([c["idCita"] for c in response.data["citasACancelar"]], [cita.id])

    def test_historial(self):
        self._login("lector", [LEER])
        self._adscribir(self.paciente, self.cons5a)
        response = self.client.get(f"{BASE}/pacientes/{self.paciente.pk}/historial")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["estatus"], "ACTIVA")


class AdscribirApiTests(AdscripcionApiBase):
    def _body(self, consultorio, **extra):
        return {
            "idPaciente": self.paciente.pk, "consultorioId": consultorio.pk,
            "idAdscripcionEsperada": None, "citasACancelar": [], "origen": "CHECKIN",
            "fueSugerida": True, **extra,
        }

    def test_sin_csrf_responde_403(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        with self._sermed(titular=fila_sermed()):
            response = self.client.post(BASE, self._body(self.cons5a), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_solo_lectura_no_puede_adscribir(self):
        self._login("lector", [LEER])
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(self.cons5a))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_adscribe(self):
        user = self._login("recepcion", [LEER, ESCRIBIR])
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(self.cons5a))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["sinCambios"])
        adscripcion = AdscripcionPaciente.objects.get(paciente=self.paciente)
        self.assertEqual(response.data["adscripcion"]["idAdscripcion"], adscripcion.id)
        self.assertEqual(adscripcion.id_usuario_creacion, user.id_usuario)

    def test_reasigna_y_cancela_citas(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        actual = self._adscribir(self.paciente, self.cons5a)
        cita = self._cita(self.paciente, self.cons5a)
        motivo = MotivoCita.objects.get(name="Cambio de consultorio familiar")
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(
                self.cons5b, idAdscripcionEsperada=actual.id, citasACancelar=[cita.id],
                motivoCancelacionId=motivo.pk,
            ))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual([c["idCita"] for c in response.data["citasCanceladas"]], [cita.id])
        self.assertEqual(len(response.data["citasPorReagendar"]), 1)

    def test_mismo_consultorio_responde_200_sin_cambios(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        actual = self._adscribir(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(self.cons5a, idAdscripcionEsperada=actual.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["sinCambios"])

    def test_error_de_negocio_con_detalle(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        actual = self._adscribir(self.paciente, self.cons5a)
        cita = self._cita(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(self.cons5b, idAdscripcionEsperada=actual.id))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "CITAS_MODIFICADAS")
        self.assertEqual([c["idCita"] for c in response.data["details"]["citas"]], [cita.id])

    def test_operador_de_otro_centro(self):
        self._login("recepcion7", [LEER, ESCRIBIR], centro=self.clinica7)
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(self.cons5a))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "CENTRO_NO_PERMITIDO")

    def test_perfil_central_opera_cualquier_centro(self):
        self._login("central", [LEER, ESCRIBIR, TODOS], centro=self.clinica7)
        with self._sermed(titular=fila_sermed()):
            response = self._post(BASE, self._body(self.cons5a))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_datos_invalidos(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        response = self._post(BASE, {"idPaciente": self.paciente.pk})
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


class CitasPorReagendarApiTests(AdscripcionApiBase):
    def setUp(self):
        super().setUp()
        actual = self._adscribir(self.paciente, self.cons5a)
        cita = self._cita(self.paciente, self.cons5a)
        nueva = self._adscribir_cerrando(actual)
        self.afectada = AdscripcionCitaAfectada.objects.create(
            adscripcion=nueva, cita_cancelada=cita, id_usuario_creacion=1,
        )

    def _adscribir_cerrando(self, actual):
        AdscripcionPaciente.objects.filter(pk=actual.pk).update(
            estatus="CERRADA", fecha_fin=actual.fecha_inicio, id_usuario_cierre=1, motivo_cierre="REASIGNACION",
        )
        return self._adscribir(self.paciente, self.cons5b)

    def test_lista_por_paciente(self):
        self._login("lector", [LEER])
        response = self.client.get(f"{BASE}/citas-por-reagendar", {"idPaciente": self.paciente.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["idCitaAfectada"] for c in response.data["items"]], [self.afectada.id])

    def test_lista_por_centro(self):
        self._login("lector", [LEER])
        response = self.client.get(f"{BASE}/citas-por-reagendar", {"centroId": self.clinica5.id})
        self.assertEqual(len(response.data["items"]), 1)

    def test_sin_filtro_lista_las_del_centro_del_operador(self):
        self._login("lector", [LEER])
        response = self.client.get(f"{BASE}/citas-por-reagendar")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["idCitaAfectada"] for c in response.data["items"]], [self.afectada.id])

    def test_sin_filtro_y_de_otro_centro_no_ve_nada(self):
        self._login("lector7", [LEER], centro=self.clinica7)
        response = self.client.get(f"{BASE}/citas-por-reagendar")
        self.assertEqual(response.data["items"], [])

    def test_trae_el_consultorio_nuevo_para_reagendar(self):
        self._login("lector", [LEER])
        item = self.client.get(f"{BASE}/citas-por-reagendar", {"idPaciente": self.paciente.pk}).data["items"][0]
        self.assertEqual(item["idPaciente"], self.paciente.pk)
        self.assertEqual(item["idConsultorioNuevo"], self.cons5b.id)
        self.assertEqual(item["consultorioNuevo"], self.cons5b.name)
        self.assertEqual(item["idCentroAtencion"], self.clinica5.id)

    def test_descartar(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        response = self._post(f"{BASE}/citas-por-reagendar/{self.afectada.id}/descartar", {"motivo": "Ya no la necesita"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.afectada.refresh_from_db()
        self.assertEqual(self.afectada.estatus, AdscripcionCitaAfectada.Estatus.DESCARTADA)


class ConfiguracionApiTests(AdscripcionApiBase):
    def test_sin_permiso_de_configuracion(self):
        self._login("recepcion", [LEER, ESCRIBIR])
        response = self._post(f"{BASE}/config/clinicas", {"claveClinicaSermed": "9", "idCentroAtencion": self.clinica5.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_configuracion_exige_leer_consultorios(self):
        self._login("admin_p03", [CONFIG, LEER_CENTROS])
        response = self.client.get(f"{BASE}/config/consultorios")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_equivalencias(self):
        self._login("admin_p03", [CONFIG, LEER_CENTROS, LEER_CONSULTORIOS])
        response = self._post(f"{BASE}/config/clinicas", {"claveClinicaSermed": " 9 ", "idCentroAtencion": self.clinica5.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["claveClinicaSermed"], "9")
        duplicada = self._post(f"{BASE}/config/clinicas", {"claveClinicaSermed": "9", "idCentroAtencion": self.clinica7.id})
        self.assertEqual(duplicada.status_code, status.HTTP_409_CONFLICT)
        baja = self._patch(f"{BASE}/config/clinicas/{response.data['idClinicaCentro']}", {"estaActivo": False})
        self.assertEqual(baja.status_code, status.HTTP_200_OK)
        self.assertFalse(AdscripcionClinicaCentro.objects.get(clave_clinica_sermed="9").esta_activo)
        listado = self.client.get(f"{BASE}/config/clinicas")
        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        self.assertIn("9", [c["claveClinicaSermed"] for c in listado.data["items"]])

    def test_consultorios_familiares(self):
        self._login("admin_p03", [CONFIG, LEER_CENTROS, LEER_CONSULTORIOS])
        nuevo = self._consultorio(self.clinica5, 3, familiar=False)
        response = self._post(f"{BASE}/config/consultorios", {"consultorioId": nuevo.pk, "capacidadMaxima": 200})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        repetido = self._post(f"{BASE}/config/consultorios", {"consultorioId": nuevo.pk})
        self.assertEqual(repetido.status_code, status.HTTP_409_CONFLICT)
        cambio = self._patch(
            f"{BASE}/config/consultorios/{response.data['idAdscripcionConsultorio']}", {"capacidadMaxima": None},
        )
        self.assertEqual(cambio.status_code, status.HTTP_200_OK)
        self.assertIsNone(AdscripcionConsultorio.objects.get(consultorio=nuevo).capacidad_maxima)
        listado = self.client.get(f"{BASE}/config/consultorios", {"centroId": self.clinica5.id})
        self.assertEqual(
            {c["consultorioId"] for c in listado.data["items"]}, {self.cons5a.id, self.cons5b.id, nuevo.id},
        )
        self.assertIn("carga", listado.data["items"][0])

    def test_capacidad_invalida(self):
        self._login("admin_p03", [CONFIG, LEER_CENTROS, LEER_CONSULTORIOS])
        nuevo = self._consultorio(self.clinica5, 3, familiar=False)
        response = self._post(f"{BASE}/config/consultorios", {"consultorioId": nuevo.pk, "capacidadMaxima": 0})
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
