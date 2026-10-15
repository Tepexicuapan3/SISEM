"""Migraciones 0038-0040 (change cancelacion-nota-cascada) sobre sqlite.

Cubre: seed idempotente de "CN" (y fallo explicito ante colision), copia
condicional de cat_autorizadores (S14, S15), DROP + reverse (restaura filas sin
password). La validacion en Postgres real (fresh + incremental + reverse) la
corre el usuario en una BD desechable; esto atrapa errores de logica antes.
"""
import importlib
from datetime import date
from types import SimpleNamespace

from django.apps import apps as live_apps
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

seed_0038 = importlib.import_module(
    "apps.catalogos.migrations.0038_seed_tpautorizacion_cancelacion_nota"
)
copy_0039 = importlib.import_module(
    "apps.catalogos.migrations.0039_copy_autorizadores_a_designaciones"
)

from apps.authentication.models import SyUsuario
from apps.catalogos.models import (
    CatCentroAtencion,
    DesignacionAlcance,
    DesignacionAutorizador,
    TpAutorizacion,
)

LEGACY_DDL = """
CREATE TABLE cat_autorizadores (
    id_autorizador INTEGER PRIMARY KEY AUTOINCREMENT,
    id_centro_atencion BIGINT NOT NULL,
    autorizador VARCHAR(100) NOT NULL,
    cargo VARCHAR(60) NOT NULL,
    id_tpautorizacion BIGINT NOT NULL,
    img_firma VARCHAR(200),
    pwd_autorizador VARCHAR(20) NOT NULL,
    id_usuario BIGINT NOT NULL,
    expediente VARCHAR(8),
    est_activo BOOLEAN NOT NULL DEFAULT 1,
    fch_alta DATETIME,
    fch_modf DATETIME,
    fch_baja DATETIME,
    usr_alta BIGINT,
    usr_modf BIGINT,
    usr_baja BIGINT
)
"""


def _user(n):
    return SyUsuario.objects.create(
        usuario=f"mig_user_{n}",
        correo=f"mig_user_{n}@example.com",
        clave_hash=make_password("x"),
        est_activo=True,
    )


def _center(n):
    return CatCentroAtencion.objects.create(
        name=f"Centro mig {n}", code=f"MIG-{n:03d}", center_type="CLINICA"
    )


class Seed0038Tests(TestCase):
    def test_siembra_cn_si_no_existe_y_es_idempotente(self):
        TpAutorizacion.objects.filter(code="CN").delete()
        seed_0038.seed_tp_autorizacion_cn(live_apps, None)
        seed_0038.seed_tp_autorizacion_cn(live_apps, None)
        rows = TpAutorizacion.objects.filter(code="CN")
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().name, "Cancelación de nota")

    def test_reutiliza_cn_existente_con_nombre_equivalente(self):
        TpAutorizacion.objects.filter(code="CN").delete()
        TpAutorizacion.objects.create(code="CN", name="CANCELACION DE NOTA", is_active=False)
        seed_0038.seed_tp_autorizacion_cn(live_apps, None)
        row = TpAutorizacion.objects.get(code="CN")
        self.assertTrue(row.is_active)  # reactivada
        self.assertEqual(TpAutorizacion.objects.filter(code="CN").count(), 1)

    def test_colision_con_otro_significado_falla_con_mensaje_explicito(self):
        TpAutorizacion.objects.filter(code="CN").delete()
        TpAutorizacion.objects.create(code="CN", name="Constancia Nutricional")
        with self.assertRaises(RuntimeError) as ctx:
            seed_0038.seed_tp_autorizacion_cn(live_apps, None)
        message = str(ctx.exception)
        self.assertIn("catalogos.0038", message)
        self.assertIn("'CN'", message)
        self.assertIn("Constancia Nutricional", message)
        self.assertEqual(TpAutorizacion.objects.filter(code="CN").count(), 1)  # nada se toco

    def test_la_migracion_ya_dejo_cn_sembrado_en_la_bd_de_pruebas(self):
        self.assertTrue(TpAutorizacion.objects.filter(code="CN").exists())


class Copy0039Tests(TestCase):
    """Llama a la funcion de la migracion con el registro vivo (los modelos de
    designacion son los mismos que en el estado 0037) sobre una tabla legada
    creada a mano."""

    def setUp(self):
        self.schema_editor = SimpleNamespace(connection=connection)
        self.tipo = TpAutorizacion.objects.get(code="CN")
        self.u1, self.u2 = _user(1), _user(2)
        self.c1, self.c2, self.c3 = _center(1), _center(2), _center(3)

    def _create_legacy_table(self):
        with connection.cursor() as cursor:
            cursor.execute(LEGACY_DDL)

    def _insert_legacy(self, user, center, *, cargo="Director", activo=1, baja=None, pwd="secreto"):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO cat_autorizadores (id_centro_atencion, autorizador, cargo, "
                "id_tpautorizacion, pwd_autorizador, id_usuario, est_activo, fch_baja) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [center.id, user.usuario, cargo, self.tipo.id, pwd, user.id_usuario, activo, baja],
            )

    def test_s16_sin_tabla_no_hace_nada(self):
        copy_0039.copy_autorizadores(live_apps, self.schema_editor)
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_s15_tabla_vacia_crea_cero_designaciones(self):
        self._create_legacy_table()
        copy_0039.copy_autorizadores(live_apps, self.schema_editor)
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_s14_copia_agrupando_por_usuario_y_tipo_sin_leer_password(self):
        self._create_legacy_table()
        self._insert_legacy(self.u1, self.c1, cargo="Director")
        self._insert_legacy(self.u1, self.c2, cargo="Director")  # mismo (usuario, tipo): 1 designacion, 2 centros
        self._insert_legacy(self.u2, self.c3, cargo="Subdirector")

        with CaptureQueriesContext(connection) as queries:
            copy_0039.copy_autorizadores(live_apps, self.schema_editor)

        # Ningun SELECT sobre la tabla legada enumera la columna del password.
        selects = [q["sql"] for q in queries if q["sql"].lstrip().upper().startswith("SELECT")]
        legacy_selects = [sql for sql in selects if "cat_autorizadores" in sql and "sqlite_master" not in sql]
        self.assertTrue(legacy_selects)
        self.assertFalse(any("pwd_autorizador" in sql for sql in legacy_selects), legacy_selects)

        self.assertEqual(DesignacionAutorizador.objects.count(), 2)
        d1 = DesignacionAutorizador.objects.get(user=self.u1)
        self.assertEqual(d1.authorization_type_id, self.tipo.id)
        self.assertEqual(d1.position, "Director")
        self.assertEqual(d1.start_date, date.today())
        self.assertIsNone(d1.end_date)
        self.assertIsNotNone(d1.origin_authorizer_id)
        scopes = DesignacionAlcance.objects.filter(designation=d1)
        self.assertEqual({s.scope_type for s in scopes}, {"CENTRO"})
        self.assertEqual({s.center_id for s in scopes}, {self.c1.id, self.c2.id})

        d2 = DesignacionAutorizador.objects.get(user=self.u2)
        self.assertEqual(list(d2.scopes.values_list("center_id", flat=True)), [self.c3.id])

    def test_no_copia_filas_dadas_de_baja_ni_inactivas(self):
        self._create_legacy_table()
        self._insert_legacy(self.u1, self.c1, activo=0)
        self._insert_legacy(self.u2, self.c2, baja="2026-01-01 00:00:00")
        copy_0039.copy_autorizadores(live_apps, self.schema_editor)
        self.assertEqual(DesignacionAutorizador.objects.count(), 0)

    def test_es_reejecutable_sin_duplicar(self):
        self._create_legacy_table()
        self._insert_legacy(self.u1, self.c1)
        copy_0039.copy_autorizadores(live_apps, self.schema_editor)
        copy_0039.copy_autorizadores(live_apps, self.schema_editor)
        self.assertEqual(DesignacionAutorizador.objects.count(), 1)
        self.assertEqual(DesignacionAlcance.objects.count(), 1)

    def test_reverse_borra_solo_lo_copiado(self):
        manual = DesignacionAutorizador.objects.create(
            user=self.u2, authorization_type=self.tipo, position="Manual", start_date=date.today()
        )
        DesignacionAlcance.objects.create(designation=manual, scope_type="CENTRO", center=self.c1)

        self._create_legacy_table()
        self._insert_legacy(self.u1, self.c2)
        copy_0039.copy_autorizadores(live_apps, self.schema_editor)
        self.assertEqual(DesignacionAutorizador.objects.count(), 2)

        copy_0039.remove_copied_designaciones(live_apps, self.schema_editor)
        self.assertEqual(list(DesignacionAutorizador.objects.values_list("pk", flat=True)), [manual.pk])
        self.assertEqual(DesignacionAlcance.objects.count(), 1)


class Roundtrip0039_0040Tests(TransactionTestCase):
    """Camino real del executor: 0038 <-> 0040 (DeleteModel + DROP + reverse)."""

    at_0038 = [("catalogos", "0038_seed_tpautorizacion_cancelacion_nota")]
    at_0040 = [("catalogos", "0040_drop_autorizadores")]
    # TransactionTestCase vacia las tablas al terminar (flush); sin esto los
    # content types / catalogos sembrados se pierden y los tests de migracion
    # con serialized_rollback que corren despues fallan con UNIQUE
    # django_content_type. Mismo patron que test_folio_receta.
    serialized_rollback = True

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _table_exists(self):
        return "cat_autorizadores" in set(connection.introspection.table_names())

    def test_drop_forward_y_reverse_restaura_filas_sin_password(self):
        # 1. Volver al estado 0038 (revierte 0040 y 0039): la tabla legada reaparece vacia.
        executor = MigrationExecutor(connection)
        executor.migrate(self.at_0038)
        self.assertTrue(self._table_exists())

        old_apps = MigrationExecutor(connection).loader.project_state(self.at_0038).apps
        Autorizadores = old_apps.get_model("catalogos", "Autorizadores")
        # Solo Autorizadores se toma del estado historico (el modelo ya no existe
        # en el codigo); el resto usa los modelos vivos, cuyas tablas no cambian
        # entre 0038 y 0040.
        tipo = TpAutorizacion.objects.filter(code="CN").first() or TpAutorizacion.objects.create(
            code="CN", name="Cancelación de nota"
        )
        centros = [_center(100 + i) for i in (1, 2)]
        usuario = _user(100)
        for centro in centros:
            Autorizadores.objects.create(
                center_id=centro.id, name="rt_user", position="Director",
                authorization_type_id=tipo.id, authorizer_password="clave-legada", user_id=usuario.id_usuario,
            )

        # 2. Adelante hasta 0040: copia a designaciones y elimina la tabla.
        executor = MigrationExecutor(connection)
        executor.migrate(self.at_0040)
        self.assertFalse(self._table_exists())
        new_apps = MigrationExecutor(connection).loader.project_state(self.at_0040).apps
        Designacion = new_apps.get_model("catalogos", "DesignacionAutorizador")
        Alcance = new_apps.get_model("catalogos", "DesignacionAlcance")
        self.assertEqual(Designacion.objects.count(), 1)
        self.assertEqual(Alcance.objects.filter(scope_type="CENTRO").count(), 2)
        with self.assertRaises(LookupError):
            new_apps.get_model("catalogos", "Autorizadores")

        # 3. Reverse a 0038: tabla de vuelta, 2 filas (una por centro) SIN password.
        executor = MigrationExecutor(connection)
        executor.migrate(self.at_0038)
        self.assertTrue(self._table_exists())
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_centro_atencion, id_usuario, cargo, pwd_autorizador FROM cat_autorizadores ORDER BY id_autorizador")
            rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r[0] for r in rows}, {c.id for c in centros})
        self.assertTrue(all(r[1] == usuario.id_usuario and r[2] == "Director" for r in rows))
        self.assertTrue(all(r[3] == "" for r in rows), "el password legado NUNCA se restaura")
        reverted_apps = MigrationExecutor(connection).loader.project_state(self.at_0038).apps
        self.assertEqual(reverted_apps.get_model("catalogos", "DesignacionAutorizador").objects.count(), 0)
