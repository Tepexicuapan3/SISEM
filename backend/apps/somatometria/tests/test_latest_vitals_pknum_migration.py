from datetime import timedelta

from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class LatestVitalsPkNumRebuildMigrationTests(TransactionTestCase):
    """
    Migracion 0005 (somatometria-reuso-signos-mismo-dia, Fase 1).

    `PatientLatestVitals` estaba indexado solo por `no_exp`, pero `no_exp`
    es compartido por todo el nucleo familiar (titular + derechohabientes,
    distinguidos por `pk_num`). Esta migracion repara la identidad del
    cache: la clave efectiva pasa a ser el PAR (no_exp, pk_num).

    Valida spec:
    - "Titular y derechohabiente no se pisan"
    - "Reconstruccion del cache en la migracion"
    """

    migrate_from = [("somatometria", "0004_patientlatestvitals")]
    migrate_to = [("somatometria", "0005_latest_vitals_pknum_rebuild")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        executor.migrate(self.migrate_from)

        Visit = old_apps.get_model("recepcion", "Visit")
        VisitVitalSigns = old_apps.get_model("somatometria", "VisitVitalSigns")

        now = timezone.now()

        # Titular (pk_num=0, default): dos capturas en visitas distintas.
        # La migracion debe quedarse con la MAS RECIENTE por fch_alta.
        titular_visit_old = Visit.objects.create(
            folio="MIG-0001",
            no_exp="EXP-FAM-1",
            arrival_type="walk_in",
            status="lista_para_doctor",
        )
        titular_vitals_old = VisitVitalSigns.objects.create(
            id_visit=titular_visit_old,
            weight_kg="70.00",
            height_cm="170.00",
            bmi="24.22",
        )
        VisitVitalSigns.objects.filter(pk=titular_vitals_old.pk).update(
            fch_alta=now - timedelta(days=30),
        )

        titular_visit_new = Visit.objects.create(
            folio="MIG-0002",
            no_exp="EXP-FAM-1",
            arrival_type="walk_in",
            status="lista_para_doctor",
        )
        titular_vitals_new = VisitVitalSigns.objects.create(
            id_visit=titular_visit_new,
            weight_kg="72.50",
            height_cm="170.00",
            bmi="25.09",
        )
        self.titular_captured_at = now - timedelta(days=1)
        VisitVitalSigns.objects.filter(pk=titular_vitals_new.pk).update(
            fch_alta=self.titular_captured_at,
        )

        # Derechohabiente del MISMO no_exp (pk_num=2): una sola captura.
        # No debe pisar ni ser pisado por el cache del titular.
        derecho_visit = Visit.objects.create(
            folio="MIG-0003",
            no_exp="EXP-FAM-1",
            pk_num=2,
            arrival_type="walk_in",
            status="lista_para_doctor",
        )
        derecho_vitals = VisitVitalSigns.objects.create(
            id_visit=derecho_visit,
            weight_kg="18.30",
            height_cm="95.00",
            bmi="20.27",
        )
        self.derecho_captured_at = now - timedelta(hours=2)
        VisitVitalSigns.objects.filter(pk=derecho_vitals.pk).update(
            fch_alta=self.derecho_captured_at,
        )

        # Visita legacy sin no_exp: debe descartarse (inatribuible),
        # nunca reventar la migracion.
        Visit.objects.create(
            folio="MIG-0004",
            no_exp=None,
            arrival_type="walk_in",
            status="lista_para_doctor",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.new_apps = executor.loader.project_state(self.migrate_to).apps
        self.Latest = self.new_apps.get_model("somatometria", "PatientLatestVitals")

    def tearDown(self):
        # Este test crea visitas SIN expediente (ver test_visitas_sin_no_exp_se_descartan):
        # no hay llave para darles id_paciente al llegar al NOT NULL, asi que se
        # borran antes de dejar el schema en el ultimo estado.
        for label in ("somatometria.PatientLatestVitals", "somatometria.VisitVitalSigns", "recepcion.Visit"):
            self.new_apps.get_model(*label.split(".")).objects.all().delete()
        # Deja el schema en el ultimo estado de la app para no interferir
        # con el resto de la suite de tests.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_titular_y_derechohabiente_coexisten_sin_pisarse(self):
        pk_nums = list(
            self.Latest.objects.filter(no_exp="EXP-FAM-1")
            .order_by("pk_num")
            .values_list("pk_num", flat=True)
        )
        self.assertEqual(pk_nums, [0, 2])

    def test_queda_la_captura_mas_reciente_por_persona(self):
        titular = self.Latest.objects.get(no_exp="EXP-FAM-1", pk_num=0)
        self.assertEqual(str(titular.weight_kg), "72.50")

        derecho = self.Latest.objects.get(no_exp="EXP-FAM-1", pk_num=2)
        self.assertEqual(str(derecho.weight_kg), "18.30")

    def test_fch_modf_igual_al_fch_alta_de_origen_no_a_la_hora_de_la_migracion(self):
        titular = self.Latest.objects.get(no_exp="EXP-FAM-1", pk_num=0)
        self.assertEqual(titular.fch_modf, self.titular_captured_at)

        derecho = self.Latest.objects.get(no_exp="EXP-FAM-1", pk_num=2)
        self.assertEqual(derecho.fch_modf, self.derecho_captured_at)

    def test_visitas_sin_no_exp_se_descartan(self):
        self.assertEqual(self.Latest.objects.count(), 2)

    def test_unique_constraint_no_exp_pk_num(self):
        with self.assertRaises(IntegrityError):
            self.Latest.objects.create(
                no_exp="EXP-FAM-1",
                pk_num=0,
                weight_kg="1.00",
                height_cm="1.00",
                bmi="1.00",
            )
