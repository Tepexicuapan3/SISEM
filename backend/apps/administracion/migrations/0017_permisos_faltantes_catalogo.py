"""
Alta de los permisos que el backend YA exige pero que no existian como fila en
`cat_permisos` (auditoria engram `sires/missing-permissions-audit`, plan
aprobado `sires/missing-permissions-plan`).

Sin la fila, la matriz de roles no puede otorgar el codigo y solo el rol
comodin ("*") podia usar la funcionalidad.

- NO asigna ningun permiso a ningun rol (admin es comodin; el resto via matriz).
- Enlaza (ModuloPermiso) los `:read` cuyo modulo de menu existe, para que el
  menu respete el permiso. Si el modulo no existe, se omite en silencio.
- NO crea codigos solo-frontend (placeholders) ni codigos solo-e2e.
- Idempotente (get_or_create) y reversible: al revertir solo se borran los
  codigos de esta migracion que NO esten referenciados por ningun rol/override
  (si ya se asignaron, se conservan).
"""
from django.db import migrations
from django.utils import timezone

# --------------------------------------------------------------------------
# Catalogos dinamicos: f"admin:catalogos:{catalogo}:{accion}"
# (catalogos.permissions.CatalogPermissionMixin: GET=read, POST=create,
#  PUT/PATCH=update, DELETE=delete).
# --------------------------------------------------------------------------

_ACCIONES = {
    "read": "Ver catalogo de {}",
    "create": "Crear en catalogo de {}",
    "update": "Editar catalogo de {}",
    "delete": "Eliminar en catalogo de {}",
}
_TODAS = ("read", "create", "update", "delete")

# Catalogos que ya tienen `:read` en BD pero les faltan create/update/delete.
# {clave_catalogo: etiqueta}
CATALOGOS_SOLO_ESCRITURA = {
    "areas": "areas",
    "areas_clinicas": "areas clinicas",
    "centro_area_clinica": "areas clinicas por centro de atencion",
    "centros_atencion": "centros de atencion",
    "cies": "CIE-S",
    "consultorios": "consultorios",
    "edo_civil": "estado civil",
    "escolaridad": "escolaridad",
    "escuelas": "escuelas",
    "especialidades": "especialidades",
    "tipo_consulta": "tipos de consulta",
    "tipos_areas": "tipos de areas",
    "turnos": "turnos",
    "vacunas": "vacunas (administrativo)",
}

# Catalogos sin NINGUN codigo en BD: read + create + update + delete.
CATALOGOS_COMPLETOS = {
    "cie9_mc": "CIE-9-MC (procedimientos, NOM-024)",
    "medicamentos": "medicamentos",
    "motivos_cita": "motivos de cita",
    "centros_atencion_horarios": "horarios de centros de atencion",
    "centros_atencion_excepciones": "excepciones de horario de centros de atencion",
}

# Drift de seed: estan en catalogos_crud_permissions_seed pero nunca se
# aplicaron en BD. Mismas descripciones que el seed.
CATALOGOS_DRIFT_SEED = {
    "tipos_cirugia": "tipos de cirugia",
    "clasificaciones_cirugia": "clasificaciones de cirugia",
    "motivos_cancelacion_cirugia": "motivos de cancelacion de cirugia",
    "motivos_cancelacion_nota": "motivos de cancelacion de nota",
    "motivos_baja_padron": "motivos de baja de padron",
    "motivos_traslado": "motivos de traslado en ambulancia",
    "tipos_traslado": "tipos de traslado en ambulancia",
    "tipos_servicio_ambulancia": "tipos de servicio de ambulancia",
    "destinos_ambulancia": "destinos de ambulancia",
}

# Catalogo de roles (RolesListCreateView: solo ListCreate -> read y create).
CATALOGO_ROLES = {
    "admin:catalogos:roles:read": "Ver catalogo de roles",
    "admin:catalogos:roles:create": "Crear en catalogo de roles",
}


def _catalogo(clave, etiqueta, acciones):
    return [
        (f"admin:catalogos:{clave}:{a}", _ACCIONES[a].format(etiqueta))
        for a in acciones
    ]


def _armar_catalogos():
    out = []
    for clave, etiqueta in CATALOGOS_SOLO_ESCRITURA.items():
        out += _catalogo(clave, etiqueta, ("create", "update", "delete"))
    for clave, etiqueta in CATALOGOS_COMPLETOS.items():
        out += _catalogo(clave, etiqueta, _TODAS)
    for clave, etiqueta in CATALOGOS_DRIFT_SEED.items():
        out += _catalogo(clave, etiqueta, _TODAS)
    out += list(CATALOGO_ROLES.items())
    return out


PERMISOS_CATALOGOS = _armar_catalogos()

# --------------------------------------------------------------------------
# RBAC (administracion/views/rbac_*.py) -- solo existian en seed_e2e.
# --------------------------------------------------------------------------
PERMISOS_RBAC = [
    ("admin:gestion:usuarios:create", "Crear usuarios del sistema"),
    ("admin:gestion:usuarios:update", "Editar usuarios del sistema (roles, estatus, overrides)"),
    ("admin:gestion:roles:create", "Crear roles del sistema"),
    ("admin:gestion:roles:update", "Editar roles y sus permisos"),
    ("admin:gestion:roles:delete", "Eliminar roles del sistema"),
    ("admin:gestion:permisos:read", "Ver catalogo de permisos del sistema"),
]

# --------------------------------------------------------------------------
# Operativos sueltos exigidos por el backend.
# --------------------------------------------------------------------------
PERMISOS_OPERATIVOS = [
    ("farmacia:recetas:dispensar", "Dispensar recetas en farmacia"),
    ("recepcion:citas:read", "Ver citas medicas en recepcion"),
    ("recepcion:citas:write", "Agendar, modificar y cancelar citas medicas en recepcion"),
    ("admin:ops:observability:read", "Ver observabilidad operativa del sistema"),
    # FarmaciaCatalogPermissionMixin (farmacia/views.py), catalog="vacunas".
    ("farmacia:vacunas:create", "Registrar lotes en inventario operativo de vacunas"),
    ("farmacia:vacunas:update", "Editar inventario operativo de vacunas"),
    ("farmacia:vacunas:delete", "Eliminar lotes del inventario operativo de vacunas"),
]

TODOS_LOS_PERMISOS = PERMISOS_RBAC + PERMISOS_OPERATIVOS + PERMISOS_CATALOGOS

# --------------------------------------------------------------------------
# Enlaces modulo -> permiso (solo `:read` con modulo de menu en
# navigation_seed.py). {clave_modulo: codigo_permiso}
# --------------------------------------------------------------------------
ENLACES_MODULO = {
    f"administracion.catalogos.{c}": f"admin:catalogos:{c}:read"
    for c in ("cie9_mc", *CATALOGOS_DRIFT_SEED)
}


def _campos(modelo):
    nombres = {f.name for f in modelo._meta.get_fields()}
    activo = "is_active" if "is_active" in nombres else "est_activo"
    modificado = "updated_at" if "updated_at" in nombres else "fch_modf"
    return activo, modificado


def crear(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    Modulo = apps.get_model("administracion", "Modulo")
    ModuloPermiso = apps.get_model("administracion", "ModuloPermiso")

    # El estado historico de catalogos conserva los nombres de 0001
    # (est_activo, fch_modf); el modelo actual los llama is_active/updated_at.
    activo, modificado = _campos(Permisos)
    ahora = timezone.now()
    for codigo, descripcion in TODOS_LOS_PERMISOS:
        Permisos.objects.get_or_create(
            codigo=codigo,
            defaults={
                "descripcion": descripcion,
                activo: True,
                "es_sistema": False,
                modificado: ahora,
            },
        )

    for clave, codigo in ENLACES_MODULO.items():
        modulo = Modulo.objects.filter(clave=clave).first()
        permiso = Permisos.objects.filter(codigo=codigo).first()
        if modulo is None or permiso is None:
            continue
        ModuloPermiso.objects.get_or_create(id_modulo=modulo, id_permiso=permiso)


def revertir(apps, schema_editor):
    Permisos = apps.get_model("catalogos", "Permisos")
    ModuloPermiso = apps.get_model("administracion", "ModuloPermiso")

    codigos = [c for c, _ in TODOS_LOS_PERMISOS]
    # Solo se borran los que nadie referencia (rol, override, etc.), para no
    # destruir asignaciones hechas despues. Los enlaces de menu se quitan antes
    # (FK PROTECT).
    # Al revertir, Django puede renderizar la clase historica de Permisos mas
    # de una vez: filtrar por instancia o comparar clases con "is" falla
    # ("Must be Permisos instance"). Se compara por label y se filtra por pk.
    relaciones = [
        r for r in Permisos._meta.related_objects
        if r.related_model._meta.label != ModuloPermiso._meta.label
    ]
    for permiso in Permisos.objects.filter(codigo__in=codigos):
        if any(
            r.related_model._default_manager.filter(**{r.field.attname: permiso.pk}).exists()
            for r in relaciones
        ):
            continue
        ModuloPermiso.objects.filter(id_permiso_id=permiso.pk).delete()
        # Sin permiso.delete(): su cascada vuelve a filtrar relacionados por
        # instancia (mismo error). Ya se verifico arriba que nadie lo referencia.
        schema_editor.execute(
            f"DELETE FROM {schema_editor.quote_name(Permisos._meta.db_table)} "
            f"WHERE {schema_editor.quote_name(Permisos._meta.pk.column)} = %s",
            [permiso.pk],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0016_permiso_credenciales_usuarios"),
        ("catalogos", "0044_motivo_baja_padron"),
    ]

    operations = [
        migrations.RunPython(crear, revertir),
    ]
