"""Archivo `legacy_medico` (solo lectura, columnas espejo del legado) y tabla
`medico_externo`. Ningún código legado se interpreta como `CatMedico.id`."""

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.medicos.models import LegacyMedico, MedicoExterno
from apps.medicos.repositories.medico_repository import MedicoRepository
from apps.medicos.tests.factories import crear_medico


class LegacyMedicoTests(TestCase):
    def test_no_medico_es_pk_explicita_y_cd_medico_puede_repetirse(self):
        LegacyMedico.objects.create(no_medico=10, cd_medico="0512", sw_status="A")
        LegacyMedico.objects.create(no_medico=11, cd_medico="0512", sw_status="A")
        self.assertEqual(LegacyMedico.objects.filter(cd_medico="0512").count(), 2)

    def test_medico_actual_es_n_a_1_y_se_anula_al_borrar_el_medico(self):
        medico = crear_medico()
        a = LegacyMedico.objects.create(no_medico=1, cd_medico="1", sw_status="A", medico_actual=medico)
        b = LegacyMedico.objects.create(no_medico=2, cd_medico="2", sw_status="A", medico_actual=medico)
        self.assertEqual(medico.registros_legado.count(), 2)

        medico.delete()

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertIsNone(a.medico_actual_id)
        self.assertIsNone(b.medico_actual_id)

    def test_filas_no_persona_y_campos_opcionales(self):
        fila = LegacyMedico.objects.create(
            no_medico=99, cd_medico="X", ds_clinica="CLINICA 1", sw_status="A",
        )
        fila.refresh_from_db()
        self.assertIsNone(fila.ds_nombre)
        self.assertIsNotNone(fila.fch_carga)


class MedicoExternoTests(TestCase):
    def test_origen_id_externo_es_unico(self):
        MedicoExterno.objects.create(origen="IMSS", id_externo="A1", nombre="Ana")
        MedicoExterno.objects.create(origen="MANUAL", id_externo="A1", nombre="Ana")
        with self.assertRaises(IntegrityError), transaction.atomic():
            MedicoExterno.objects.create(origen="IMSS", id_externo="A1", nombre="Otra")

    def test_activo_por_defecto(self):
        self.assertTrue(MedicoExterno.objects.create(origen="IMSS", id_externo="B", nombre="B").activo)


class AltaRequiereUsuarioTests(TestCase):
    def test_repositorio_rechaza_alta_sin_usuario(self):
        with self.assertRaises(ValueError):
            MedicoRepository.create(
                usuario=None, tipo_medico="CLINICA", servicio=None,
                observaciones=None, created_by_id=None,
            )
