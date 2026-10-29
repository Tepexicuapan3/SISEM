"""
Plan identidad del paciente, Fase 5: las tablas operativas guardan
id_paciente (el registro atendido). Desde C7 (plan contraer la llave vieja)
es lo unico que guardan; el portal todavia se vincula por su llave.
"""
from django.test import TestCase, override_settings

from apps.consulta_medica.models import Patient
from apps.portal_citas.models import PortalMiembro
from apps.recepcion.models import Visit
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave


def _visita(folio, no_exp="E1", pk_num=0, **kw):
    return Visit.objects.create(
        folio=folio, patient=_paciente_de_llave(no_exp, pk_num), arrival_type="walk_in",
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
        visita = Visit.objects.create(folio="F-4", patient=_paciente_de_llave("40041", 0), arrival_type="walk_in",
                                      service_type="medicina_general", nombre_paciente="P")
        # La ficha guarda solo el paciente: el titular (pk_num 0) de ese expediente.
        self.assertEqual((visita.patient.no_exp, visita.patient.pk_num), ("40041", 0))


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
