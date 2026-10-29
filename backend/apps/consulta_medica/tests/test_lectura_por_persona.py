"""
Plan identidad del paciente, Fase 4: las lecturas clinicas son de la PERSONA
(todas sus afiliaciones), no de un solo registro. Hoy cada persona tiene un
registro y el resultado es identico al anterior; aqui se simula lo que dejara
la vinculacion (Fase 7): dos registros con la misma persona.
"""
from django.test import TestCase

from apps.consulta_medica.models import Allergy, Patient
from apps.consulta_medica.services.patient_link_service import for_patient


def _alergia(no_exp, pk_num, sustancia, paciente=None):
    return Allergy.objects.create( patient=paciente, allergy_type_id=9,
        substance=sustancia, severity="M", service_origin_code=1,
    )


class LecturaPorPersonaTests(TestCase):
    def setUp(self):
        # Juan como hijo del 40041 y, mas tarde, como trabajador 50123.
        self.hijo = Patient.objects.create(no_exp="40041", pk_num=900)
        self.trabajador = Patient.objects.create(no_exp="50123", pk_num=0, person=self.hijo.person)
        self.otro = Patient.objects.create(no_exp="40041", pk_num=901)
        _alergia("40041", 900, "PENICILINA", self.hijo)
        _alergia("50123", 0, "SULFAS", self.trabajador)
        _alergia("40041", 901, "POLEN", self.otro)

    def _sustancias(self, no_exp, pk_num):
        return sorted(for_patient(Allergy.objects.all(), no_exp, pk_num).values_list("substance", flat=True))

    def test_desde_cualquier_afiliacion_se_ve_todo_lo_de_la_persona(self):
        # La alergia a la penicilina capturada cuando era hijo aparece al
        # atenderlo como trabajador: es la regla de seguridad del plan.
        self.assertEqual(self._sustancias("50123", 0), ["PENICILINA", "SULFAS"])
        self.assertEqual(self._sustancias("40041", 900), ["PENICILINA", "SULFAS"])

    def test_no_mezcla_a_otra_persona_del_mismo_expediente(self):
        self.assertEqual(self._sustancias("40041", 901), ["POLEN"])

