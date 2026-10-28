"""
5.2 paso 3: HABITO como el documento. Estado N/A/E, desde/hasta como anios y
una sola fila vigente por paciente y habito: editar crea una version nueva, la
anterior pasa a B y el cambio va a la bitacora (ACTUALIZACION).
"""
import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status

from apps.catalogos.models import CatHabito
from apps.consulta_medica.models import ChangeLog, Habit
from apps.consulta_medica.tests.test_consultation_audit_api import _ConsultationAuditApiTestBase
# Se importa el modulo para la fila de ejemplo: una clase de test importada
# aqui la descubriria el runner otra vez y repetiria sus tests.
from apps.consulta_medica.tests import test_unified_history
from apps.consulta_medica.tests.test_unified_history import _UnifiedApiBase
from apps.consulta_medica.tests.test_migrar_historial_clinico_legacy import _mock_conn


def _habit_id(code):
    return CatHabito.objects.get(code=code).id


class HabitVersioningApiTests(_UnifiedApiBase):
    def _create_smoking(self, **extra):
        return self._post(
            self._url("habits"),
            {"habitId": _habit_id("tabaquismo"), "quantity": "10 cigarros", "since": 2010, **extra},
        )

    def test_alta_con_anios_y_vigente(self):
        created = self._create_smoking()

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["since"], 2010)
        self.assertEqual(created.data["recordStatus"], "A")
        listed = self.client.get(self._url("habits")).data["items"]
        self.assertEqual([item["history"] for item in listed], [[]])

    def test_no_se_agrega_otro_vigente_del_mismo_habito(self):
        self._create_smoking()

        second = self._create_smoking()

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Habit.objects.count(), 1)

    def test_editar_crea_version_nueva_y_deja_la_anterior_en_b(self):
        first = self._create_smoking()

        updated = self._patch(
            self._url(f"habits/{first.data['id']}"),
            {"status": "E", "until": 2020, "reason": "Lo dejo por indicacion medica"},
        )

        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertNotEqual(updated.data["id"], first.data["id"])
        self.assertEqual((updated.data["status"], updated.data["until"]), ("E", 2020))
        # Lo que no se edito pasa tal cual a la version nueva.
        self.assertEqual((updated.data["quantity"], updated.data["since"]), ("10 cigarros", 2010))
        self.assertEqual(Habit.objects.get(pk=first.data["id"]).record_status, "B")

        listed = self.client.get(self._url("habits")).data["items"]
        self.assertEqual(len(listed), 1)
        self.assertEqual([old["status"] for old in listed[0]["history"]], ["A"])

        entrada = ChangeLog.objects.get(table="cns_habito")
        self.assertEqual(entrada.reason, ChangeLog.Reason.CLINICAL_UPDATE)
        self.assertEqual(entrada.key, f"id_habito_paciente|{first.data['id']}")
        self.assertEqual(entrada.previous_value["status"], "A")
        self.assertEqual(entrada.new_value["status"], "E")
        self.assertEqual(entrada.new_value["until"], 2020)
        self.assertEqual(entrada.new_value["id_version_nueva"], updated.data["id"])
        self.assertEqual(entrada.new_value["motivo"], "Lo dejo por indicacion medica")

    def test_guardar_sin_cambios_no_crea_version(self):
        first = self._create_smoking()

        same = self._patch(self._url(f"habits/{first.data['id']}"), {"quantity": "10 cigarros"})

        self.assertEqual(same.data["id"], first.data["id"])
        self.assertEqual(Habit.objects.count(), 1)
        self.assertFalse(ChangeLog.objects.filter(table="cns_habito").exists())

    def test_la_version_anterior_ya_no_se_edita(self):
        first = self._create_smoking()
        self._patch(self._url(f"habits/{first.data['id']}"), {"quantity": "5 cigarros"})

        stale = self._patch(self._url(f"habits/{first.data['id']}"), {"quantity": "1 cigarro"})

        self.assertEqual(stale.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_se_cambia_el_tipo_de_habito(self):
        first = self._create_smoking()

        response = self._patch(self._url(f"habits/{first.data['id']}"), {"habitId": _habit_id("alcoholismo")})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("habitId", response.data["details"])

    def test_dar_de_baja_permite_registrar_otro(self):
        first = self._create_smoking()
        self._delete(self._url(f"habits/{first.data['id']}"), {"reason": "Capturado en otro paciente"})

        again = self._create_smoking()

        self.assertEqual(again.status_code, status.HTTP_201_CREATED)


class HabitRulesTests(_UnifiedApiBase):
    def _post_habit(self, body):
        return self._post(self._url("habits"), {"habitId": _habit_id("alcoholismo"), **body})

    def test_lo_niega_sin_cantidad_ni_anios(self):
        ok = self._post_habit({"status": "N"})
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ok.data["status"], "N")

    def test_lo_niega_con_cantidad_se_rechaza(self):
        response = self._post_habit({"status": "N", "quantity": "3 copas"})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("status", response.data["details"])

    def test_hasta_solo_con_lo_dejo(self):
        response = self._post_habit({"status": "A", "until": 2015})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("until", response.data["details"])

    def test_lo_dejo_antes_de_empezar(self):
        response = self._post_habit({"status": "E", "since": 2018, "until": 2015})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_anio_futuro_se_rechaza(self):
        response = self._post_habit({"since": timezone.localdate().year + 1})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("since", response.data["details"])

    def test_anio_absurdo_lo_rechaza_el_serializer(self):
        response = self._post_habit({"since": 1800})

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_lo_dejo_con_anios_validos(self):
        response = self._post_habit({"status": "E", "since": 2005, "until": 2015})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class HabitLegacyImportTests(_ConsultationAuditApiTestBase):
    ROW = test_unified_history.MigrarHistoriaEstomatologiaLegacyTests.ROW

    @patch("apps.authentication.management.commands._legacy_mysql_base.pymysql.connect")
    def test_el_legado_no_pisa_el_habito_vigente_capturado_en_sires(self, mock_connect):
        # Mismo habito con OTRO texto: el legado entra como version anterior.
        Habit.objects.create(
            no_exp="EXPDENT1", pk_num=0, habit_id=_habit_id("alimentacion"), notes="Dieta capturada en SIRES",
        )
        mock_connect.return_value = _mock_conn([dict(self.ROW)])

        call_command("migrar_historia_estomatologia_legacy", host="x", user="x", password="x",
                     database="x", stdout=StringIO())

        diet = Habit.objects.filter(patient__no_exp="EXPDENT1", habit__code="alimentacion")
        self.assertEqual(diet.count(), 2)
        self.assertEqual(diet.get(record_status="A").notes, "Dieta capturada en SIRES")
        legacy = diet.get(record_status="B")
        self.assertEqual((legacy.notes, legacy.source), ("Dieta blanda", "legacy"))


class HabitHistoryDataMigrationTests(TransactionTestCase):
    """Prueba REAL de la 0048: fecha -> anio sin perder el dato, y duplicados
    vigentes resueltos antes del indice unico (ninguno se borra)."""

    migrate_from = [("consulta_medica", "0047_antecedentes_sw_presente")]
    migrate_to = [("consulta_medica", "0048_habito_historial")]
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

    def test_desde_pasa_a_anio_y_los_duplicados_quedan_como_anteriores(self):
        OldHabit = self.old_apps.get_model("consulta_medica", "Habit")
        smoking = self.old_apps.get_model("catalogos", "CatHabito").objects.get(code="tabaquismo").id
        older = OldHabit.objects.create(no_exp="MIG1", pk_num=0, habit_id=smoking, since=datetime.date(2010, 6, 15))
        newer = OldHabit.objects.create(no_exp="MIG1", pk_num=0, habit_id=smoking, quantity="5")
        other = OldHabit.objects.create(no_exp="MIG2", pk_num=0, habit_id=smoking)

        apps = self._migrate_forward()
        Habit = apps.get_model("consulta_medica", "Habit")

        self.assertEqual(Habit.objects.get(pk=older.pk).since, 2010)
        self.assertEqual(Habit.objects.get(pk=older.pk).record_status, "B")
        self.assertEqual(Habit.objects.get(pk=newer.pk).record_status, "A")
        self.assertEqual(Habit.objects.get(pk=other.pk).record_status, "A")
        self.assertEqual(Habit.objects.count(), 3)
