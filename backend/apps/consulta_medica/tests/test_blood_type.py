"""
5.2: GRUPO_SANGUINEO. Una fila vigente por paciente; un cambio deja la
anterior en B y el porque en la bitacora de cambios (motivo CORRECCION).
"""
from django.db import IntegrityError, transaction
from rest_framework import status

from apps.catalogos.models import TiposSanguineo
from apps.consulta_medica.models import BloodType, ChangeLog, StudyResult, VisitConsultation
from apps.consulta_medica.repositories.clinical_history_repository import PatientRepository
from apps.consulta_medica.tests.test_unified_history import _UnifiedApiBase
from apps.consulta_medica.services.paciente_entrada import llave_publica


def _type_id(name):
    return TiposSanguineo.objects.get(name=name).id


class BloodTypeCatalogSeedTests(_UnifiedApiBase):
    def test_el_catalogo_tiene_los_8_tipos_con_los_codigos_del_legado(self):
        seeded = dict(TiposSanguineo.objects.values_list("name", "id"))

        self.assertEqual(
            seeded,
            {"A+": 1, "B-": 2, "A-": 3, "B+": 4, "AB+": 5, "AB-": 6, "O+": 7, "O-": 8},
        )

    def test_catalogos_clinicos_incluyen_los_tipos_de_sangre(self):
        catalogs = self.client.get("/api/v1/clinical-catalogs")

        self.assertEqual(len(catalogs.data["bloodTypes"]), 8)
        self.assertIn({"id": 7, "name": "O+"}, catalogs.data["bloodTypes"])


class BloodTypeApiTests(_UnifiedApiBase):
    def _put(self, body):
        return self.client.put(
            self._url("blood-type"), body, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def _changes(self):
        return ChangeLog.objects.filter(table="cns_grupo_sanguineo")

    def test_sin_tipo_de_sangre_devuelve_vacio(self):
        response = self.client.get(self._url("blood-type"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"current": None, "history": [], "conflict": False})

    def test_primera_captura_queda_vigente_y_no_va_a_la_bitacora(self):
        response = self._put({"bloodTypeId": _type_id("O+"), "source": "D"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current"]["bloodTypeName"], "O+")
        self.assertEqual(response.data["current"]["source"], "D")
        self.assertEqual(response.data["current"]["createdById"], self.doctor_user.id_usuario)
        self.assertEqual(response.data["history"], [])
        self.assertFalse(self._changes().exists())

    def test_guardar_lo_mismo_no_crea_otra_fila(self):
        self._put({"bloodTypeId": _type_id("O+"), "source": "D"})

        self._put({"bloodTypeId": _type_id("O+"), "source": "D"})

        self.assertEqual(BloodType.objects.count(), 1)

    def test_cambiar_sin_motivo_se_rechaza(self):
        self._put({"bloodTypeId": _type_id("O+"), "source": "D"})

        response = self._put({"bloodTypeId": _type_id("A+"), "source": "L"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("reason", response.data["details"])
        self.assertEqual(BloodType.objects.get().blood_type.name, "O+")

    def test_corregir_deja_la_anterior_en_b_y_el_motivo_en_la_bitacora(self):
        self._put({"bloodTypeId": _type_id("O+"), "source": "D"})

        response = self._put({
            "bloodTypeId": _type_id("A+"), "source": "L", "reason": "Resultado de laboratorio",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current"]["bloodTypeName"], "A+")
        self.assertEqual(response.data["current"]["source"], "L")
        self.assertEqual([item["bloodTypeName"] for item in response.data["history"]], ["O+"])
        self.assertEqual(response.data["history"][0]["status"], "B")

        entrada = self._changes().get()
        self.assertEqual(entrada.reason, ChangeLog.Reason.CORRECTION)
        self.assertEqual(entrada.action, ChangeLog.Action.UPDATE)
        patient = BloodType.objects.first().patient
        self.assertEqual(entrada.key, f"id_paciente|{patient.pk}")
        # Solo lo que cambio (lab_result_id siguio en None); el motivo es nuevo.
        self.assertEqual(
            entrada.previous_value, {"blood_type_id": _type_id("O+"), "source": "D", "motivo": None},
        )
        self.assertEqual(entrada.new_value, {
            "blood_type_id": _type_id("A+"), "source": "L", "motivo": "Resultado de laboratorio",
        })
        self.assertEqual(entrada.user, str(self.doctor_user.id_usuario))

    def test_tipo_invalido_se_rechaza(self):
        response = self._put({"bloodTypeId": 999, "source": "D"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("bloodTypeId", response.data["details"])

    def test_fuente_invalida_se_rechaza(self):
        response = self._put({"bloodTypeId": _type_id("O+"), "source": "X"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


class BloodTypeLabResultTests(_UnifiedApiBase):
    def setUp(self):
        super().setUp()
        visit = self._visit_with_consultation()
        self._login_doctor()
        self.no_exp = llave_publica(visit)[0]
        consultation = VisitConsultation.objects.get(id_visit=visit)
        self.result = StudyResult.objects.create(
            consultation=consultation, no_exp=llave_publica(visit)[0], pk_num=0, study_type=self.study_type,
            result_date="2026-02-01", file="resultados/grupo.pdf",
        )
        self.other_result = StudyResult.objects.create(
            consultation=consultation, no_exp="OTRO-EXP", pk_num=0, study_type=self.study_type,
            result_date="2026-02-01", file="resultados/otro.pdf",
        )

    def _put(self, body):
        return self.client.put(
            self._url("blood-type"), body, format="json",
            HTTP_X_REQUEST_ID=self.request_id, **self._csrf_headers(),
        )

    def test_laboratorio_con_resultado_del_paciente(self):
        response = self._put({"bloodTypeId": _type_id("B+"), "source": "L", "labResultId": self.result.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current"]["labResultId"], self.result.pk)

    def test_resultado_de_otro_paciente_se_rechaza(self):
        response = self._put({"bloodTypeId": _type_id("B+"), "source": "L", "labResultId": self.other_result.pk})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("labResultId", response.data["details"])

    def test_declarado_no_lleva_resultado(self):
        response = self._put({"bloodTypeId": _type_id("B+"), "source": "D", "labResultId": self.result.pk})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)


class BloodTypeConstraintTests(_UnifiedApiBase):
    def test_no_puede_haber_dos_vigentes_del_mismo_paciente(self):
        patient, _ = PatientRepository.get_or_create("EXP-RH", 0)
        BloodType.objects.create(patient=patient, blood_type_id=_type_id("O+"), source="D")

        with self.assertRaises(IntegrityError), transaction.atomic():
            BloodType.objects.create(patient=patient, blood_type_id=_type_id("A+"), source="D")

    def test_puede_haber_varias_corregidas(self):
        patient, _ = PatientRepository.get_or_create("EXP-RH", 0)
        BloodType.objects.create(patient=patient, blood_type_id=_type_id("O+"), source="D", status="B")
        BloodType.objects.create(patient=patient, blood_type_id=_type_id("A+"), source="D", status="B")
        BloodType.objects.create(patient=patient, blood_type_id=_type_id("B+"), source="L")

        self.assertEqual(BloodType.objects.filter(patient=patient).count(), 3)
