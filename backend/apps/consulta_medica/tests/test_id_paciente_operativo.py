"""
Plan identidad del paciente, Fase 5: las tablas operativas guardan
id_paciente (el registro atendido). Doble escritura al guardar, llenado de lo
existente con vincular_id_paciente y lectura por id con interruptor.
"""
from django.test import TestCase, override_settings

from apps.consulta_medica.models import Patient
from apps.consulta_medica.services.operational_link_service import (
    OPERATIONAL_MODELS,
    no_exp_field,
    operational_models,
)
from apps.consulta_medica.services.patient_link_service import link_existing, unlinked_counts
from apps.portal_citas.models import PortalMiembro
from apps.recepcion.models import Visit


def _visita(folio, no_exp="E1", pk_num=0, **kw):
    return Visit.objects.create(
        folio=folio, no_exp=no_exp, pk_num=pk_num, arrival_type="walk_in",
        service_type="medicina_general", nombre_paciente="Paciente", **kw,
    )


class DobleEscrituraTests(TestCase):
    def test_la_visita_nace_con_su_registro_de_paciente(self):
        visita = _visita("F-1", "40041", 900)
        paciente = Patient.objects.get(no_exp="40041", pk_num=900)
        self.assertEqual(visita.patient_id, paciente.pk)

    def test_usa_el_registro_existente_sin_duplicarlo(self):
        existente = Patient.objects.create(no_exp="40041", pk_num=0)
        visita = _visita("F-2", "40041", 0)
        self.assertEqual(visita.patient_id, existente.pk)
        self.assertEqual(Patient.objects.filter(no_exp="40041", pk_num=0).count(), 1)

    def test_el_portal_solo_vincula_no_crea(self):
        miembro = PortalMiembro.objects.create(
            no_exp="E-PORTAL", pk_num=0, nombre_visible="X", es_titular_login=True,
        )
        self.assertIsNone(miembro.patient_id)
        self.assertFalse(Patient.objects.filter(no_exp="E-PORTAL").exists())

        existente = Patient.objects.create(no_exp="E-PORTAL2", pk_num=0)
        miembro2 = PortalMiembro.objects.create(
            no_exp="E-PORTAL2", pk_num=0, nombre_visible="Y", es_titular_login=True,
        )
        self.assertEqual(miembro2.patient_id, existente.pk)

    def test_sin_registro_resoluble_la_ficha_no_se_guarda(self):
        # Plan contraer la llave vieja: id_paciente es obligatorio. Sin llave que
        # resolver (pk_num None) la ficha no se guarda sin paciente.
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            _visita("F-3", "40041", None)

    def test_omitir_pk_num_conserva_el_cero_del_titular(self):
        visita = Visit.objects.create(folio="F-4", no_exp="40041", arrival_type="walk_in",
                                      service_type="medicina_general", nombre_paciente="P")
        # La ficha guarda solo el paciente: el titular (pk_num 0) de ese expediente.
        self.assertEqual((visita.patient.no_exp, visita.patient.pk_num), ("40041", 0))


class LlenadoDeLoExistenteTests(TestCase):
    def test_sin_filas_sin_paciente_el_llenado_no_cambia_nada(self):
        # Plan contraer la llave vieja: id_paciente ya es obligatorio, no puede
        # haber fichas sin paciente; el llenado (migracion 0065) no tiene que hacer.
        _visita("F-10", "50123", 0)
        self.assertEqual(unlinked_counts()["rcp_visits"], 0)
        self.assertEqual(link_existing()["rcp_visits"]["rows"], 0)

    def test_el_llenado_no_crea_registros_desde_el_portal(self):
        miembro = PortalMiembro.objects.create(
            no_exp="E-P3", pk_num=0, nombre_visible="Z", es_titular_login=True,
        )
        link_existing()
        miembro.refresh_from_db()
        self.assertIsNone(miembro.patient_id)
        self.assertFalse(Patient.objects.filter(no_exp="E-P3").exists())


class RegistroDeTablasTests(TestCase):
    def test_las_diez_tablas_del_inventario_tienen_id_paciente(self):
        tablas = {modelo._meta.db_table for modelo in operational_models()}
        self.assertEqual(tablas, {
            "rcp_visits", "citas_medicas", "smt_visit_vitals", "smt_patient_latest_vitals",
            "cir_surgery", "hsp_admission", "amb_request", "ref_referral",
            "contratos_oxigeno", "portal_miembros",
            # Plan contraer la llave vieja: los padrones tambien solo guardan id_paciente.
            "cns_padron_cronico", "cns_padron_discapacidad",
        })
        for modelo in operational_models():
            campo = modelo._meta.get_field("patient")
            self.assertEqual(campo.column, "id_paciente", modelo._meta.label)
            # Plan contraer la llave vieja: obligatorio, salvo el portal (solo liga si existe).
            self.assertEqual(campo.null, modelo._meta.label == "portal_citas.PortalMiembro", modelo._meta.label)
            modelo._meta.get_field(no_exp_field(modelo))   # el campo de expediente existe
        self.assertEqual(OPERATIONAL_MODELS["contratos_oxigeno.ContratoOxigeno"], "expediente")


class LecturaPorIdTests(TestCase):
    @override_settings(IDENTIDAD_PACIENTE={
        "VERIFICAR_SERMED": "apagado", "LECTURA_OPERATIVA_POR_ID": True,
        "RECIEN_NACIDOS": False, "VINCULACION": False,
    })
    def test_con_el_interruptor_se_suman_las_visitas_por_id_paciente(self):
        from apps.consulta_medica.repositories.consultation_repository import ConsultationRepository

        # La consulta compila con el filtro por id_paciente sin error (las
        # visitas sin consulta no aparecen: solo se verifica la consulta SQL).
        Patient.objects.create(no_exp="40041", pk_num=0)
        sql = str(ConsultationRepository.list_for_patient("40041", 0).query)
        self.assertIn("id_paciente", sql)
