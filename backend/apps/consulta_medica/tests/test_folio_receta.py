"""
5.3: folio de receta "RX-<anio>-<consecutivo>". Distinto del legado
("<clinica>R<aa>-<n>") para no confundirse con los historicos; consecutivo por
anio con el contador bloqueado; se asigna al crear la receta y no cambia.
"""
import datetime

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.authentication.models import SyUsuario
from apps.catalogos.models import Medicamentos
from apps.consulta_medica.models import PrescriptionFolioCounter, VisitPrescription
from apps.consulta_medica.services.prescription_folio_service import format_folio, next_folio
from apps.consulta_medica.uses_case.consultation_usecase import save_diagnosis, save_prescriptions
from apps.consulta_medica.uses_case.prescription_dispensation_usecase import (
    get_dispensation_preview,
    list_pending_dispensation_queue,
)
from apps.consulta_medica.uses_case.prescription_item_usecase import (
    add_prescription_item,
    get_prescription_items,
)
from apps.recepcion.models import Visit
from apps.consulta_medica.services.paciente_entrada import paciente_de_llave as _paciente_de_llave

PHARMACY = ["farmacia:recetas:dispensar"]


def _noop_audit_hook(**kwargs):
    return None


class FolioServiceTests(TestCase):
    def test_formato(self):
        self.assertEqual(format_folio(2026, 123), "RX-2026-000123")

    def test_consecutivo_por_anio(self):
        self.assertEqual(next_folio(2026), ("RX-2026-000001", 1))
        self.assertEqual(next_folio(2026), ("RX-2026-000002", 2))
        self.assertEqual(next_folio(2027), ("RX-2027-000001", 1))
        self.assertEqual(PrescriptionFolioCounter.objects.get(year=2026).last_value, 2)

    def test_nunca_parece_un_folio_del_legado(self):
        # Legado: <clinica> + "R" + aa (o "F") + "-" + n. Despues de la R
        # nunca viene una X.
        folio, _ = next_folio(2026)
        self.assertTrue(folio.startswith("RX-"))


class PrescriptionFolioFlowTests(TestCase):
    def setUp(self):
        self.doctor_id = SyUsuario.objects.create(
            usuario="doctor_folio", correo="folio@example.com", clave_hash="x",
        ).id_usuario
        self.year = timezone.localdate().year
        self.medication = Medicamentos.objects.create(
            name="Paracetamol 500mg", cuadro_basico=Medicamentos.CuadroBasico.BASICO, is_controlled=False,
        )

    def _visit(self):
        n = Visit.objects.count() + 1
        return Visit.objects.create(
            folio=f"FOL-{n}", patient=_paciente_de_llave(f"EXP-FOL-{n}", 0), arrival_type=Visit.ArrivalType.APPOINTMENT,
            appointment_id=f"APP-FOL-{n}", status="en_consulta",
        )

    def _visit_with_diagnosis(self):
        # Regla existente: los medicamentos del catalogo piden el diagnostico antes.
        visit = self._visit()
        save_diagnosis(
            visit.id_visit, ["DOCTOR"], "Cefalea", "Nota", self.doctor_id, audit_hook=_noop_audit_hook,
        )
        return visit

    def _save(self, visit, items=("Paracetamol cada 8 h",)):
        return save_prescriptions(
            visit.id_visit, ["DOCTOR"], list(items), self.doctor_id, audit_hook=_noop_audit_hook,
        )

    def test_cada_receta_nueva_recibe_el_siguiente_folio(self):
        first = self._save(self._visit())
        second = self._save(self._visit())

        self.assertEqual(first["folio"], f"RX-{self.year}-000001")
        self.assertEqual(second["folio"], f"RX-{self.year}-000002")

    def test_editar_la_receta_no_cambia_el_folio(self):
        visit = self._visit()
        first = self._save(visit)

        again = self._save(visit, items=("Otra indicacion",))

        self.assertEqual(again["folio"], first["folio"])
        self.assertEqual(VisitPrescription.objects.get().sequence, 1)

    def test_la_receta_de_medicamentos_del_catalogo_tambien_tiene_folio(self):
        visit = self._visit_with_diagnosis()

        item = add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.medication.id, quantity=1,
            indications="Cada 8 horas", actor_id=self.doctor_id,
        )

        self.assertEqual(item["prescriptionFolio"], f"RX-{self.year}-000001")
        listed = get_prescription_items(visit.id_visit, ["DOCTOR"])
        self.assertEqual(listed["items"][0]["prescriptionFolio"], f"RX-{self.year}-000001")

    def test_farmacia_ve_el_folio_en_la_cola_y_en_la_vista_previa(self):
        visit = self._visit_with_diagnosis()
        item = add_prescription_item(
            visit.id_visit, ["DOCTOR"], medication_id=self.medication.id, quantity=1,
            indications="Cada 8 horas", actor_id=self.doctor_id,
        )
        prescription = VisitPrescription.objects.get()

        queue = list_pending_dispensation_queue([], PHARMACY)
        preview = get_dispensation_preview(prescription.pk, [], PHARMACY)

        self.assertEqual(queue["items"][0]["folio"], item["prescriptionFolio"])
        self.assertEqual(preview["folio"], item["prescriptionFolio"])


class FolioBackfillMigrationTests(TransactionTestCase):
    """Prueba REAL de la 0051: las recetas existentes reciben folio por orden
    de creacion y por anio, y el contador continua la serie."""

    migrate_from = [("consulta_medica", "0050_nota_morbilidad_seguimiento")]
    migrate_to = [("consulta_medica", "0051_receta_folio")]
    serialized_rollback = True

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _prescription(self, n, created_at):
        OldVisit = self.old_apps.get_model("recepcion", "Visit")
        OldPrescription = self.old_apps.get_model("consulta_medica", "VisitPrescription")
        visit = OldVisit.objects.create(
            folio=f"BKF-{n}", no_exp=f"EXP-BKF-{n}", arrival_type="appointment",
            appointment_id=f"APP-BKF-{n}", status="cerrada",
        )
        prescription = OldPrescription.objects.create(id_visit=visit, items=["x"])
        OldPrescription.objects.filter(pk=prescription.pk).update(created_at=created_at)
        return prescription.pk

    def test_folios_por_anio_en_orden_y_el_contador_continua(self):
        tz = timezone.get_current_timezone()
        late_2025 = self._prescription(1, datetime.datetime(2025, 12, 30, 10, tzinfo=tz))
        early_2025 = self._prescription(2, datetime.datetime(2025, 3, 1, 10, tzinfo=tz))
        first_2026 = self._prescription(3, datetime.datetime(2026, 1, 5, 10, tzinfo=tz))

        apps = self._migrate_forward()
        Prescription = apps.get_model("consulta_medica", "VisitPrescription")
        Counter = apps.get_model("consulta_medica", "PrescriptionFolioCounter")

        folio = lambda pk: Prescription.objects.filter(pk=pk).values_list("folio", flat=True).get()  # noqa: E731
        self.assertEqual(folio(early_2025), "RX-2025-000001")
        self.assertEqual(folio(late_2025), "RX-2025-000002")
        self.assertEqual(folio(first_2026), "RX-2026-000001")
        self.assertEqual(dict(Counter.objects.values_list("year", "last_value")), {2025: 2, 2026: 1})

    def _migrate_forward(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps
