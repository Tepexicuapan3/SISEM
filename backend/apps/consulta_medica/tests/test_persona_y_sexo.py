"""
Plan identidad del paciente, bloque A:
  - Fase 2: el sexo usa la convencion de SERMED (M/F/X); los datos H/M se
    convierten (migracion 0056) y la sync copia el sexo de los familiares.
  - Fase 3: cada registro de paciente (afiliacion) pertenece a una persona
    (cns_persona); los existentes reciben una persona con su mismo uuid
    (0057) y la columna es obligatoria (0058).
"""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from apps.consulta_medica.models import Patient, Person
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.services import sermed_sync_service as sync
from apps.consulta_medica.services.sermed_source import SermedFamilyMember

CURP_MUJER_2015 = "PELA150601MDFRRN03"   # mujer, 01/06/2015


def _familiar(**kw):
    datos = dict(
        pk_num=501, holder_no_exp="100", paternal_surname="PEREZ", maternal_surname="LOPEZ",
        first_name="ANA", birth_date=date(2015, 6, 1), relationship_code="H", beneficiary_type="HI",
        valid_until=date(2027, 1, 1), clinic_code="1", sex_code="F",
    )
    datos.update(kw)
    return SermedFamilyMember(**datos)


class _Fuente:
    def __init__(self, familiares):
        self._familiares = {f.pk_num: f for f in familiares}

    def employees(self, no_exps):
        return {}

    def family_members(self, pk_nums):
        return {p: self._familiares[p] for p in pk_nums if p in self._familiares}


class PersonaTests(TestCase):
    def test_todo_registro_nace_con_su_persona_y_el_mismo_uuid(self):
        paciente = Patient.objects.create(no_exp="100", pk_num=0)
        self.assertIsNotNone(paciente.person_id)
        self.assertEqual(paciente.person.uuid, paciente.uuid)

    def test_la_puerta_central_tambien_crea_la_persona(self):
        paciente, creado = PatientRepository.get_or_create("100", 501)
        self.assertTrue(creado)
        self.assertEqual(Person.objects.get(pk=paciente.person_id).uuid, paciente.uuid)

    def test_reutilizar_un_registro_no_crea_otra_persona(self):
        PatientRepository.get_or_create("100", 501)
        PatientRepository.get_or_create("100", 501)
        self.assertEqual(Person.objects.count(), 1)

    def test_dos_afiliaciones_pueden_compartir_persona(self):
        # La base de la Fase 7: vincular = misma persona, registros separados.
        hijo = Patient.objects.create(no_exp="40041", pk_num=900)
        trabajador = Patient.objects.create(no_exp="50123", pk_num=0, person=hijo.person)
        self.assertEqual(trabajador.person_id, hijo.person_id)
        self.assertEqual(set(hijo.person.records.values_list("pk", flat=True)), {hijo.pk, trabajador.pk})


class SexoDeFamiliarEnLaSyncTests(TestCase):
    def setUp(self):
        self.familiar = Patient.objects.create(no_exp="100", pk_num=501)

    def test_copia_el_sexo_de_sermed(self):
        sync.sync_patients(Patient.objects.all(), source=_Fuente([_familiar(sex_code="F")]))
        self.familiar.refresh_from_db()
        self.assertEqual(self.familiar.sex, "F")

    def test_con_curp_capturada_manda_la_curp_y_va_al_reporte(self):
        Patient.objects.filter(pk=self.familiar.pk).update(curp=CURP_MUJER_2015)
        resultado = sync.sync_patients(Patient.objects.all(), source=_Fuente([_familiar(sex_code="M")]))
        self.familiar.refresh_from_db()
        self.assertEqual(self.familiar.sex, "F")
        self.assertIn(sync.SEXO_DE_CURP, {d.kind for d in resultado.discrepancies})

    def test_sin_sexo_en_sermed_no_borra_el_que_hay(self):
        Patient.objects.filter(pk=self.familiar.pk).update(sex="F")
        sync.sync_patients(Patient.objects.all(), source=_Fuente([_familiar(sex_code=None)]))
        self.familiar.refresh_from_db()
        self.assertEqual(self.familiar.sex, "F")


class MigracionesSexoYPersonaTests(TransactionTestCase):
    """Prueba REAL de 0056-0058 con datos en la convencion vieja."""

    migrate_from = [("consulta_medica", "0055_bitacora_cambios_inmutable")]
    migrate_to = [("consulta_medica", "0058_persona_obligatoria")]
    serialized_rollback = True

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_convierte_el_sexo_y_da_una_persona_a_cada_registro(self):
        Paciente = self.old_apps.get_model("consulta_medica", "Patient")
        Revision = self.old_apps.get_model("consulta_medica", "PatientRevision")
        hombre = Paciente.objects.create(no_exp="1", pk_num=0, sex="H")
        mujer = Paciente.objects.create(no_exp="2", pk_num=0, sex="M")
        no_binario = Paciente.objects.create(no_exp="3", pk_num=0, sex="X")
        sin_dato = Paciente.objects.create(no_exp="4", pk_num=0, sex=None)
        Revision.objects.create(patient=mujer, previous_sex="H")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        Paciente = apps.get_model("consulta_medica", "Patient")
        Revision = apps.get_model("consulta_medica", "PatientRevision")

        sexo = dict(Paciente.objects.values_list("no_exp", "sex"))
        self.assertEqual(sexo, {"1": "M", "2": "F", "3": "X", "4": None})
        self.assertEqual(Revision.objects.get().previous_sex, "M")

        filas = Paciente.objects.values_list("pk", "uuid", "person__uuid")
        self.assertEqual(len(filas), 4)
        for pk, uuid_paciente, uuid_persona in filas:
            self.assertEqual(uuid_paciente, uuid_persona, f"paciente {pk}")
        self.assertEqual(
            len({p for p in Paciente.objects.values_list("person_id", flat=True)}), 4,
            "cada registro existente tiene su propia persona",
        )
        for paciente in (hombre, mujer, no_binario, sin_dato):
            self.assertTrue(Paciente.objects.filter(pk=paciente.pk).exists())
