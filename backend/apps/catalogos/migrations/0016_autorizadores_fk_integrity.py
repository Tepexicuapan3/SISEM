# Autorizadores.center_id / .authorization_type_id / .user_id vivian como
# enteros sueltos (BigIntegerField) aunque los tres apuntan a catalogos ya
# existentes (CatCentroAtencion, TpAutorizacion, authentication.SyUsuario) --
# sin FK real no habia integridad referencial ni proteccion contra borrar un
# centro/tipo/usuario que todavia tuviera autorizadores asociados.
#
# db_column se mantiene identico en los tres casos, asi que el RenameField
# (mismo tipo, solo cambia el nombre Python) no genera SQL de renombrado de
# columna. El AlterField que sigue es el que agrega la constraint FK real,
# sin tocar los valores ya cargados en la columna -- si existiera algun id
# huerfano, Postgres rechaza la migracion en vez de aplicarla a medias.
#
# BUG DE DB 100% FRESCA (defensivo agregado despues, ver `add_fk_integrity`):
# la migracion 0013 (crear_tablas_faltantes) usa el registro de apps VIVO
# (django.apps.apps) en vez del "apps" historico que Django inyecta a todo
# RunPython. En una base creada de cero, eso hace que cat_autorizadores nazca
# ya con el modelo ACTUAL (center/authorization_type/user como ForeignKey),
# incluyendo la FK constraint y el indice implicito que Django agrega por
# cada ForeignKey (db_index=True por default). Cuando esta migracion (0016)
# corre despues e intenta agregar esa misma FK + indice via AlterField
# normal, Postgres rechaza la creacion duplicada.
#
# En cualquier entorno con historial incremental real (dev/produccion
# actuales), cat_autorizadores YA EXISTIA como tabla legada con columnas
# enteras sueltas ANTES de que corriera 0013 (que la salta via
# "if tabla in tablas_existentes: continue"), asi que en esos entornos la
# FK/indice NUNCA existen todavia en este punto y se crean normalmente -- el
# camino defensivo de abajo no cambia el comportamiento ahi, solo evita el
# choque en el escenario de DB fresca (disaster recovery, CI, onboarding).
# No se toca 0013 (ya aplicada en todos los entornos reales; editar
# historial ya shippeado es mas riesgoso que dejarlo como esta).
#
# PENDIENTE DE VERIFICAR: este fix se escribio y revisó solo por analisis
# estatico + `makemigrations --check --dry-run` + la suite de tests de
# catalogos corriendo sobre sqlite (manage.py test) -- sqlite no reproduce
# el bug original (es especifico de constraints/indices de Postgres), asi
# que esto NO confirma el fix contra Postgres real. Para confirmarlo del
# todo, correr contra una Postgres de prueba vacia (nunca contra la DB
# compartida de DEV):
#     python manage.py migrate catalogos
import django.db.models.deletion
from django.db import migrations, models

AUTORIZADORES_TABLE = "cat_autorizadores"

# (db_column, tabla referenciada, columna referenciada)
AUTORIZADORES_FK_COLUMNS = [
    ("id_centro_atencion", "cat_centros_atencion", "id_centro_atencion"),
    ("id_tpautorizacion", "cat_tpautorizacion", "id_tpautorizacion"),
    ("id_usuario", "sy_usuarios", "id_usuario"),
]


def _fk_exists(constraints, column):
    return any(
        info.get("foreign_key") and info.get("columns") == [column]
        for info in constraints.values()
    )


def _index_exists(constraints, column):
    return any(
        info.get("index") and not info.get("foreign_key") and info.get("columns") == [column]
        for info in constraints.values()
    )


def add_fk_integrity(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor != "postgresql":
        # El bug de duplicado es especifico de Postgres (ver comentario de
        # cabecera). En otros vendors (sqlite, usado por manage.py test) el
        # tipo de columna no cambia (sigue siendo entero) y la integridad de
        # PROTECT se aplica a nivel Django (senal pre_delete en el ORM), no
        # a nivel DB -- no hay nada fisico que agregar de forma segura y
        # portable aca.
        return

    table = AUTORIZADORES_TABLE
    qn = schema_editor.quote_name

    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)

        for column, ref_table, ref_column in AUTORIZADORES_FK_COLUMNS:
            if not _index_exists(constraints, column):
                index_name = f"{table}_{column}_idx"
                cursor.execute(
                    f'CREATE INDEX IF NOT EXISTS {qn(index_name)} '
                    f'ON {qn(table)} ({qn(column)});'
                )

            if not _fk_exists(constraints, column):
                fk_name = f"{table}_{column}_fk"
                cursor.execute(
                    f'ALTER TABLE {qn(table)} ADD CONSTRAINT {qn(fk_name)} '
                    f'FOREIGN KEY ({qn(column)}) REFERENCES {qn(ref_table)} ({qn(ref_column)});'
                )


def remove_fk_integrity_noop(apps, schema_editor):
    # No revertimos la parte fisica: si la FK/indice ya existian de antes
    # (creados por 0013 en DB fresca) no nos corresponde tocarlos al bajar
    # esta migracion, y si los creamos nosotros, borrarlos a mano en reversa
    # arriesga mas de lo que vale. Si alguna vez se necesita revertir 0016
    # de verdad, hacerlo manualmente contra el entorno puntual.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0015_reconcile_catcentroatencion_drift"),
        ("authentication", "0011_sesionusuario"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="autorizadores",
                    old_name="center_id",
                    new_name="center",
                ),
                migrations.RenameField(
                    model_name="autorizadores",
                    old_name="authorization_type_id",
                    new_name="authorization_type",
                ),
                migrations.RenameField(
                    model_name="autorizadores",
                    old_name="user_id",
                    new_name="user",
                ),
                migrations.AlterField(
                    model_name="autorizadores",
                    name="center",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="catalogos.catcentroatencion",
                        db_column="id_centro_atencion",
                        related_name="autorizadores",
                    ),
                ),
                migrations.AlterField(
                    model_name="autorizadores",
                    name="authorization_type",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="catalogos.tpautorizacion",
                        db_column="id_tpautorizacion",
                        related_name="autorizadores",
                    ),
                ),
                migrations.AlterField(
                    model_name="autorizadores",
                    name="user",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="authentication.syusuario",
                        db_column="id_usuario",
                        related_name="autorizaciones",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_fk_integrity, remove_fk_integrity_noop),
            ],
        ),
    ]
