"""
Plan identidad del paciente, bloque C: permisos para registrar recien
nacidos provisionales y para vincular registros de la misma persona. Se
asignan a los roles que hoy tienen admin:gestion:expedientes:update vigente
(los que operan la pantalla de expedientes); despues el administrador los
ajusta desde Administracion -> Roles. Tambien en navigation_permissions_seed.
"""
from django.db import migrations
from django.utils import timezone

ACTUALIZAR = "admin:gestion:expedientes:update"
NUEVOS = (
    ("admin:gestion:expedientes:recien_nacidos", "Registrar recien nacidos provisionales (sin registro en SERMED)"),
    ("admin:gestion:expedientes:vincular", "Vincular registros de la misma persona (recien nacido con SERMED)"),
)


def asignar(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")

    # El estado historico de catalogos conserva los nombres de 0001.
    campos = {f.name for f in Permisos._meta.get_fields()}
    activo = "is_active" if "is_active" in campos else "est_activo"
    modificado = "updated_at" if "updated_at" in campos else "fch_modf"

    roles = list(
        RelRolPermiso.objects.filter(id_permiso__codigo=ACTUALIZAR, fch_baja__isnull=True)
        .values_list("id_rol_id", flat=True).distinct()
    )
    for codigo, descripcion in NUEVOS:
        permiso, _ = Permisos.objects.get_or_create(
            codigo=codigo,
            defaults={"descripcion": descripcion, activo: True, "es_sistema": False, modificado: timezone.now()},
        )
        for id_rol in roles:
            RelRolPermiso.objects.get_or_create(
                id_rol_id=id_rol, id_permiso_id=permiso.pk, defaults={"fch_baja": None},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0017_permisos_faltantes_catalogo"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [
        # Reversa sin efecto: no se borran asignaciones hechas despues.
        migrations.RunPython(asignar, migrations.RunPython.noop),
    ]
