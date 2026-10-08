"""
Identificadores del paciente (documento "Historia Clinica Unificada", 5.1).
"""
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.consulta_medica.models import ChangeLog, LegacyMigrationRun, Patient, PatientIdentifier
from apps.consulta_medica.repositories.clinical_history_repository import (
    ClinicalHistoryRepository,
    PatientRepository,
)
from apps.consulta_medica.services.patient_identifier_service import (
    IdentifierConflict,
    find_patient,
    identifiers_from_columns,
    register_identifier,
    retire_identifier,
)

IdType = PatientIdentifier.IdType


class PatientIdentifierServiceTests(TestCase):
    def setUp(self):
        self.titular = Patient.objects.create(no_exp="1001", pk_num=0)
        self.familiar = Patient.objects.create(no_exp="1001", pk_num=88731, legacy_family_code=52895)

    def test_alta_queda_en_la_bitacora_con_su_motivo(self):
        identificador, creado = register_identifier(
            self.familiar, IdType.PK_NUM, 88731, reason=ChangeLog.Reason.SERMED_SYNC, user="SYNC_SERMED",
        )

        self.assertTrue(creado)
        self.assertEqual(identificador.value, "88731")
        self.assertEqual(identificador.created_by, "SYNC_SERMED")
        entrada = ChangeLog.objects.get()
        self.assertEqual(entrada.key, "PK_NUM|88731")
        self.assertEqual(entrada.action, ChangeLog.Action.CREATE)
        self.assertEqual(entrada.new_value, {"id_paciente": self.familiar.pk})

    def test_registrar_dos_veces_no_duplica(self):
        register_identifier(self.familiar, IdType.PK_NUM, 88731, reason="X", user="u")
        _, creado = register_identifier(self.familiar, IdType.PK_NUM, "88731", reason="X", user="u")

        self.assertFalse(creado)
        self.assertEqual(PatientIdentifier.objects.count(), 1)
        self.assertEqual(ChangeLog.objects.count(), 1)

    def test_un_numero_no_puede_ser_de_dos_personas(self):
        register_identifier(self.familiar, IdType.PK_NUM, 88731, reason="X", user="u")

        with self.assertRaises(IdentifierConflict) as ctx:
            register_identifier(self.titular, IdType.PK_NUM, 88731, reason="X", user="u")

        self.assertEqual(ctx.exception.owner, self.familiar)

    def test_la_base_tambien_impide_dos_vigentes_iguales(self):
        PatientIdentifier.objects.create(patient=self.titular, id_type=IdType.NO_EXP, value="1001", created_by="u")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PatientIdentifier.objects.create(patient=self.familiar, id_type=IdType.NO_EXP, value="1001", created_by="u")

    def test_pk_num_y_cd_familiar_iguales_no_chocan(self):
        # Son tipos distintos: el mismo numero puede existir en los dos.
        register_identifier(self.familiar, IdType.PK_NUM, 500, reason="X", user="u")
        _, creado = register_identifier(self.titular, IdType.CD_FAMILIAR, 500, reason="X", user="u")

        self.assertTrue(creado)
        self.assertEqual(find_patient(IdType.PK_NUM, 500), self.familiar)
        self.assertEqual(find_patient(IdType.CD_FAMILIAR, 500), self.titular)

    def test_baja_conserva_la_fila_y_libera_el_numero(self):
        identificador, _ = register_identifier(self.familiar, IdType.PK_NUM, 88731, reason="X", user="u")

        self.assertTrue(retire_identifier(identificador, reason=ChangeLog.Reason.CORRECTION, user="u"))

        identificador.refresh_from_db()
        self.assertEqual(identificador.status, PatientIdentifier.Status.RETIRED)
        self.assertIsNone(find_patient(IdType.PK_NUM, 88731))
        baja = ChangeLog.objects.filter(action=ChangeLog.Action.DELETE).get()
        self.assertEqual(baja.reason, "CORRECCION")
        # Corregida una liga equivocada, el numero puede ir al paciente correcto.
        _, creado = register_identifier(self.titular, IdType.PK_NUM, 88731, reason="X", user="u")
        self.assertTrue(creado)
        self.assertFalse(retire_identifier(identificador, reason="X", user="u"))

    def test_rechaza_tipo_invalido_o_valor_vacio(self):
        with self.assertRaises(ValueError):
            register_identifier(self.titular, "RFC", "X", reason="X", user="u")
        with self.assertRaises(ValueError):
            register_identifier(self.titular, IdType.NO_EXP, "  ", reason="X", user="u")

    def test_identificadores_segun_las_columnas(self):
        legado = Patient.objects.create(no_exp="1001", pk_num=None, legacy_family_code=11)

        self.assertEqual(identifiers_from_columns(self.titular), [(IdType.NO_EXP, "1001")])
        self.assertEqual(
            identifiers_from_columns(self.familiar),
            [(IdType.PK_NUM, "88731"), (IdType.CD_FAMILIAR, "52895")],
        )
        self.assertEqual(identifiers_from_columns(legado), [(IdType.CD_FAMILIAR, "11")])
        self.assertEqual(identifiers_from_columns(self.familiar, include_family=False), [])


class PatientOpenedRegistersIdentifierTests(TestCase):
    def test_abrir_un_titular_nuevo_registra_su_no_exp(self):
        paciente, creado = PatientRepository.get_or_create("2001", 0, created_by_id=9)

        self.assertTrue(creado)
        self.assertEqual(find_patient(IdType.NO_EXP, "2001"), paciente)
        entrada = ChangeLog.objects.get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.PATIENT_OPENED)
        self.assertEqual(entrada.user, "9")

    def test_abrir_un_familiar_no_registra_identificadores(self):
        # Por aqui entra tambien la importacion del legado, que pasa cd_familiar
        # como pk_num: registrarlo guardaria el error como PK_NUM oficial.
        ClinicalHistoryRepository.get_or_create_for_patient("2001", 52895)

        self.assertFalse(PatientIdentifier.objects.exists())

    def test_sin_usuario_registra_el_proceso_sires(self):
        ClinicalHistoryRepository.get_or_create_for_patient("2002", 0)

        self.assertEqual(PatientIdentifier.objects.get().created_by, "SIRES")

    def test_un_conflicto_no_frena_la_apertura(self):
        otro = Patient.objects.create(no_exp="9999", pk_num=0)
        PatientIdentifier.objects.create(patient=otro, id_type=IdType.NO_EXP, value="2003", created_by="u")

        with self.assertLogs("apps.consulta_medica.repositories.clinical_history_repository", "WARNING"):
            paciente, creado = PatientRepository.get_or_create("2003", 0)

        self.assertTrue(creado)
        self.assertFalse(paciente.identifiers.exists())


class PoblarIdentificadoresTitularesCommandTests(TestCase):
    def test_registra_solo_titulares_y_es_idempotente(self):
        Patient.objects.create(no_exp="3001", pk_num=0)
        Patient.objects.create(no_exp="3002", pk_num=0)
        Patient.objects.create(no_exp="3001", pk_num=52895)  # familiar: fuera a proposito

        call_command("poblar_identificadores_titulares", stdout=StringIO())
        out = StringIO()
        call_command("poblar_identificadores_titulares", stdout=out)

        self.assertEqual(
            set(PatientIdentifier.objects.values_list("id_type", "value")),
            {(IdType.NO_EXP, "3001"), (IdType.NO_EXP, "3002")},
        )
        self.assertIn("Registrados: 0", out.getvalue())
        self.assertIn("Ya tenian NO_EXP: 2", out.getvalue())
        self.assertEqual(ChangeLog.objects.filter(reason=ChangeLog.Reason.MIGRATION).count(), 2)
        self.assertEqual(LegacyMigrationRun.objects.filter(command="poblar_identificadores_titulares").count(), 2)

    def test_dry_run_no_escribe(self):
        Patient.objects.create(no_exp="4001", pk_num=0)
        out = StringIO()

        call_command("poblar_identificadores_titulares", "--dry-run", stdout=out)

        self.assertFalse(PatientIdentifier.objects.exists())
        self.assertIn("[dry-run] Titulares: 1, Registrados: 1", out.getvalue())
