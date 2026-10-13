"""
Tests de la tarea ``generar_slots_todos_medicos``.

Regresión W5: el bloque ``except`` loggeaba ``medico.id_medclin`` (atributo
inexistente en CatMedico) y el AttributeError abortaba todo el loop, dejando
al resto de los médicos sin slots.
"""

from unittest import mock

from django.test import TestCase

from apps.medicos.models import CatMedico
from apps.recepcion.tasks import generar_slots_todos_medicos


class GenerarSlotsTodosMedicosTests(TestCase):
    def setUp(self):
        # Médicos sin usuario (id_usuario None): el id es el No. Médico.
        self.m1 = CatMedico.objects.create(nombre="Ana", paterno="Lopez")
        self.m2 = CatMedico.objects.create(nombre="Beto", paterno="Ruiz")
        self.m3 = CatMedico.objects.create(nombre="Carla", paterno="Diaz")

    def test_error_en_un_medico_no_aborta_el_loop(self):
        llamados = []

        def fake_generar(medico_id, dias_adelante):
            llamados.append(medico_id)
            if medico_id == self.m2.id:
                raise RuntimeError("fallo simulado")
            return 5

        with mock.patch(
            "apps.recepcion.tasks.CitasRepository.generar_slots_medico",
            side_effect=fake_generar,
        ):
            # Se ejecuta sin AttributeError y devuelve el resumen.
            resultado = generar_slots_todos_medicos.apply().get()

        # Orden determinista por id y todos los médicos procesados.
        self.assertEqual(llamados, [self.m1.id, self.m2.id, self.m3.id])
        self.assertEqual(resultado["medicos"], 2)
        self.assertEqual(resultado["slots_creados"], 10)
        self.assertEqual(resultado["errores"], 1)
