"""
Plan identidad del paciente, bloque C1: recien nacido provisional, candidatos
de SERMED, vinculacion con un clic, descarte y guardias contra duplicados.
La replica de SERMED no existe en tests: titular y familiares se simulan.
"""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.consulta_medica.models import ChangeLog, Patient, PatientIdentifier, PersonDiscard, ProvisionalPatient
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.services import newborn_service as rn
from apps.consulta_medica.services.patient_link_service import records_for_key
from apps.recepcion.services.errors import VisitDomainError

NACIMIENTO = date(2026, 10, 1)
ENCENDIDO = override_settings(IDENTIDAD_PACIENTE={
    "VERIFICAR_SERMED": "apagado", "LECTURA_OPERATIVA_POR_ID": False,
    "RECIEN_NACIDOS": True, "VINCULACION": False, "DIAS_VIGENCIA_RN": 60,
})
TITULAR = SimpleNamespace(no_exp="40041", cd_clinica="3", cd_sexo="M",
                          ds_paterno="PEREZ", ds_materno="GOMEZ", ds_nombre="JUAN")


# Como viene en la replica (verificado 2026-10-26): descripcion en cd_parentesco, codigo en tp_der.
PARENTESCOS = {"H": ("HIJO (A)", "H1"), "E": ("ESPOSA (O)", "E"), "C": ("CONCUBINA (O)", "C")}


def _familiar(pk_num, fe_nac=NACIMIENTO, sexo="F", nombre="ANA", parentesco="H", fec_vig=None, tp_der=None):
    descripcion, codigo = PARENTESCOS[parentesco]
    return SimpleNamespace(pk_num=pk_num, fe_nac=fe_nac, cd_sexo=sexo, ds_paterno="PEREZ",
                           ds_materno="LOPEZ", ds_nombre=nombre, cd_parentesco=descripcion,
                           tp_der=tp_der or codigo, fec_vig=fec_vig)


class _SermedSimulado:
    familiares: list = []

    def setUp(self):
        super().setUp()
        for nombre, valor in (("_titular_en_sermed", lambda no_exp: TITULAR if no_exp == "40041" else None),
                              ("_familiares_sermed", lambda no_exp: list(self.familiares))):
            parche = mock.patch.object(rn, nombre, side_effect=valor)
            parche.start()
            self.addCleanup(parche.stop)

    def _registrar(self, **kw):
        datos = dict(paterno="PEREZ", materno="LOPEZ", nombre="RN", fecha_nacimiento=NACIMIENTO, sexo="F")
        datos.update(kw)
        return rn.registrar_recien_nacido("40041", **datos)


@ENCENDIDO
class AltaTests(_SermedSimulado, TestCase):
    def test_registra_el_provisional_con_su_secuencia_vigencia_y_bitacora(self):
        resultado = self._registrar(madre="MARIA LOPEZ")
        paciente = Patient.objects.get(pk=resultado["idPaciente"])
        self.assertEqual((paciente.no_exp, paciente.pk_num), ("40041", None))
        self.assertGreater(paciente.legacy_family_code, rn.BASE_CD_FAMILIAR)
        self.assertEqual(paciente.sex, "F")
        provisional = paciente.provisional
        self.assertEqual(provisional.status, "A")
        self.assertEqual(provisional.clinic_code, "3")
        self.assertEqual(provisional.valid_until, timezone.localdate() + timedelta(days=60))
        self.assertTrue(PatientIdentifier.objects.filter(
            patient=paciente, id_type="CD_FAMILIAR", value=str(paciente.legacy_family_code)).exists())
        self.assertTrue(ChangeLog.objects.filter(
            table="cns_paciente", key=f"id_paciente|{paciente.pk}", reason="REGISTRO RN").exists())
        self.assertTrue(resultado["vigente"])

    def test_la_secuencia_avanza_y_no_choca(self):
        primero = self._registrar(orden=1)
        segundo = self._registrar(orden=2)
        self.assertEqual(segundo["cdFamiliar"], primero["cdFamiliar"] + 1)

    def test_valida_campos_y_curp(self):
        with self.assertRaises(VisitDomainError) as error:
            self._registrar(nombre="", paterno="", materno="", sexo="Z", fecha_nacimiento=date(2999, 1, 1))
        self.assertEqual(set(error.exception.details), {"paternalSurname", "sex", "birthDate"})
        with self.assertRaises(VisitDomainError) as error:
            self._registrar(curp="NO-ES-CURP")
        self.assertIn("curp", error.exception.details)

    def test_titular_que_no_esta_en_sermed(self):
        with self.assertRaises(VisitDomainError) as error:
            rn.registrar_recien_nacido("99999", paterno="X", materno=None, nombre="RN",
                                       fecha_nacimiento=NACIMIENTO, sexo="F")
        self.assertEqual(error.exception.code, "TITULAR_NO_EN_SERMED")

    def test_no_registra_dos_veces_el_mismo_bebe(self):
        self._registrar()
        with self.assertRaises(VisitDomainError) as error:
            self._registrar()
        self.assertEqual(error.exception.code, "RN_YA_REGISTRADO")
        self.assertEqual(ProvisionalPatient.objects.count(), 1)

    def test_guardia_2_avisa_si_sermed_ya_tiene_al_bebe(self):
        self.familiares = [_familiar(777)]
        with self.assertRaises(VisitDomainError) as error:
            self._registrar()
        self.assertEqual(error.exception.code, "RN_YA_EN_SERMED")
        self.assertEqual(error.exception.details["candidatos"][0]["pkNum"], 777)
        # Con confirmacion explicita (p. ej. gemelos) se registra igual.
        self._registrar(confirmar_aunque_exista=True)

    def test_sin_nombre_queda_recien_nacido(self):
        resultado = self._registrar(nombre="  ")
        paciente = Patient.objects.get(pk=resultado["idPaciente"])
        self.assertEqual(paciente.first_name, "RECIEN NACIDO")
        cambio = ChangeLog.objects.get(table="cns_paciente", reason="REGISTRO RN")
        self.assertEqual(cambio.new_value["first_name"], "RECIEN NACIDO")

    @override_settings(IDENTIDAD_PACIENTE={"RECIEN_NACIDOS": False, "VERIFICAR_SERMED": "apagado"})
    def test_apagado_no_registra(self):
        with self.assertRaises(VisitDomainError) as error:
            self._registrar()
        self.assertEqual(error.exception.code, "RECIEN_NACIDOS_DESHABILITADO")


@ENCENDIDO
class VinculacionTests(_SermedSimulado, TestCase):
    def setUp(self):
        super().setUp()
        self.provisional = self._registrar()
        self.id_rn = self.provisional["idPaciente"]
        self.familiares = [_familiar(777), _familiar(778, sexo="M"), _familiar(779, fe_nac=date(2020, 1, 1))]

    def test_candidatos_por_fecha_y_sexo(self):
        lista = rn.listar("40041")
        candidatos = lista["provisionales"][0]["candidatos"]
        self.assertEqual([c["pkNum"] for c in candidatos], [777])
        self.assertFalse(candidatos[0]["yaTieneRegistro"])

    def test_vincular_une_las_dos_historias_sin_mover_nada(self):
        resultado = rn.vincular(self.id_rn, 777)
        self.assertEqual((resultado["estatus"], resultado["pkNumSermed"]), ("B", 777))
        rn_paciente = Patient.objects.get(pk=self.id_rn)
        sermed = Patient.objects.get(no_exp="40041", pk_num=777)
        self.assertEqual(sermed.person_id, rn_paciente.person_id)
        # Desde la afiliacion de SERMED se ve todo lo de la persona (Fase 4).
        self.assertEqual({p.pk for p in records_for_key("40041", 777)}, {self.id_rn, sermed.pk})
        self.assertTrue(ChangeLog.objects.filter(table="cns_paciente_provisional", reason="LIGA RN").exists())

    def test_vincular_un_registro_de_sermed_que_ya_existia(self):
        existente = Patient.objects.create(no_exp="40041", pk_num=777)
        rn.vincular(self.id_rn, 777)
        existente.refresh_from_db()
        self.assertEqual(existente.person_id, Patient.objects.get(pk=self.id_rn).person_id)
        self.assertTrue(ChangeLog.objects.filter(
            table="cns_paciente", key=f"id_paciente|{existente.pk}", reason="LIGA RN").exists())

    def test_no_vincula_un_candidato_que_no_coincide(self):
        with self.assertRaises(VisitDomainError) as error:
            rn.vincular(self.id_rn, 778)
        self.assertEqual(error.exception.code, "CANDIDATO_NO_VALIDO")

    def test_no_se_vincula_dos_veces(self):
        rn.vincular(self.id_rn, 777)
        with self.assertRaises(VisitDomainError) as error:
            rn.vincular(self.id_rn, 777)
        self.assertEqual(error.exception.code, "RN_YA_VINCULADO")

    def test_descartar_quita_al_candidato(self):
        rn.descartar(self.id_rn, 777, motivo="Es su hermana mayor")
        self.assertEqual(rn.listar("40041")["provisionales"][0]["candidatos"], [])
        self.assertTrue(PersonDiscard.objects.filter(candidate_pk_num=777).exists())
        self.assertTrue(ChangeLog.objects.filter(reason="DESCARTE LIGA RN").exists())

    def test_guardia_1_no_abre_registro_del_familiar_sin_vincular(self):
        with self.assertRaises(VisitDomainError) as error:
            PatientRepository.get_or_create("40041", 777)
        self.assertEqual(error.exception.code, "RN_PENDIENTE_DE_VINCULAR")
        self.assertFalse(Patient.objects.filter(no_exp="40041", pk_num=777).exists())
        # Un familiar que no coincide se abre normal.
        PatientRepository.get_or_create("40041", 779)

    def test_guardia_1_respeta_el_descarte_y_la_vinculacion(self):
        rn.descartar(self.id_rn, 777)
        PatientRepository.get_or_create("40041", 777)   # ya no bloquea


class ApiRecienNacidosTests(TestCase):
    def test_sin_permiso_de_vincular_no_vincula(self):
        from rest_framework.response import Response
        from rest_framework.test import APIRequestFactory

        from apps.administracion.views import recien_nacido_view as vista

        denegado = Response({"code": "PERMISSION_DENIED"}, status=403)
        request = APIRequestFactory().post("/x", {"pkNum": 777}, format="json")
        with mock.patch.object(vista, "_authorize", return_value=(None, denegado)) as autorizar, \
             mock.patch.object(vista.newborn_service, "vincular") as vincular:
            respuesta = vista.VincularRecienNacidoView.as_view()(request, id_paciente=1)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(autorizar.call_args[0][1], "admin:gestion:expedientes:vincular")
        vincular.assert_not_called()

    def test_extender_vigencia_usa_el_permiso_de_registrar(self):
        from rest_framework.response import Response
        from rest_framework.test import APIRequestFactory

        from apps.administracion.views import recien_nacido_view as vista

        denegado = Response({"code": "PERMISSION_DENIED"}, status=403)
        request = APIRequestFactory().post("/x", {}, format="json")
        with mock.patch.object(vista, "_authorize", return_value=(None, denegado)) as autorizar, \
             mock.patch.object(vista.newborn_service, "extender_vigencia") as extender:
            respuesta = vista.ExtenderVigenciaRecienNacidoView.as_view()(request, id_paciente=1)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(autorizar.call_args[0][1], "admin:gestion:expedientes:recien_nacidos")
        extender.assert_not_called()


@ENCENDIDO
class MadreSugeridaTests(_SermedSimulado, TestCase):
    """El bebe se liga al titular, que puede ser el padre: la madre solo se propone."""

    def _sugerida(self):
        return rn.listar("40041")["madreSugerida"]

    def test_titular_mujer_es_la_madre(self):
        titular = SimpleNamespace(**{**vars(TITULAR), "cd_sexo": "F", "ds_nombre": "LAURA"})
        with mock.patch.object(rn, "_titular_en_sermed", return_value=titular):
            self.assertEqual(self._sugerida(), "LAURA PEREZ GOMEZ")

    def test_titular_hombre_con_una_esposa_vigente(self):
        self.familiares = [_familiar(10, parentesco="E", nombre="MARIA"), _familiar(11, nombre="HIJA")]
        self.assertEqual(self._sugerida(), "MARIA PEREZ LOPEZ")

    def test_concubina_tambien_cuenta(self):
        self.familiares = [_familiar(10, parentesco="C", nombre="ROSA")]
        self.assertEqual(self._sugerida(), "ROSA PEREZ LOPEZ")

    def test_dos_parejas_o_ninguna_no_sugiere(self):
        self.familiares = [_familiar(10, parentesco="E"), _familiar(11, parentesco="C")]
        self.assertIsNone(self._sugerida())
        self.familiares = [_familiar(11)]
        self.assertIsNone(self._sugerida())

    def test_manda_la_descripcion_no_el_codigo_cruzado(self):
        # Datos reales: un "HIJO (A)" con tp_der E y una "ESPOSA (O)" con tp_der C.
        self.familiares = [_familiar(10, parentesco="H", tp_der="E"),
                           _familiar(11, parentesco="E", tp_der="C", nombre="MARIA")]
        self.assertEqual(self._sugerida(), "MARIA PEREZ LOPEZ")

    def test_pareja_con_vigencia_vencida_no_cuenta(self):
        vencida = timezone.localdate() - timedelta(days=1)
        self.familiares = [_familiar(10, parentesco="E", fec_vig=vencida)]
        self.assertIsNone(self._sugerida())

    def test_sermed_caido_no_rompe_el_panel(self):
        caido = VisitDomainError("EXPEDIENTES_NO_DISPONIBLE", "x", 503)
        with mock.patch.object(rn, "_titular_en_sermed", side_effect=caido):
            self.assertIsNone(self._sugerida())


@ENCENDIDO
class ExtenderVigenciaTests(_SermedSimulado, TestCase):
    """Como el legado: hoy + 60 (sin fecha libre) y la anterior queda en la bitacora."""

    def setUp(self):
        super().setUp()
        self.id_rn = self._registrar()["idPaciente"]
        self.hoy = timezone.localdate()

    def _vencer(self, dias_atras=1):
        ProvisionalPatient.objects.filter(patient_id=self.id_rn).update(
            valid_until=self.hoy - timedelta(days=dias_atras))

    def test_un_provisional_vencido_vuelve_a_estar_vigente(self):
        self._vencer()
        resultado = rn.extender_vigencia(self.id_rn, motivo="Constancia de nacimiento en trámite")
        self.assertEqual(resultado["vigencia"], (self.hoy + timedelta(days=60)).isoformat())
        self.assertTrue(resultado["vigente"])
        cambio = ChangeLog.objects.get(reason="EXTENSION VIGENCIA RN")
        self.assertEqual((cambio.table, cambio.key), ("cns_paciente_provisional", f"id_paciente|{self.id_rn}"))
        self.assertEqual(cambio.previous_value["fe_vigencia"], (self.hoy - timedelta(days=1)).isoformat())
        self.assertEqual(cambio.new_value["motivo"], "Constancia de nacimiento en trámite")

    def test_se_puede_extender_antes_de_que_venza(self):
        ProvisionalPatient.objects.filter(patient_id=self.id_rn).update(valid_until=self.hoy + timedelta(days=5))
        rn.extender_vigencia(self.id_rn)
        self.assertEqual(ProvisionalPatient.objects.get(patient_id=self.id_rn).valid_until,
                         self.hoy + timedelta(days=60))

    def test_recien_registrado_no_hay_nada_que_extender(self):
        with self.assertRaises(VisitDomainError) as error:
            rn.extender_vigencia(self.id_rn)
        self.assertEqual(error.exception.code, "VIGENCIA_SIN_CAMBIO")
        self.assertFalse(ChangeLog.objects.filter(reason="EXTENSION VIGENCIA RN").exists())

    def test_vinculado_no_se_extiende(self):
        self.familiares = [_familiar(777)]
        rn.vincular(self.id_rn, 777)
        self._vencer()
        with self.assertRaises(VisitDomainError) as error:
            rn.extender_vigencia(self.id_rn)
        self.assertEqual(error.exception.code, "RN_YA_VINCULADO")

    def test_extendido_vuelve_a_aparecer_en_recepcion(self):
        self._vencer()
        self.assertEqual(rn.miembros_recepcion("40041", historico=False), [])
        rn.extender_vigencia(self.id_rn)
        self.assertEqual([m["idPaciente"] for m in rn.miembros_recepcion("40041", historico=False)], [self.id_rn])


@ENCENDIDO
class RecepcionProvisionalTests(_SermedSimulado, TestCase):
    """Bloque C2: el provisional se atiende en recepcion con su cd_familiar
    en el lugar del pk_num, como los familiares del legado sin PK_NUM."""

    FILA_TITULAR = {"NO_EXP": "40041", "DS_PATERNO": "PEREZ", "DS_MATERNO": "GOMEZ", "DS_NOMBRE": "JUAN",
                    "ESTATUS": "ACTIVO", "EDAD": 40, "FE_NAC": date(1985, 3, 15), "CD_CLINICA": "3"}

    def setUp(self):
        super().setUp()
        self.provisional = self._registrar(nombre="BEBE")
        self.clave = self.provisional["cdFamiliar"]

    def test_la_clave_nunca_choca_con_un_pk_num_de_sermed(self):
        # CAT_FAMILIAR.PK_NUM es NUMBER(8): hasta 99 999 999.
        self.assertGreater(self.clave, 99_999_999)
        self.assertTrue(rn.es_clave_provisional(self.clave))
        self.assertFalse(rn.es_clave_provisional(48411))

    def test_aparece_en_el_buscador_de_recepcion(self):
        from apps.recepcion.uses_case import visit_queue_usecase

        with mock.patch.object(visit_queue_usecase, "buscar_expediente",
                               return_value={"empleados": [self.FILA_TITULAR], "familiares": []}):
            resultado = visit_queue_usecase.lookup_patient("40041")
        miembro = next(m for m in resultado["dependientes"] if m.get("provisional"))
        self.assertEqual(miembro["pkNum"], self.clave)
        self.assertEqual(miembro["estatus"], "ACTIVO")
        self.assertEqual(miembro["parentesco"], "HIJO(A) RECIEN NACIDO (PROVISIONAL) · ORDEN 1")
        self.assertEqual(miembro["idPaciente"], self.provisional["idPaciente"])

    def test_gemelos_con_el_mismo_nombre_se_distinguen_por_el_orden(self):
        rn.registrar_recien_nacido("40041", paterno="PEREZ", materno="LOPEZ", nombre=None,
                                   fecha_nacimiento=NACIMIENTO, sexo="F", orden=2, madre="MARIA LOPEZ")
        miembros = rn.miembros_recepcion("40041", historico=False)
        self.assertEqual({m["nombre"] for m in miembros if m["orden"] == 2}, {"RECIEN NACIDO PEREZ LOPEZ"})
        self.assertEqual(sorted(m["orden"] for m in miembros), [1, 2])

    def test_la_madre_se_muestra_solo_si_el_titular_es_hombre(self):
        ProvisionalPatient.objects.update(mother_name="MARIA LOPEZ")
        self.assertEqual(rn.miembros_recepcion("40041", historico=False)[0]["madre"], "MARIA LOPEZ")
        titular_mujer = SimpleNamespace(**{**vars(TITULAR), "cd_sexo": "F"})
        with mock.patch.object(rn, "_titular_en_sermed", return_value=titular_mujer):
            self.assertIsNone(rn.miembros_recepcion("40041", historico=False)[0]["madre"])
            self.assertTrue(rn.listar("40041")["titularEsMujer"])

    def test_vencido_no_aparece_en_check_in_pero_si_en_historico(self):
        from apps.recepcion.uses_case import visit_queue_usecase

        ProvisionalPatient.objects.update(valid_until=timezone.localdate() - timedelta(days=1))
        with mock.patch.object(visit_queue_usecase, "buscar_expediente",
                               return_value={"empleados": [self.FILA_TITULAR], "familiares": []}):
            activos = visit_queue_usecase.lookup_patient("40041")["dependientes"]
            historico = visit_queue_usecase.lookup_patient("40041", historico=True)["dependientes"]
        self.assertFalse(any(m.get("provisional") for m in activos))
        self.assertEqual([m["estatus"] for m in historico if m.get("provisional")], ["NO ACTIVO"])

    def test_vigencia_del_provisional(self):
        from apps.recepcion.services.vigencia_service import tiene_vigencia

        self.assertTrue(tiene_vigencia("40041", self.clave))
        ProvisionalPatient.objects.update(valid_until=timezone.localdate() - timedelta(days=1))
        self.assertFalse(tiene_vigencia("40041", self.clave))
        self.assertFalse(tiene_vigencia("40041", self.clave + 999))   # no existe

    def test_la_visita_queda_en_el_registro_del_provisional(self):
        from apps.recepcion.models import Visit

        visita = Visit.objects.create(folio="RN-1", no_exp="40041", pk_num=self.clave, arrival_type="walk_in",
                                      service_type="medicina_general", nombre_paciente="BEBE")
        self.assertEqual(visita.patient_id, self.provisional["idPaciente"])
        self.assertEqual(Patient.objects.filter(no_exp="40041").count(), 1)   # no creo otro

    def test_ficha_e_impresion_toman_el_nombre_del_registro(self):
        from apps.impresion.services import patient_header
        from apps.recepcion.services import ficha_service

        with mock.patch("apps.administracion.use_cases.expedientes.buscar_expediente.buscar_expediente",
                        return_value={"empleados": [self.FILA_TITULAR], "familiares": []}):
            nombre = ficha_service._get_nombre_components("40041", self.clave)
        self.assertEqual((nombre["nombre_paciente"], nombre["a_paterno"]), ("BEBE", "PEREZ"))
        encabezado = patient_header._from_patient("40041", self.clave)
        self.assertEqual(encabezado["first_name"], "BEBE")

    @override_settings(IDENTIDAD_PACIENTE={"RECIEN_NACIDOS": False, "VERIFICAR_SERMED": "apagado"})
    def test_apagado_recepcion_no_los_muestra(self):
        self.assertEqual(rn.miembros_recepcion("40041", historico=True), [])
