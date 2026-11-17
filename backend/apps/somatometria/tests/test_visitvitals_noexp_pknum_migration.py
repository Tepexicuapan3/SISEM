from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class VisitVitalsNoExpPkNumMigrationTests(TransactionTestCase):
    """
    Migracion 0008: denormaliza `no_exp`/`pk_num` directo en
    `smt_visit_vitals` (antes solo alcanzables via JOIN contra
    `recepcion.Visit`). Valida que el backfill de filas EXISTENTES copia
    los valores correctos desde la visita relacionada, distinguiendo
    titular (pk_num=0) de un derechohabiente (pk_num>0) que comparte el
    mismo `no_exp` (mismo cuidado que la migracion 0005).
    """

    migrate_from = [("somatometria", "0007_visitvitals_captured_by_updated_by")]
    migrate_to = [("somatometria", "0008_visitvitals_noexp_pknum_denorm")]
    # TransactionTestCase vacia las tablas al terminar (flush); sin esto los
    # content types se recrean con otros ids y los tests de migracion con
    # serialized_rollback que corren despues fallan con UNIQUE
    # django_content_type. Mismo patron que test_folio_receta.
    serialized_rollback = True

    def setUp(self):
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        executor.migrate(self.migrate_from)

        Visit = old_apps.get_model("recepcion", "Visit")
        VisitVitalSigns = old_apps.get_model("somatometria", "VisitVitalSigns")

        titular_visit = Visit.objects.create(
            folio="MIG8-0001",
            no_exp="EXP-FAM-8",
            pk_num=0,
            arrival_type="walk_in",
            status="lista_para_doctor",
        )
        self.titular_vitals_pk = VisitVitalSigns.objects.create(
            id_visit=titular_visit,
            weight_kg="70.00",
            height_cm="170.00",
            bmi="24.22",
        ).pk

        dependiente_visit = Visit.objects.create(
            folio="MIG8-0002",
            no_exp="EXP-FAM-8",
            pk_num=2,
            arrival_type="walk_in",
            status="lista_para_doctor",
        )
        self.dependiente_vitals_pk = VisitVitalSigns.objects.create(
            id_visit=dependiente_visit,
            weight_kg="30.00",
            height_cm="120.00",
            bmi="20.83",
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.new_apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        # Deja el schema en el ultimo estado de la app para no interferir
        # con el resto de la suite de tests.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_backfill_copia_no_exp_pk_num_desde_la_visita_relacionada(self):
        VisitVitalSigns = self.new_apps.get_model("somatometria", "VisitVitalSigns")

        titular_row = VisitVitalSigns.objects.get(pk=self.titular_vitals_pk)
        self.assertEqual(titular_row.no_exp, "EXP-FAM-8")
        self.assertEqual(titular_row.pk_num, 0)

        dependiente_row = VisitVitalSigns.objects.get(pk=self.dependiente_vitals_pk)
        self.assertEqual(dependiente_row.no_exp, "EXP-FAM-8")
        self.assertEqual(dependiente_row.pk_num, 2)
