"""
Baja de cat_autorizadores (change cancelacion-nota-cascada).

Estado: DeleteModel(Autorizadores). Base de datos: DROP TABLE IF EXISTS (la
tabla puede no existir en BD fresca porque 0013 ya no la crea).

Reverse: recrea la tabla con el modelo historico y restaura una fila por
cada alcance CENTRO de las designaciones copiadas en 0039
(id_autorizador_origen NOT NULL), con pwd_autorizador = '' (nunca se copio
ni se restaura ningun password). Los ids originales no se conservan.
"""
from django.db import migrations

LEGACY_TABLE = "cat_autorizadores"


def drop_autorizadores(apps, schema_editor):
    schema_editor.execute(
        "DROP TABLE IF EXISTS %s" % schema_editor.quote_name(LEGACY_TABLE)
    )


def recreate_autorizadores(apps, schema_editor):
    Autorizadores = apps.get_model("catalogos", "Autorizadores")
    if LEGACY_TABLE not in set(schema_editor.connection.introspection.table_names()):
        schema_editor.create_model(Autorizadores)

    Alcance = apps.get_model("catalogos", "DesignacionAlcance")
    scopes = (
        Alcance.objects.filter(
            scope_type="CENTRO",
            is_active=True,
            deleted_at__isnull=True,
            designation__origin_authorizer_id__isnull=False,
            designation__is_active=True,
            designation__deleted_at__isnull=True,
        )
        .select_related("designation", "designation__user")
        .order_by("pk")
    )
    for scope in scopes:
        designation = scope.designation
        Autorizadores.objects.create(
            center_id=scope.center_id,
            name=(designation.user.usuario or "")[:100],
            position=designation.position,
            authorization_type_id=designation.authorization_type_id,
            signature_image=designation.signature_image,
            authorizer_password="",
            user_id=designation.user_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0039_copy_autorizadores_a_designaciones"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="Autorizadores"),
            ],
            database_operations=[
                migrations.RunPython(drop_autorizadores, recreate_autorizadores),
            ],
        ),
    ]
