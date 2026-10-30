"""
P-03 · Adscripción a consultorio familiar: permisos atómicos.

Mismo patrón que 0018: lectura y escritura se asignan a los roles que hoy
tienen recepcion:citas:write vigente (los que agendan en recepción). La
excepción, todos los centros y la configuración NO se asignan: los otorga el
administrador desde Administracion -> Roles. Idempotente (get_or_create).
"""
from django.db import migrations
from django.utils import timezone

ANCLA = "recepcion:citas:write"
PARA_RECEPCION = (
    ("recepcion:consultorio_familiar:read", "Ver la adscripción a consultorio familiar de los pacientes"),
    ("recepcion:consultorio_familiar:write", "Adscribir y reasignar pacientes a su consultorio familiar"),
)
SIN_ASIGNAR = (
    ("recepcion:consultorio_familiar:excepcion", "Atender en un consultorio distinto al familiar, con motivo"),
    ("recepcion:consultorio_familiar:todos_centros", "Adscribir pacientes de cualquier centro de atención"),
    ("admin:catalogos:consultorio_familiar:config", "Configurar equivalencias de clínica y consultorios familiares"),
)


def crear(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    RelRolPermiso = apps.get_model("administracion", "RelRolPermiso")

    # El estado historico de catalogos conserva los nombres de 0001.
    campos = {f.name for f in Permisos._meta.get_fields()}
    activo = "is_active" if "is_active" in campos else "est_activo"
    modificado = "updated_at" if "updated_at" in campos else "fch_modf"

    def permiso(codigo, descripcion):
        return Permisos.objects.get_or_create(
            codigo=codigo,
            defaults={"descripcion": descripcion, activo: True, "es_sistema": False, modificado: timezone.now()},
        )[0]

    roles = list(
        RelRolPermiso.objects.filter(id_permiso__codigo=ANCLA, fch_baja__isnull=True)
        .values_list("id_rol_id", flat=True).distinct()
    )
    for codigo, descripcion in PARA_RECEPCION:
        nuevo = permiso(codigo, descripcion)
        for id_rol in roles:
            RelRolPermiso.objects.get_or_create(
                id_rol_id=id_rol, id_permiso_id=nuevo.pk, defaults={"fch_baja": None},
            )
    for codigo, descripcion in SIN_ASIGNAR:
        permiso(codigo, descripcion)


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0018_permisos_recien_nacidos"),
        ("catalogos", "0045_parametro_anticipacion_checkin"),
    ]

    operations = [
        # Reversa sin efecto: no se borran asignaciones hechas después.
        migrations.RunPython(crear, migrations.RunPython.noop),
    ]
