"""
Historia clinica unificada: parseo del texto del legado, migracion de datos
0029 (nada se pierde antes de que 0030 borre columnas), registros
permanentes, odontograma versionado, exploracion fisica por consulta,
estado de alergias e importacion de his_clinicad.
"""
import datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from rest_framework import status

from apps.administracion.models import AuditoriaEvento
from apps.catalogos.models import CatCies, CatHabito, CatRegionCorporal
from apps.catalogos.services.sensitive_diagnosis_service import invalidate_cache
from apps.consulta_medica.models import (
    Allergy,
    FamilyHistory,
    Habit,
    HistoricalNote,
    LegacyVitalSigns,
    Odontogram,
    PersonalHistory,
    PhysicalExamFinding,
    SurgicalHistory,
)
from apps.consulta_medica.services.legacy_history_parsing import (
    is_negative_allergy,
    parse_legacy_vitals,
    split_allergy_items,
    split_annotations,
)
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase
from apps.consulta_medica.repositories.clinical_history_repository import ClinicalHistoryRepository
from apps.consulta_medica.tests.test_migrar_historial_clinico_legacy import _mock_conn


class LegacyTextParsingTests(SimpleTestCase):
    def test_splits_signed_annotations_with_date_and_author(self):
        text = "Texto viejo sin firma [05/06/2019 (ana)] - Segunda nota [07/08/2020 (luis)] - cola"

        self.assertEqual(
            split_annotations(text),
            [
                ("Texto viejo sin firma", datetime.date(2019, 6, 5), "ana"),
                ("Segunda nota", datetime.date(2020, 8, 7), "luis"),
                ("cola", None, None),
            ],
        )

    def test_text_without_signature_is_one_annotation(self):
        self.assertEqual(split_annotations("  solo texto  "), [("solo texto", None, None)])
        self.assertEqual(split_annotations(None), [])

    def test_negative_answers_are_not_allergies(self):
        for text in ("NEGADAS", "Niega", "ninguna.", "Interrogadas y negadas", "N/A"):
            self.assertTrue(is_negative_allergy(text), text)
        self.assertFalse(is_negative_allergy("Penicilina"))

    def test_allergy_items_split_by_comma_but_not_slash(self):
        self.assertEqual(
            split_allergy_items("Penicilina, TMP/SMX; mariscos, negadas"),
            ["Penicilina", "TMP/SMX", "mariscos"],
        )

    def test_legacy_vitals_parsed_within_plausible_ranges(self):
        parsed = parse_legacy_vitals(weight="70", height="1.65", blood_pressure="120//80",
                                     pulse="72", temperature="36.5", respiration="18")

        self.assertEqual(parsed["weight_kg"], Decimal("70.00"))
        self.assertEqual(parsed["height_cm"], Decimal("165.00"))
        self.assertEqual((parsed["blood_pressure_systolic"], parsed["blood_pressure_diastolic"]), (120, 80))
        self.assertEqual(parsed["heart_rate_bpm"], 72)
        self.assertEqual(parsed["temperature_c"], Decimal("36.5"))
        self.assertEqual(parsed["respiratory_rate_bpm"], 18)
        self.assertEqual(parsed["bmi"], Decimal("25.71"))

    def test_legacy_vitals_placeholders_and_out_of_range_are_null(self):
        # Relleno real del dump: "0", ".", "..", TA sin diastolica, pulso 5 digitos.
        parsed = parse_legacy_vitals(weight="0", height=".", blood_pressure="120",
                                     pulse="72000", temperature="..", respiration="0")

        self.assertTrue(all(value is None for value in parsed.values()), parsed)
        self.assertEqual(parse_legacy_vitals(height="170")["height_cm"], Decimal("170.00"))
        # Sistolica menor o igual que diastolica: dato invertido, no se adivina.
        self.assertIsNone(parse_legacy_vitals(blood_pressure="80/120")["blood_pressure_systolic"])


class HistoriaClinicaUnificadaDataMigrationTests(TransactionTestCase):
    """Prueba REAL de la migracion 0029: se baja la BD a 0028 (esquema viejo
    + tablas nuevas), se cargan datos con la forma anterior y se aplica hasta
    0030 -- todo lo que 0030 borra tiene que haber llegado a su destino."""

    migrate_from = [("consulta_medica", "0028_historia_clinica_unificada_esquema")]
    migrate_to = [("consulta_medica", "0030_historia_clinica_unificada_limpieza")]
    # TransactionTestCase vacia las tablas al terminar: sin esto los catalogos
    # que siembran las migraciones (tipos de alergia, habitos...) no estarian
    # para el siguiente test.
    serialized_rollback = True

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _migrate_forward(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def test_moves_every_removed_column_to_its_new_home(self):
        ClinicalHistory = self.old_apps.get_model("consulta_medica", "ClinicalHistory")
        StomatologyHistory = self.old_apps.get_model("consulta_medica", "StomatologyHistory")
        OdontogramTooth = self.old_apps.get_model("consulta_medica", "OdontogramTooth")
        OldAllergy = self.old_apps.get_model("consulta_medica", "Allergy")

        ClinicalHistory.objects.create(
            no_exp="MIG1", pk_num=0,
            family_history="Madre diabetica [01/02/2020 (ana)] - Padre HTA [03/04/2021 (luis)] - ",
            chest_exam="Campos pulmonares limpios",
            allergies="Penicilina, negadas",
        )
        StomatologyHistory.objects.create(
            no_exp="MIG1", pk_num=0, family_diabetes=True, personal_hiv=True,
            personal_smoking=True, diet="Alta en azucares", surgical_history="Apendicectomia 2010",
            allergy_anesthesia="Lidocaina", cause_of_death="Infarto",
        )
        OdontogramTooth.objects.create(no_exp="MIG1", pk_num=0, tooth_fdi="16", condition="caries")
        OdontogramTooth.objects.create(no_exp="MIG1", pk_num=0, tooth_fdi="26", condition="filled")
        OdontogramTooth.objects.create(no_exp="MIG1", pk_num=0, tooth_fdi="55", condition="missing")
        OldAllergy.objects.create(
            no_exp="MIG1", pk_num=0, category="food", substance="Nuez", severity="mild",
            source="general", is_active=False,
        )

        apps = self._migrate_forward()
        Note = apps.get_model("consulta_medica", "HistoricalNote")
        NewAllergy = apps.get_model("consulta_medica", "Allergy")

        background = list(Note.objects.filter(no_exp="MIG1", section="antecedentes", specialty="general")
                          .order_by("noted_on").values_list("content", "author"))
        self.assertEqual(background, [("Madre diabetica", "ana"), ("Padre HTA", "luis")])
        self.assertTrue(Note.objects.filter(section="torax", content="Campos pulmonares limpios").exists())
        self.assertTrue(Note.objects.filter(section="alergias", content="Penicilina, negadas").exists())

        substances = set(NewAllergy.objects.filter(is_active=True).values_list("substance", "category"))
        self.assertEqual(substances, {("Penicilina", "other"), ("Lidocaina", "anesthesia")})
        self.assertEqual(NewAllergy.objects.get(substance="Nuez").status, "entered_in_error")

        FamilyModel = apps.get_model("consulta_medica", "FamilyHistory")
        self.assertEqual(
            set(FamilyModel.objects.values_list("description", "is_deceased")),
            {("Diabetes mellitus", False), ("Familiar finado", True)},
        )
        self.assertTrue(apps.get_model("consulta_medica", "PersonalHistory").objects.filter(description="VIH").exists())
        habits = set(apps.get_model("consulta_medica", "Habit").objects.values_list("habit__code", "notes"))
        self.assertEqual(habits, {("tabaquismo", None), ("alimentacion", "Alta en azucares")})
        self.assertTrue(
            apps.get_model("consulta_medica", "SurgicalHistory").objects.filter(procedure="Apendicectomia 2010").exists()
        )

        OdontogramModel = apps.get_model("consulta_medica", "Odontogram")
        version = OdontogramModel.objects.get(no_exp="MIG1")
        self.assertEqual(version.origin, "migrated")
        self.assertEqual(version.dentition, "M")
        self.assertEqual((version.dmft_decayed, version.dmft_missing, version.dmft_filled), (1, 1, 1))
        self.assertEqual(version.teeth.count(), 3)


class NucleoPacienteDataMigrationTests(HistoriaClinicaUnificadaDataMigrationTests):
    """Prueba REAL de la migracion 0032 (Nucleo del paciente tal cual el
    documento): se baja a 0031, se cargan datos con la forma anterior y se
    aplica hasta 0033, que borra lo que 0032 debio mover."""

    migrate_from = [("consulta_medica", "0031_paciente_esquema")]
    migrate_to = [("consulta_medica", "0033_paciente_limpieza")]

    def test_moves_every_removed_column_to_its_new_home(self):
        apps = self.old_apps
        ClinicalHistory = apps.get_model("consulta_medica", "ClinicalHistory")
        Revision = apps.get_model("consulta_medica", "ClinicalHistoryRevision")
        Note = apps.get_model("consulta_medica", "HistoricalNote")
        OldAllergy = apps.get_model("consulta_medica", "Allergy")
        OldPersonal = apps.get_model("consulta_medica", "PersonalHistory")
        OldHabit = apps.get_model("consulta_medica", "Habit")
        CatHabitoOld = apps.get_model("catalogos", "CatHabito")

        history = ClinicalHistory.objects.create(
            no_exp="NUC1", pk_num=0, curp="PEGJ850315HDFRRN09", sex="H", phone="5551112222",
        )
        Revision.objects.create(history=history, previous_phone="5550000000", changed_by_id=7)
        Note.objects.create(no_exp="NUC1", pk_num=0, section="torax", content="Normal", origin="legacy_text")
        Note.objects.create(no_exp="SOLO_NOTA", pk_num=2, section="antecedentes", content="x", origin="revision")
        OldAllergy.objects.create(no_exp="NUC1", pk_num=0, category="anesthesia", substance="Lidocaina",
                                  severity="severe", source="general", status="resolved")
        OldPersonal.objects.create(no_exp="NUC1", pk_num=0, description="Asma", status="resolved")
        OldHabit.objects.create(no_exp="NUC1", pk_num=0, habit_id=CatHabitoOld.objects.get(code="tabaquismo").id,
                                status="former")

        apps = self._migrate_forward()
        Patient = apps.get_model("consulta_medica", "Patient")
        PatientRevision = apps.get_model("consulta_medica", "PatientRevision")
        NewHistory = apps.get_model("consulta_medica", "ClinicalHistory")
        NewNote = apps.get_model("consulta_medica", "HistoricalNote")

        patient = Patient.objects.get(no_exp="NUC1", pk_num=0)
        self.assertEqual((patient.curp, patient.sex, patient.phone), ("PEGJ850315HDFRRN09", "H", "5551112222"))
        header = NewHistory.objects.get(no_exp="NUC1")
        self.assertEqual(header.patient_id, patient.pk)
        self.assertIsNotNone(header.opened_on)
        revision = PatientRevision.objects.get()
        self.assertEqual((revision.patient_id, revision.previous_phone, revision.changed_by_id),
                         (patient.pk, "5550000000", 7))

        self.assertEqual(NewNote.objects.get(no_exp="NUC1").clinical_history_id, header.pk)
        self.assertEqual(NewNote.objects.get(no_exp="NUC1").origin, "M")
        orphan_note = NewNote.objects.get(no_exp="SOLO_NOTA")
        self.assertEqual(orphan_note.origin, "V")
        self.assertTrue(Patient.objects.filter(no_exp="SOLO_NOTA", pk_num=2).exists())

        allergy = apps.get_model("consulta_medica", "Allergy").objects.get()
        self.assertEqual((allergy.allergy_type_id, allergy.severity, allergy.status), (2, "G", "R"))
        self.assertEqual(apps.get_model("consulta_medica", "PersonalHistory").objects.get().status, "R")
        self.assertEqual(apps.get_model("consulta_medica", "Habit").objects.get().status, "E")


class DocumentoEstructuraDataMigrationTests(HistoriaClinicaUnificadaDataMigrationTests):
    """Prueba REAL de la 0035: FKs de estomatologia (id_historia,
    id_hc_estoma), indice_cpod y cd_servicio_origen de alergias."""

    migrate_from = [("consulta_medica", "0034_documento_estructura_esquema")]
    migrate_to = [("consulta_medica", "0036_documento_estructura_limpieza")]

    def test_moves_every_removed_column_to_its_new_home(self):
        apps = self.old_apps
        Section = apps.get_model("consulta_medica", "StomatologyHistory")
        Odontogram = apps.get_model("consulta_medica", "Odontogram")
        Allergy = apps.get_model("consulta_medica", "Allergy")

        Section.objects.create(no_exp="EST1", pk_num=0, oral_hygiene="good")
        Odontogram.objects.create(no_exp="ODO1", pk_num=1, dmft_decayed=2, dmft_missing=1, dmft_filled=3)
        Allergy.objects.create(no_exp="EST1", pk_num=0, allergy_type_id=3, substance="Latex",
                               severity="M", source="stomatology")
        Allergy.objects.create(no_exp="EST1", pk_num=0, allergy_type_id=1, substance="Sulfas",
                               severity="L", source="general")

        apps = self._migrate_forward()
        History = apps.get_model("consulta_medica", "ClinicalHistory")
        Section = apps.get_model("consulta_medica", "StomatologyHistory")
        Odontogram = apps.get_model("consulta_medica", "Odontogram")
        Allergy = apps.get_model("consulta_medica", "Allergy")

        section = Section.objects.get(no_exp="EST1")
        self.assertEqual(section.clinical_history_id, History.objects.get(no_exp="EST1").pk)
        odontogram = Odontogram.objects.get(no_exp="ODO1")
        # Sin seccion dental previa: se abre la seccion (y su historia) del paciente.
        self.assertEqual(odontogram.stomatology_history.no_exp, "ODO1")
        self.assertEqual(odontogram.stomatology_history.clinical_history.no_exp, "ODO1")
        self.assertEqual(int(odontogram.dmft_total), 6)
        self.assertEqual(
            dict(Allergy.objects.values_list("substance", "service_origin_code")),
            {"Latex": 5, "Sulfas": 1},
        )


class SignosVitalesLegadoDataMigrationTests(HistoriaClinicaUnificadaDataMigrationTests):
    """Prueba REAL de la 0039: las notas de texto "signos_vitales" que ya
    hubiera creado el importador pasan a cns_signos_vitales_legado."""

    migrate_from = [("consulta_medica", "0038_signos_vitales_legado")]
    migrate_to = [("consulta_medica", "0039_signos_vitales_legado_datos")]

    def test_moves_every_removed_column_to_its_new_home(self):
        Patient = self.old_apps.get_model("consulta_medica", "Patient")
        History = self.old_apps.get_model("consulta_medica", "ClinicalHistory")
        Note = self.old_apps.get_model("consulta_medica", "HistoricalNote")
        patient = Patient.objects.create(no_exp="SV1", pk_num=0)
        history = History.objects.create(patient=patient, no_exp="SV1", pk_num=0)
        Note.objects.create(
            clinical_history=history, no_exp="SV1", pk_num=0, section="signos_vitales", origin="M",
            content="Ultima medicion registrada (fecha desconocida): Peso: 70; Talla: 1.70; TA: 120/80",
            legacy_ref="his_clinica:9",
        )
        Note.objects.create(clinical_history=history, no_exp="SV1", pk_num=0, section="padecimiento",
                            content="Cefalea", legacy_ref="his_clinica:9:ds_padecimiento")

        apps = self._migrate_forward()
        Vitals = apps.get_model("consulta_medica", "LegacyVitalSigns")
        Note = apps.get_model("consulta_medica", "HistoricalNote")

        vitals = Vitals.objects.get(legacy_ref="his_clinica:9")
        self.assertEqual(vitals.weight_kg, Decimal("70.00"))
        self.assertEqual(vitals.height_cm, Decimal("170.00"))
        self.assertEqual(vitals.blood_pressure_systolic, 120)
        self.assertEqual(vitals.raw_text, "Peso: 70; Talla: 1.70; TA: 120/80")
        self.assertEqual(list(Note.objects.values_list("section", flat=True)), ["padecimiento"])


class _UnifiedApiBase(_ConsultationAuditApiTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        invalidate_cache()
        self.no_exp = "EXPUNI1"
        self._login_doctor()

    def _url(self, suffix):
        return f"/api/v1/patients/{self.no_exp}/{suffix}?pkNum=0"

    def _post(self, url, body):
        return self.client.post(url, body, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers())

    def _patch(self, url, body):
        return self.client.patch(url, body, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers())

    def _delete(self, url, body):
        return self.client.delete(url, body, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers())


class PatientRecordsApiTests(_UnifiedApiBase):
    def test_personal_history_crud_with_soft_delete_and_audit(self):
        created = self._post(self._url("personal-history"), {"cieCode": "A090", "diagnosisDate": "2020-01-01"})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        record_id = created.data["id"]
        self.assertEqual(created.data["cieDescription"], "GASTROENTERITIS")

        updated = self._patch(self._url(f"personal-history/{record_id}"), {"status": "R"})
        self.assertEqual(updated.data["status"], "R")

        no_reason = self._delete(self._url(f"personal-history/{record_id}"), {})
        self.assertEqual(no_reason.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        deleted = self._delete(self._url(f"personal-history/{record_id}"), {"reason": "Capturado en otro paciente"})
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)

        self.assertEqual(self.client.get(self._url("personal-history")).data["items"], [])
        record = PersonalHistory.objects.get(pk=record_id)
        self.assertFalse(record.is_active)
        self.assertEqual(record.deletion_reason, "Capturado en otro paciente")
        actions = set(AuditoriaEvento.objects.values_list("accion", flat=True))
        self.assertTrue({"PersonalHistoryCreated", "PersonalHistoryUpdated", "PersonalHistoryDeactivated"} <= actions)

    def test_personal_history_requires_cie_or_description_and_valid_cie(self):
        empty = self._post(self._url("personal-history"), {})
        unknown = self._post(self._url("personal-history"), {"cieCode": "ZZZ9"})

        self.assertEqual(empty.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(unknown.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("cieCode", unknown.data["details"])

    def test_sensitive_antecedent_is_redacted_without_permission(self):
        CatCies.objects.create(code="B240", description="VIH", version="CIE-10", is_active=True)
        self._post(self._url("family-history"), {"cieCode": "B240", "description": "Tio con VIH"})

        response = self.client.get(self._url("family-history"))

        item = response.data["items"][0]
        self.assertTrue(item["isRestricted"])
        self.assertIsNone(item["cieCode"])
        self.assertNotIn("VIH", str(item))
        self.assertTrue(AuditoriaEvento.objects.filter(accion="SensitiveDiagnosisRedacted").exists())

    def test_access_profile_role_sees_sensitive_antecedent(self):
        """CAT_PERFIL_ACCESO: habilitar el rol del medico para la categoria
        VIH (via el comando) quita la redaccion sin darle el permiso."""
        CatCies.objects.create(code="B240", description="VIH", version="CIE-10", is_active=True)
        self._post(self._url("family-history"), {"cieCode": "B240", "description": "Tio con VIH"})
        self.assertTrue(self.client.get(self._url("family-history")).data["items"][0]["isRestricted"])

        call_command("perfil_acceso_sensible", agregar=True, categoria="hiv", rol="DOCTOR", stdout=StringIO())
        visible = self.client.get(self._url("family-history")).data["items"][0]

        self.assertFalse(visible["isRestricted"])
        self.assertEqual(visible["cieCode"], "B240")

        call_command("perfil_acceso_sensible", quitar=True, categoria="hiv", rol="DOCTOR", stdout=StringIO())
        self.assertTrue(self.client.get(self._url("family-history")).data["items"][0]["isRestricted"])

    def test_habit_surgical_and_treatment_resources(self):
        habit_id = CatHabito.objects.get(code="tabaquismo").id
        habit = self._post(self._url("habits"), {"habitId": habit_id, "quantity": "5 al dia"})
        surgical = self._post(self._url("surgical-history"), {"procedure": "Colecistectomia"})
        treatment = self._post(self._url("dental-treatments"), {"toothFdi": "16", "procedure": "Resina", "status": "done"})
        bad_tooth = self._post(self._url("dental-treatments"), {"toothFdi": "99", "procedure": "Resina"})

        self.assertEqual(habit.data["habitName"], "Tabaquismo")
        self.assertEqual(surgical.status_code, status.HTTP_201_CREATED)
        self.assertEqual(treatment.data["status"], "done")
        self.assertIsNotNone(treatment.data["performedAt"])
        self.assertEqual(bad_tooth.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(Habit.objects.count(), 1)
        self.assertEqual(SurgicalHistory.objects.count(), 1)

    def test_catalogs_and_historical_notes_are_read_only(self):
        history, _ = ClinicalHistoryRepository.get_or_create_for_patient(self.no_exp, 0)
        HistoricalNote.objects.create(
            clinical_history=history, no_exp=self.no_exp, pk_num=0, section="torax", content="Normal",
        )
        LegacyVitalSigns.objects.create(
            clinical_history=history, no_exp=self.no_exp, pk_num=0, weight_kg=Decimal("70.00"),
            blood_pressure_systolic=120, blood_pressure_diastolic=80, raw_text="Peso: 70; TA: 120/80",
            legacy_ref="his_clinica:1",
        )

        catalogs = self.client.get("/api/v1/clinical-catalogs")
        notes = self.client.get(self._url("historical-notes"))
        write = self._post(self._url("historical-notes"), {"content": "x"})

        self.assertEqual(len(catalogs.data["teeth"]), 52)
        self.assertEqual(len(catalogs.data["bodyRegions"]), 7)
        # CAT_TIPO_ALERGIA con los codigos exactos del documento.
        self.assertEqual([item["id"] for item in catalogs.data["allergyTypes"]], [1, 2, 3, 4, 5, 9])
        self.assertEqual(notes.data["items"][0]["content"], "Normal")
        self.assertEqual(notes.data["legacyVitals"][0]["weightKg"], "70.00")
        self.assertEqual(notes.data["legacyVitals"][0]["bloodPressureSystolic"], 120)
        self.assertIsNone(notes.data["legacyVitals"][0]["heightCm"])
        only_torax = self.client.get(self._url("historical-notes"), {"section": "torax"})
        self.assertEqual(only_torax.data["legacyVitals"], [])
        self.assertEqual(write.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class OdontogramVersioningApiTests(_UnifiedApiBase):
    def _set_tooth(self, tooth, condition, visit_id=None, face=""):
        body = {"condition": condition, "face": face}
        if visit_id:
            body["visitId"] = visit_id
        return self._patch(self._url(f"odontogram/{tooth}"), body)

    def test_one_version_per_visit_and_previous_versions_preserved(self):
        visit_a = self._make_visit()
        visit_b = self._make_visit()
        visit_a.no_exp = visit_b.no_exp = self.no_exp
        visit_a.save()
        visit_b.save()

        self._set_tooth("16", "caries", visit_a.id_visit)
        self._set_tooth("26", "filled", visit_a.id_visit)
        first = self.client.get(self._url("odontogram")).data["version"]
        self._set_tooth("16", "filled", visit_b.id_visit)

        versions = self.client.get(self._url("odontogram/versions")).data["items"]
        self.assertEqual(len(versions), 2)
        self.assertEqual(first["dmft"], {"decayed": 1, "missing": 0, "filled": 1, "index": 2})
        self.assertEqual(versions[0]["dmft"]["filled"], 2)

        old = self.client.get(self._url("odontogram") + f"&versionId={first['id']}").data
        tooth_16 = next(item for item in old["items"] if item["toothFdi"] == "16")
        self.assertEqual(tooth_16["condition"], "caries")

    def test_faces_and_invalid_inputs(self):
        self._set_tooth("16", "caries", face="O")
        faces = next(i for i in self.client.get(self._url("odontogram")).data["items"] if i["toothFdi"] == "16")["faces"]

        self.assertEqual(faces, [{"face": "O", "condition": "caries", "notes": None}])
        self.assertEqual(self._set_tooth("16", "inexistente").status_code, 422)
        self.assertEqual(self._set_tooth("99", "caries").status_code, 422)
        self.assertEqual(self._set_tooth("16", "caries", visit_id=999999).status_code, 422)
        self.assertEqual(Odontogram.objects.count(), 1)


class PhysicalExamAndAllergyStatusApiTests(_UnifiedApiBase):
    def test_physical_exam_only_editable_while_in_consultation(self):
        visit = self._visit_with_consultation()
        region_ids = list(CatRegionCorporal.objects.order_by("order").values_list("id", flat=True)[:2])
        url = f"/api/v1/visits/{visit.id_visit}/consultation/physical-exam"
        body = {"findings": [
            {"regionId": region_ids[0], "isNormal": True},
            {"regionId": region_ids[1], "isNormal": False, "finding": "Adenopatia cervical"},
        ]}

        saved = self.client.put(url, body, format="json", HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers())
        abnormal_without_text = self.client.put(
            url, {"findings": [{"regionId": region_ids[0], "isNormal": False}]}, format="json",
            **self._csrf_headers(),
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(len(saved.data["items"]), 2)
        self.assertEqual(abnormal_without_text.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Solo importa que la visita deje de estar "en_consulta" (el cierre
        # real tiene sus propios tests).
        visit.status = "consulta_finalizada"
        visit.save(update_fields=["status"])
        after_close = self.client.put(url, body, format="json", **self._csrf_headers())
        self.assertEqual(after_close.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(self.client.get(url).data["editable"])
        self.assertEqual(PhysicalExamFinding.objects.count(), 2)

    def test_allergy_status_change_requires_reason_and_affects_alerts(self):
        allergy = Allergy.objects.create(
            no_exp=self.no_exp, pk_num=0, allergy_type_id=1, substance="Penicilina",
            severity="G", service_origin_code=1,
        )
        url = self._url(f"allergies/{allergy.id_allergy}/status")

        missing_reason = self._post(url, {"status": "R"})
        resolved = self._post(url, {"status": "R", "reason": "Prueba de tolerancia negativa"})
        error = self._post(url, {"status": "E", "reason": "Paciente equivocado"})

        self.assertEqual(missing_reason.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(resolved.data["status"], "R")
        self.assertTrue(resolved.data["isActive"])
        self.assertEqual(error.data["status"], "E")
        self.assertFalse(error.data["isActive"])
        self.assertEqual(self._post(url, {"status": "A", "reason": "x"}).status_code, 404)


class MigrarHistoriaEstomatologiaLegacyTests(_ConsultationAuditApiTestBase):
    ROW = {
        "no_hisclin": 77, "no_exp": "EXPDENT1", "tp_paciente": "0", "fe_hisclin": None,
        "cd_medico": "M01", "cd_clinica": 3, "ds_ocupacion": None, "ds_edocivil": None,
        "sw_diabetes": "S", "sw_cancer": None, "sw_presalta": None, "sw_presbaja": None,
        "ds_muerte": "Infarto", "sw_diabetesp": None, "sw_asma": "S", "sw_presaltap": None,
        "sw_presbajap": None, "sw_hepatitis": None, "sw_sida": None, "sw_tabaquismo": "S",
        "sw_alcoholismo": None, "sw_toxicomias": None, "ds_habitos": None,
        "ds_alimentos": "Dieta blanda", "ds_antquir": "Amigdalectomia",
        "ds_antecedentes": "Sin datos relevantes", "ds_alemedicam": "Ampicilina",
        "ds_alemdental": None, "ds_aleanestes": "NEGADAS", "ds_aleambient": None,
        "ds_alealiment": None, "ds_aleotros": None, "ds_terapias": "Dolor molar",
        "no_peso": "70", "no_talla": "1.70", "no_ta": "120/80", "no_pulso": None,
        "no_temp": None, "no_resp": None,
    }

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_maps_his_clinicad_respecting_p_suffix_and_is_idempotent(self, mock_connect):
        out = StringIO()
        for _ in range(2):
            mock_connect.return_value = _mock_conn([dict(self.ROW)])
            call_command("migrar_historia_estomatologia_legacy", host="x", user="x", password="x",
                         database="x", stdout=out)

        base = {"no_exp": "EXPDENT1", "pk_num": 0}
        # SIN sufijo = familiar; CON sufijo p / asma = personal.
        self.assertEqual(
            set(FamilyHistory.objects.filter(**base).values_list("description", flat=True)),
            {"Diabetes mellitus", "Familiar finado"},
        )
        self.assertEqual(list(PersonalHistory.objects.filter(**base).values_list("description", flat=True)), ["Asma"])
        self.assertEqual(
            set(Habit.objects.filter(**base).values_list("habit__code", flat=True)), {"tabaquismo", "alimentacion"},
        )
        self.assertEqual(SurgicalHistory.objects.get(**base).procedure, "Amigdalectomia")
        self.assertEqual(list(Allergy.objects.filter(**base).values_list("substance", flat=True)), ["Ampicilina"])
        vitals = LegacyVitalSigns.objects.get(**base)
        self.assertEqual((vitals.weight_kg, vitals.height_cm), (Decimal("70.00"), Decimal("170.00")))
        self.assertEqual((vitals.blood_pressure_systolic, vitals.blood_pressure_diastolic), (120, 80))
        self.assertIsNone(vitals.measured_on)
        self.assertFalse(HistoricalNote.objects.filter(**base, section="signos_vitales").exists())
        self.assertTrue(HistoricalNote.objects.filter(**base, section="padecimiento", content="Dolor molar").exists())
        self.assertIn("Ya importadas: 1", out.getvalue())

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_duplicate_his_clinicad_rows_do_not_duplicate_permanent_records(self, mock_connect):
        # 26 pacientes del dump tienen mas de una fila en his_clinicad.
        second = dict(self.ROW, no_hisclin=78, sw_cancer="S")
        mock_connect.return_value = _mock_conn([dict(self.ROW), second])
        call_command("migrar_historia_estomatologia_legacy", host="x", user="x", password="x",
                     database="x", stdout=StringIO())

        base = {"no_exp": "EXPDENT1", "pk_num": 0}
        self.assertEqual(
            sorted(FamilyHistory.objects.filter(**base).values_list("description", flat=True)),
            ["Cancer", "Diabetes mellitus", "Familiar finado"],
        )
        self.assertEqual(Habit.objects.filter(**base).count(), 2)
        self.assertEqual(SurgicalHistory.objects.filter(**base).count(), 1)
        # Cada fila conserva su propia medicion de signos (fecha desconocida).
        self.assertEqual(LegacyVitalSigns.objects.filter(**base).count(), 2)
