"""
P-03: enganches en el flujo actual de recepción (validaciones A1 a A3 y el
estado por miembro en la búsqueda del expediente).

- lookup_patient agrega ``adscripcion`` a cada miembro con las filas de
  SERMED que ya leyó, y nunca se rompe por P-03.
- Fichas (POST /visits), citas (POST /citas) y check-in por folio validan que
  la atención de medicina general sea en el consultorio familiar, salvo
  excepción con permiso y motivo.
- POST /citas con idCitaAfectada marca la cita por reagendar en la misma
  transacción.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.recepcion.models import AdscripcionCitaAfectada, AdscripcionPaciente, CitaMedica, EstatusCita
from apps.recepcion.tests._adscripcion_base import fila_sermed
from apps.recepcion.tests.test_adscripcion_api import AdscripcionApiBase, ESCRIBIR, LEER
from apps.recepcion.uses_case.adscripcion_usecase import (
    AdscripcionError,
    Operador,
    validar_consultorio_familiar,
)
from apps.recepcion.uses_case.visit_queue_usecase import lookup_patient
from django.test import RequestFactory

EXCEPCION = "recepcion:consultorio_familiar:excepcion"
FICHAS = ["recepcion:citas:read", "recepcion:fichas:medicina_general:read", "recepcion:fichas:medicina_general:create"]


def fila_completa(no_exp="EXP-1", cd_clinica="5", estatus="ACTIVO", pk_num=None):
    """Fila con los campos que lookup_patient arma por miembro."""
    fila = fila_sermed(cd_clinica=cd_clinica, estatus=estatus, pk_num=pk_num)
    fila.update({"DS_PATERNO": "PEREZ", "DS_MATERNO": "LOPEZ", "DS_NOMBRE": "JUAN"})
    fila["NO_EXPF" if pk_num else "NO_EXP"] = no_exp
    return fila


class ValidarConsultorioFamiliarTests(AdscripcionApiBase):
    """A1, A2 y A3 a nivel de caso de uso."""

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().post("/")
        usuario = self._usuario("valida", [])
        self.sin_excepcion = Operador(usuario=usuario, id_centro_atencion=self.clinica5.id)
        self.con_excepcion = Operador(usuario=usuario, id_centro_atencion=self.clinica5.id, puede_excepcion=True)

    def _validar(self, consultorio, *, servicio="medicina_general", motivo=None, operador=None, paciente=None):
        with self._sermed(titular=fila_sermed()):
            validar_consultorio_familiar(
                paciente=paciente if paciente is not None else self.paciente,
                consultorio_id=consultorio.pk if consultorio else None,
                servicio_tipo=servicio, excepcion_motivo=motivo,
                operador=operador or self.sin_excepcion, request=self.request, recurso="ficha",
            )

    def test_mismo_consultorio_pasa(self):
        self._adscribir(self.paciente, self.cons5a)
        self._validar(self.cons5a)

    def test_otro_consultorio_se_detiene(self):
        self._adscribir(self.paciente, self.cons5a)
        with self.assertRaises(AdscripcionError) as ctx:
            self._validar(self.cons5b)
        self.assertEqual(ctx.exception.code, "CONSULTORIO_FAMILIAR_DIFERENTE")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.details["estado"], "VIGENTE")
        self.assertEqual(ctx.exception.details["idConsultorioFamiliar"], self.cons5a.id)

    def test_no_coincide_se_detiene_aunque_sea_el_mismo_consultorio(self):
        self._adscribir(self.paciente, self.cons5a)
        self._consultorio(self.clinica7, 1)
        with self._sermed(titular=fila_sermed(cd_clinica="7")):
            with self.assertRaises(AdscripcionError) as ctx:
                validar_consultorio_familiar(
                    paciente=self.paciente, consultorio_id=self.cons5a.pk, servicio_tipo="medicina_general",
                    operador=self.sin_excepcion, request=self.request, recurso="ficha",
                )
        self.assertEqual(ctx.exception.details["estado"], "NO_COINCIDE")

    def test_sin_adscripcion_pasa(self):
        self._validar(self.cons5b)

    def test_especialidad_no_se_valida(self):
        self._adscribir(self.paciente, self.cons5a)
        self._validar(self.cons5b, servicio="especialidad")

    def test_sin_consultorio_o_sin_paciente_pasa(self):
        self._adscribir(self.paciente, self.cons5a)
        self._validar(None)
        with self._sermed(titular=fila_sermed()):
            validar_consultorio_familiar(
                paciente=None, consultorio_id=self.cons5b.pk, servicio_tipo="medicina_general",
                operador=self.sin_excepcion, request=self.request, recurso="ficha",
            )

    def test_excepcion_con_permiso_y_motivo_pasa_y_se_audita(self):
        self._adscribir(self.paciente, self.cons5a)
        self._validar(self.cons5b, motivo="Su médico no vino hoy", operador=self.con_excepcion)
        evento = AuditoriaEvento.objects.get(accion="ADSCRIPCION_EXCEPCION")
        self.assertEqual(evento.meta["motivo"], "Su médico no vino hoy")
        self.assertEqual(evento.meta["idConsultorio"], self.cons5b.id)
        self.assertEqual(evento.meta["recurso"], "ficha")

    def test_excepcion_sin_permiso(self):
        self._adscribir(self.paciente, self.cons5a)
        with self.assertRaises(AdscripcionError) as ctx:
            self._validar(self.cons5b, motivo="Su médico no vino hoy")
        self.assertEqual(ctx.exception.code, "EXCEPCION_NO_PERMITIDA")
        self.assertEqual(ctx.exception.status_code, 403)


class BusquedaExpedienteTests(AdscripcionApiBase):
    """lookup_patient: estado de P-03 por miembro, sin volver a consultar SERMED."""

    BUSCAR = "apps.recepcion.uses_case.visit_queue_usecase.buscar_expediente"

    def _buscar(self, titular, familiares=()):
        with mock.patch(self.BUSCAR, return_value={"empleados": [titular], "familiares": list(familiares)}):
            return lookup_patient("EXP-1")

    def test_cada_miembro_trae_su_estado(self):
        self._adscribir(self.paciente, self.cons5a)
        self._consultorio(self.clinica7, 1)
        resultado = self._buscar(
            fila_completa(cd_clinica="5"), [fila_completa(cd_clinica="7", pk_num=2)],
        )
        titular = resultado["titular"]["adscripcion"]
        self.assertEqual(titular["estado"], "VIGENTE")
        self.assertEqual(titular["idConsultorio"], self.cons5a.id)
        self.assertEqual(titular["consultorio"], self.cons5a.name)
        hijo = resultado["dependientes"][0]["adscripcion"]
        self.assertEqual(hijo["estado"], "SIN_ADSCRIPCION")
        self.assertEqual(hijo["idCentroSermed"], self.clinica7.id)

    def test_no_coincide_avisa_las_citas(self):
        self._adscribir(self.paciente, self.cons5a)
        self._consultorio(self.clinica7, 1)
        self._cita(self.paciente, self.cons5a)
        resultado = self._buscar(fila_completa(cd_clinica="7"))
        adscripcion = resultado["titular"]["adscripcion"]
        self.assertEqual(adscripcion["estado"], "NO_COINCIDE")
        self.assertTrue(adscripcion["requiereReasignar"])
        self.assertEqual(adscripcion["citasFuturas"], 1)

    def test_si_p03_falla_la_busqueda_sigue(self):
        with mock.patch(
            "apps.recepcion.services.adscripcion_evaluacion.estado_de_miembro", side_effect=RuntimeError("falla"),
        ):
            resultado = self._buscar(fila_completa())
        self.assertIsNone(resultado["titular"]["adscripcion"])
        self.assertEqual(resultado["titular"]["noExp"], "EXP-1")


class FichaConConsultorioDistintoTests(AdscripcionApiBase):
    """A1 en POST /visits (Generar ficha de consulta)."""

    def test_ficha_en_otro_consultorio_responde_409(self):
        self._login("recepcion_ficha", FICHAS)
        self._adscribir(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed()):
            response = self._post("/api/v1/visits", {
                "idPaciente": self.paciente.pk, "arrivalType": "walk_in",
                "serviceType": "medicina_general", "consultorioId": self.cons5b.pk,
            })
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "CONSULTORIO_FAMILIAR_DIFERENTE")
        self.assertEqual(response.data["details"]["idConsultorioFamiliar"], self.cons5a.id)


class CitaConConsultorioDistintoTests(AdscripcionApiBase):
    """A1 en POST /citas y el reagendado con idCitaAfectada."""

    CREAR = "apps.recepcion.views.citas_views.CitasRepository.create"

    def setUp(self):
        super().setUp()
        self._login("recepcion_citas", ["recepcion:citas:read", "recepcion:citas:write", LEER, ESCRIBIR])
        clinica = mock.patch("apps.recepcion.views.citas_views.centro_del_paciente", return_value=None)
        clinica.start()
        self.addCleanup(clinica.stop)

    def _crear_real(self, **kwargs):
        cita = CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), patient=self.paciente, medico_id=kwargs["medico_id"],
            consultorio_id=kwargs["consultorio_id"], fecha_hora=kwargs["fecha_hora"],
            servicio_tipo=kwargs["servicio_tipo"],
        )
        return {"id": cita.id, "folio": cita.folio}

    def _body(self, consultorio, **extra):
        return {
            "idPaciente": self.paciente.pk, "medicoId": self.medico.id, "consultorioId": consultorio.pk,
            "fechaHora": (timezone.now() + timedelta(days=5)).isoformat(), **extra,
        }

    def test_cita_en_otro_consultorio_responde_409(self):
        self._adscribir(self.paciente, self.cons5a)
        with self._sermed(titular=fila_sermed()), mock.patch(self.CREAR, side_effect=self._crear_real) as crear:
            response = self._post("/api/v1/citas", self._body(self.cons5b))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "CONSULTORIO_FAMILIAR_DIFERENTE")
        crear.assert_not_called()

    def test_reagendar_marca_la_cita_afectada(self):
        anterior = self._adscribir(self.paciente, self.cons5a)
        cancelada = self._cita(self.paciente, self.cons5a, estatus=EstatusCita.CANCELADA)
        AdscripcionPaciente.objects.filter(pk=anterior.pk).update(
            estatus="CERRADA", fecha_fin=anterior.fecha_inicio, id_usuario_cierre=1, motivo_cierre="REASIGNACION",
        )
        nueva_adscripcion = self._adscribir(self.paciente, self.cons5b)
        afectada = AdscripcionCitaAfectada.objects.create(
            adscripcion=nueva_adscripcion, cita_cancelada=cancelada, id_usuario_creacion=1,
        )
        with self._sermed(titular=fila_sermed()), mock.patch(self.CREAR, side_effect=self._crear_real):
            response = self._post("/api/v1/citas", self._body(self.cons5b, idCitaAfectada=afectada.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        afectada.refresh_from_db()
        self.assertEqual(afectada.estatus, AdscripcionCitaAfectada.Estatus.REAGENDADA)
        self.assertEqual(afectada.cita_nueva_id, response.data["id"])

    def test_si_el_reagendado_falla_no_queda_la_cita(self):
        self._adscribir(self.paciente, self.cons5b)
        with self._sermed(titular=fila_sermed()), mock.patch(self.CREAR, side_effect=self._crear_real):
            response = self._post("/api/v1/citas", self._body(self.cons5b, idCitaAfectada=999999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CitaMedica.objects.filter(patient=self.paciente).exists())


class CheckinConConsultorioDistintoTests(AdscripcionApiBase):
    """A2 y A3 en POST /citas/checkin/confirmar-folio."""

    URL = "/api/v1/citas/checkin/confirmar-folio"

    def setUp(self):
        super().setUp()
        self._adscribir(self.paciente, self.cons5a)
        self.cita = CitaMedica.objects.create(
            folio=CitaMedica.generar_folio(), patient=self.paciente, medico=self.medico,
            consultorio=self.cons5b, fecha_hora=timezone.localtime(timezone.now()) + timedelta(hours=2),
            servicio_tipo="medicina_general", estatus=EstatusCita.AGENDADA,
        )
        titular = fila_completa()
        expediente = mock.patch(
            "apps.recepcion.services.vigencia_service.buscar_expediente",
            return_value={"empleados": [titular], "familiares": []},
        )
        expediente.start()
        self.addCleanup(expediente.stop)

    def test_cita_de_otro_consultorio_responde_409(self):
        self._login("recepcion_checkin", FICHAS)
        response = self._post(self.URL, {"folio": self.cita.folio})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "CONSULTORIO_FAMILIAR_DIFERENTE")

    def test_con_excepcion_se_atiende(self):
        self._login("recepcion_excepcion", [*FICHAS, LEER, EXCEPCION])
        response = self._post(self.URL, {"folio": self.cita.folio, "excepcionConsultorioFamiliar": "Médico ausente"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(AuditoriaEvento.objects.filter(accion="ADSCRIPCION_EXCEPCION").exists())

    def test_candidatos_traen_el_id_del_paciente(self):
        self._login("recepcion_checkin", FICHAS)
        response = self.client.get("/api/v1/citas/checkin/candidatos", {"folio": self.cita.folio})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["candidatos"][0]["idPaciente"], self.paciente.pk)

    def test_folio_inexistente_sigue_el_flujo_actual(self):
        self._login("recepcion_checkin", FICHAS)
        response = self._post(self.URL, {"folio": "CIT-NOEXISTE"})
        self.assertNotEqual(response.data.get("code"), "CONSULTORIO_FAMILIAR_DIFERENTE")
