"""
P-03 · Asignación por familia (/api/v1/adscripcion/familia).

GET: el núcleo del expediente con lo que hace falta para asignar en un solo
paso (estado de cada miembro, opciones y citas a cancelar por opción). No
registra a nadie. POST: registra a los miembros marcados que falten y los
asigna en UNA transacción; si uno falla no queda nada escrito.
"""

from contextlib import contextmanager
from unittest import mock

from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import MotivoCita
from apps.consulta_medica.models import Patient
from apps.recepcion.models import AdscripcionCitaAfectada, AdscripcionConsultorio, AdscripcionPaciente, EstatusCita
from apps.recepcion.tests._adscripcion_base import BUSCAR_EXPEDIENTE
from apps.recepcion.tests.test_adscripcion_api import ESCRIBIR, LEER, TODOS, AdscripcionApiBase

LOOKUP = "apps.recepcion.uses_case.visit_queue_usecase.buscar_expediente"
URL = "/api/v1/adscripcion/familia"
NO_EXP = "3498"


def titular(cd_clinica="5", estatus="ACTIVO"):
    return {
        "NO_EXP": NO_EXP, "DS_PATERNO": "PEREZ", "DS_MATERNO": "LOPEZ", "DS_NOMBRE": "JUAN",
        "ESTATUS": estatus, "CD_CLINICA": cd_clinica,
    }


def familiar(pk_num, nombre, cd_clinica="5", estatus="ACTIVO"):
    return {
        "NO_EXPF": NO_EXP, "PK_NUM": pk_num, "DS_PATERNO": "PEREZ", "DS_MATERNO": "LOPEZ",
        "DS_NOMBRE": nombre, "CD_PARENTESCO": "HIJO", "ESTATUS": estatus, "CD_CLINICA": cd_clinica,
    }


class FamiliaBase(AdscripcionApiBase):
    def setUp(self):
        super().setUp()
        self.motivo = MotivoCita.objects.get(name="Cambio de consultorio familiar")

    @contextmanager
    def _familia(self, *familiares, cd_clinica="5"):
        # La búsqueda del expediente importa buscar_expediente en su módulo.
        datos = {"empleados": [titular(cd_clinica)], "familiares": list(familiares)}
        with mock.patch(BUSCAR_EXPEDIENTE, return_value=datos), mock.patch(LOOKUP, return_value=datos):
            yield

    def _miembro(self, respuesta, pk_num):
        return next(m for m in respuesta.data["miembros"] if m["pkNum"] == pk_num)

    def _asignacion(self, pk_num, consultorio, *, esperada=None, citas=(), sugerida=True):
        return {
            "pkNum": pk_num, "consultorioId": consultorio.id, "idAdscripcionEsperada": esperada,
            "citasACancelar": list(citas), "fueSugerida": sugerida,
        }

    def _confirmar(self, *asignaciones, motivo=None):
        return self._post(URL, {
            "noExp": NO_EXP, "asignaciones": list(asignaciones),
            "motivoCancelacionId": motivo, "origen": "CHECKIN",
        })


class ConsultarFamiliaTests(FamiliaBase):
    def test_consultar_no_registra_a_nadie(self):
        self._login("lee", [LEER])
        with self._familia(familiar(1, "ANA"), familiar(2, "LUIS")):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertFalse(Patient.objects.filter(no_exp=NO_EXP).exists())
        self.assertEqual(respuesta.data["idCentroAtencion"], self.clinica5.id)
        self.assertEqual([m["pkNum"] for m in respuesta.data["miembros"]], [0, 1, 2])
        for miembro in respuesta.data["miembros"]:
            self.assertEqual(miembro["estado"], "SIN_ADSCRIPCION")
            self.assertTrue(miembro["elegible"])
            self.assertTrue(miembro["preseleccionado"])
            self.assertIsNone(miembro["idPaciente"])
        self.assertEqual([o["consultorioId"] for o in respuesta.data["opciones"]], [self.cons5a.id, self.cons5b.id])
        self.assertTrue(respuesta.data["opciones"][0]["sugerida"])
        self.assertIsNone(respuesta.data["motivoSinOpciones"])

    def test_no_vigente_y_otra_clinica_no_son_elegibles(self):
        self._login("lee", [LEER])
        with self._familia(familiar(1, "ANA", estatus="BAJA"), familiar(2, "LUIS", cd_clinica="7")):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        baja = self._miembro(respuesta, 1)
        otra = self._miembro(respuesta, 2)
        self.assertEqual((baja["elegible"], baja["razon"]), (False, "NO_VIGENTE"))
        self.assertEqual((otra["elegible"], otra["razon"]), (False, "OTRA_CLINICA"))
        self.assertFalse(baja["preseleccionado"])

    def test_ya_asignado_aparece_desmarcado_con_las_citas_por_opcion(self):
        ana = self._paciente(NO_EXP, 1)
        actual = self._adscribir(ana, self.cons5b)
        cita = self._cita(ana, self.cons5b)
        self._login("lee", [LEER])
        with self._familia(familiar(1, "ANA")):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        miembro = self._miembro(respuesta, 1)
        self.assertEqual(miembro["estado"], "VIGENTE")
        self.assertTrue(miembro["elegible"])
        self.assertFalse(miembro["preseleccionado"])
        self.assertEqual(miembro["idPaciente"], ana.pk)
        self.assertEqual(miembro["idAdscripcionActual"], actual.id)
        self.assertEqual(miembro["idConsultorioActual"], self.cons5b.id)
        citas = miembro["citasACancelarPorConsultorio"]
        self.assertEqual([c["idCita"] for c in citas[str(self.cons5a.id)]], [cita.id])
        self.assertEqual(citas[str(self.cons5b.id)], [])
        # La familia ya está en el 5b: es el sugerido.
        sugerida = next(o for o in respuesta.data["opciones"] if o["sugerida"])
        self.assertEqual(sugerida["consultorioId"], self.cons5b.id)
        self.assertTrue(sugerida["esDeLaFamilia"])

    def test_familia_separada_si_su_consultorio_esta_lleno(self):
        lleno = self._consultorio(self.clinica5, 3, capacidad=1)
        self._adscribir(self._paciente(NO_EXP, 1), lleno)
        self._login("lee", [LEER])
        with self._familia(familiar(1, "ANA"), familiar(2, "LUIS")):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        self.assertTrue(respuesta.data["familiaSeparada"])
        self.assertNotIn(lleno.id, [o["consultorioId"] for o in respuesta.data["opciones"]])

    def test_sin_opciones_dice_por_que(self):
        self._login("lee", [LEER], centro=self.clinica7)
        sin_medico = self._consultorio(self.clinica7, 1, con_medico=False)
        with self._familia(cd_clinica="7"):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})
        self.assertEqual(respuesta.data["opciones"], [])
        self.assertEqual(respuesta.data["motivoSinOpciones"], "SIN_MEDICO")

        AdscripcionConsultorio.objects.filter(consultorio=sin_medico).update(esta_activo=False)
        chico = self._consultorio(self.clinica7, 2, capacidad=1)
        self._adscribir(self._paciente("OTRO", 0), chico, clave="7")
        with self._familia(cd_clinica="7"):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})
        self.assertEqual(respuesta.data["motivoSinOpciones"], "TODOS_LLENOS")

    def test_sin_consultorios_familiares(self):
        self._login("lee", [LEER], centro=self.clinica7)
        with self._familia(cd_clinica="7"):
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        self.assertEqual(respuesta.data["motivoSinOpciones"], "SIN_CONSULTORIOS")
        self.assertFalse(self._miembro(respuesta, 0)["elegible"])

    def test_recien_nacido_va_con_la_clinica_del_titular(self):
        bebe = self._recien_nacido(NO_EXP)
        self._login("lee", [LEER])
        with self._familia():
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        miembro = next(m for m in respuesta.data["miembros"] if m["idPaciente"] == bebe.pk)
        self.assertTrue(miembro["elegible"])
        self.assertEqual(miembro["estado"], "SIN_ADSCRIPCION")

    def test_sin_permiso_de_lectura(self):
        self._login("nadie", [])
        with self._familia():
            respuesta = self.client.get(URL, {"noExp": NO_EXP})

        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)


class AsignarFamiliaTests(FamiliaBase):
    def test_registra_y_asigna_solo_a_los_marcados(self):
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia(familiar(1, "ANA"), familiar(2, "LUIS")):
            respuesta = self._confirmar(self._asignacion(0, self.cons5a), self._asignacion(1, self.cons5a))

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(
            set(Patient.objects.filter(no_exp=NO_EXP).values_list("pk_num", flat=True)), {0, 1},
        )
        activas = AdscripcionPaciente.objects.filter(
            paciente__no_exp=NO_EXP, estatus=AdscripcionPaciente.Estatus.ACTIVA,
        )
        self.assertEqual({a.consultorio_id for a in activas}, {self.cons5a.id})
        self.assertEqual(activas.count(), 2)
        self.assertEqual([r["pkNum"] for r in respuesta.data["resultados"]], [0, 1])
        self.assertEqual(AuditoriaEvento.objects.filter(accion="ADSCRIPCION_ASIGNAR", resultado="SUCCESS").count(), 2)

    def test_si_un_miembro_falla_no_se_graba_nada(self):
        otro = self._consultorio(self.clinica7, 1)
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia(familiar(1, "ANA")):
            respuesta = self._confirmar(self._asignacion(0, self.cons5a), self._asignacion(1, otro))

        self.assertEqual(respuesta.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(respuesta.json()["code"], "CONSULTORIO_NO_ELEGIBLE")
        self.assertEqual(respuesta.json()["details"]["pkNum"], 1)
        self.assertFalse(Patient.objects.filter(no_exp=NO_EXP).exists())
        self.assertFalse(AdscripcionPaciente.objects.filter(paciente__no_exp=NO_EXP).exists())

    def test_la_capacidad_cuenta_a_todo_el_lote(self):
        chico = self._consultorio(self.clinica5, 3, capacidad=1)
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia(familiar(1, "ANA")):
            respuesta = self._confirmar(self._asignacion(0, chico), self._asignacion(1, chico))

        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.json()["code"], "CONSULTORIO_LLENO")
        self.assertEqual(respuesta.json()["details"]["pkNum"], 1)
        self.assertFalse(AdscripcionPaciente.objects.filter(paciente__no_exp=NO_EXP).exists())

    def test_mover_a_un_familiar_cancela_sus_citas(self):
        ana = self._paciente(NO_EXP, 1)
        actual = self._adscribir(ana, self.cons5b)
        cita = self._cita(ana, self.cons5b)
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia(familiar(1, "ANA")):
            respuesta = self._confirmar(
                self._asignacion(0, self.cons5a),
                self._asignacion(1, self.cons5a, esperada=actual.id, citas=[cita.id]),
                motivo=self.motivo.id,
            )

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        cita.refresh_from_db()
        self.assertEqual(cita.estatus, EstatusCita.CANCELADA)
        self.assertTrue(AdscripcionCitaAfectada.objects.filter(cita_cancelada=cita).exists())
        resultado = next(r for r in respuesta.data["resultados"] if r["pkNum"] == 1)
        self.assertEqual([c["idCita"] for c in resultado["citasCanceladas"]], [cita.id])

    def test_si_otro_la_cambio_antes_rechaza(self):
        ana = self._paciente(NO_EXP, 1)
        self._adscribir(ana, self.cons5b)
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia(familiar(1, "ANA")):
            respuesta = self._confirmar(self._asignacion(1, self.cons5a, esperada=None))

        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.json()["code"], "ADSCRIPCION_MODIFICADA")

    def test_recien_nacido_se_asigna_con_su_familia(self):
        bebe = self._recien_nacido(NO_EXP)
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia():
            respuesta = self._confirmar(
                self._asignacion(0, self.cons5a), self._asignacion(bebe.provisional_code, self.cons5a),
            )

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertTrue(AdscripcionPaciente.objects.filter(paciente=bebe, consultorio=self.cons5a).exists())

    def test_sin_permiso_de_escritura(self):
        self._login("lee", [LEER])
        with self._familia():
            respuesta = self._confirmar(self._asignacion(0, self.cons5a))

        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Patient.objects.filter(no_exp=NO_EXP).exists())

    def test_paciente_de_otro_centro_sin_todos_centros(self):
        self._login("asigna", [LEER, ESCRIBIR], centro=self.clinica7)
        with self._familia():
            respuesta = self._confirmar(self._asignacion(0, self.cons5a))

        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(respuesta.json()["code"], "CENTRO_NO_PERMITIDO")
        self.assertFalse(Patient.objects.filter(no_exp=NO_EXP).exists())

    def test_con_todos_centros_si_puede(self):
        self._login("central", [LEER, ESCRIBIR, TODOS], centro=self.clinica7)
        with self._familia():
            respuesta = self._confirmar(self._asignacion(0, self.cons5a))

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)

    def test_miembro_repetido_es_invalido(self):
        self._login("asigna", [LEER, ESCRIBIR])
        with self._familia():
            respuesta = self._confirmar(self._asignacion(0, self.cons5a), self._asignacion(0, self.cons5b))

        self.assertEqual(respuesta.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(respuesta.json()["code"], "VALIDATION_ERROR")
