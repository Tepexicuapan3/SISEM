from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.db import connection, transaction
from django.utils import timezone

from apps.administracion.models import RelRolPermiso, RelUsuarioOverride, RelUsuarioRol
from apps.authentication.models import DetUsuario, SyUsuario
from apps.catalogos.models import Areas, CatCentroAtencion, Permisos, Roles, TiposAreas
from apps.recepcion.models import Visit

DEFAULT_PASSWORD = "Sisem_123456"

REQUIRED_TABLES = {
    "sy_usuarios",
    "det_usuarios",
    "cat_roles",
    "cat_permisos",
    "cat_centros_atencion",
    "rel_usuario_roles",
    "rel_rol_permisos",
    "rel_usuario_overrides",
}


def _build_schedule(
    morning_starts,
    morning_ends,
    afternoon_starts,
    afternoon_ends,
    night_starts,
    night_ends,
):
    return {
        "morning": {"startsAt": morning_starts, "endsAt": morning_ends},
        "afternoon": {"startsAt": afternoon_starts, "endsAt": afternoon_ends},
        "night": {"startsAt": night_starts, "endsAt": night_ends},
    }


PERMISSIONS = [
    ("admin:gestion:usuarios:read", "Admin - Ver usuarios y perfiles"),
    ("admin:gestion:usuarios:create", "Admin - Crear usuarios"),
    ("admin:gestion:usuarios:update", "Admin - Editar usuarios"),
    ("admin:gestion:usuarios:delete", "Admin - Eliminar usuarios"),
    ("admin:gestion:medicos:read",        "Admin - Ver catalogo de medicos"),
    ("admin:gestion:medicos:create",      "Admin - Registrar medico desde usuario"),
    ("admin:gestion:medicos:update",      "Admin - Editar perfil medico"),
    ("admin:gestion:medicos:horarios",    "Admin - Gestionar horarios y consultorios"),
    ("admin:gestion:medicos:excepciones", "Admin - Registrar excepciones del medico"),
    ("admin:gestion:medicos:coberturas",  "Admin - Registrar coberturas entre medicos"),
    ("admin:gestion:expedientes:read", "Admin - Ver expedientes"),
    ("admin:gestion:roles:read", "Admin - Ver roles"),
    ("admin:gestion:roles:create", "Admin - Crear roles"),
    ("admin:gestion:roles:update", "Admin - Editar roles"),
    ("admin:gestion:roles:delete", "Admin - Eliminar roles"),
    ("admin:gestion:permisos:read", "Admin - Ver catalogo de permisos"),
    (
        "admin:catalogos:centros_atencion:read",
        "Admin - Ver centros de atencion",
    ),
    (
        "admin:catalogos:centros_atencion:create",
        "Admin - Crear centros de atencion",
    ),
    (
        "admin:catalogos:centros_atencion:update",
        "Admin - Editar centros de atencion",
    ),
    (
        "admin:catalogos:centros_atencion:delete",
        "Admin - Eliminar centros de atencion",
    ),
    ("admin:catalogos:areas:read", "Admin - Ver areas"),
    ("admin:catalogos:areas:create", "Admin - Crear areas"),
    ("admin:catalogos:areas:update", "Admin - Editar areas"),
    ("admin:catalogos:areas:delete", "Admin - Eliminar areas"),
    ("admin:catalogos:vacunas:read", "Admin - Ver catalogo de vacunas"),
    ("admin:catalogos:vacunas:create", "Admin - Crear vacunas"),
    ("admin:catalogos:vacunas:update", "Admin - Editar vacunas"),
    ("admin:catalogos:vacunas:delete", "Admin - Eliminar vacunas"),
    ("admin:catalogos:areas_clinicas:read", "Admin - Ver areas clinicas"),
    ("admin:catalogos:areas_clinicas:create", "Admin - Crear areas clinicas"),
    ("admin:catalogos:areas_clinicas:update", "Admin - Editar areas clinicas"),
    ("admin:catalogos:areas_clinicas:delete", "Admin - Eliminar areas clinicas"),
    ("admin:catalogos:centro_area_clinica:read", "Admin - Ver areas clinicas por centro"),
    ("admin:catalogos:centro_area_clinica:create", "Admin - Asignar area clinica a centro"),
    ("admin:catalogos:centro_area_clinica:update", "Admin - Editar area clinica por centro"),
    ("admin:catalogos:centro_area_clinica:delete", "Admin - Eliminar area clinica de centro"),
    ("admin:catalogos:especialidades:read", "Admin - Ver especialidades"),
    ("admin:catalogos:especialidades:create", "Admin - Crear especialidades"),
    ("admin:catalogos:especialidades:update", "Admin - Editar especialidades"),
    ("admin:catalogos:especialidades:delete", "Admin - Eliminar especialidades"),
    ("admin:reportes:read", "Admin - Ver reportes"),
    ("admin:estadisticas:read", "Admin - Ver estadisticas"),
    ("admin:autorizacion:estudios:read", "Admin - Autorizacion estudios"),
    ("admin:licencias:read", "Admin - Licencias"),
    ("admin:conciliacion:read", "Admin - Conciliacion"),
    ("clinico:consultas:read", "Clinico - Ver consultas"),
    ("clinico:consultas:agenda:read", "Clinico - Ver agenda"),
    ("clinico:consultas:create", "Clinico - Crear consulta"),
    ("clinico:consultas:historial:read", "Clinico - Ver historial"),
    ("clinico:expedientes:read", "Clinico - Ver expedientes"),
    ("clinico:expedientes:create", "Clinico - Crear expediente"),
    ("clinico:somatometria:read", "Clinico - Ver somatometria"),
    ("clinico:somatometria:update", "Clinico - Corregir somatometria"),
    (
        "recepcion:fichas:medicina_general:read",
        "Recepcion - Ver ficha medicina general",
    ),
    (
        "recepcion:fichas:medicina_general:create",
        "Recepcion - Ficha medicina general",
    ),
    (
        "recepcion:fichas:especialidad:read",
        "Recepcion - Ver ficha especialidad",
    ),
    (
        "recepcion:fichas:especialidad:create",
        "Recepcion - Ficha especialidad",
    ),
    ("recepcion:fichas:urgencias:read", "Recepcion - Ver ficha urgencias"),
    ("recepcion:fichas:urgencias:create", "Recepcion - Ficha urgencias"),
    ("recepcion:incapacidad:read",     "Recepcion - Ver historial de incapacidades"),
    ("recepcion:citas:read",           "Recepcion - Ver citas médicas"),
    ("recepcion:citas:write",          "Recepcion - Agendar y gestionar citas"),
    ("farmacia:recetas:dispensar", "Farmacia - Dispensar recetas"),
    ("farmacia:inventario:update", "Farmacia - Actualizar inventario"),
    ("farmacia:vacunas:read", "Farmacia - Ver inventario de vacunas"),
    ("farmacia:vacunas:create", "Farmacia - Registrar inventario de vacunas"),
    ("farmacia:vacunas:update", "Farmacia - Actualizar inventario de vacunas"),
    ("farmacia:vacunas:delete", "Farmacia - Dar de baja inventario de vacunas"),
    ("urgencias:triage:read", "Urgencias - Ver triage"),
    ("comunicados:anuncios:read", "Comunicados - Ver anuncios del portal de citas"),
    ("comunicados:anuncios:create", "Comunicados - Crear anuncios del portal de citas"),
    ("comunicados:anuncios:update", "Comunicados - Editar anuncios del portal de citas"),
    ("comunicados:anuncios:delete", "Comunicados - Eliminar anuncios del portal de citas"),
]


ROLE_DEFS = [
    {
        "code": "ADMIN",
        "desc": "Administrador",
        "landing": "/admin/roles",
        "is_admin": True,
        "is_system": True,
        "perms": [],
    },
    {
        "code": "ADMIN_USUARIOS",
        "desc": "Admin Usuarios",
        "landing": "/admin/usuarios",
        "perms": [
            "admin:gestion:usuarios:read",
            "admin:gestion:usuarios:create",
            "admin:gestion:usuarios:update",
            "admin:gestion:usuarios:delete",
        ],
    },
    {
        "code": "ADMIN_EXPEDIENTES",
        "desc": "Admin Expedientes",
        "landing": "/admin/expedientes",
        "perms": ["admin:gestion:expedientes:read"],
    },
    {
        "code": "ADMIN_ROLES",
        "desc": "Admin Roles",
        "landing": "/admin/roles",
        "perms": [
            "admin:gestion:roles:read",
            "admin:gestion:roles:create",
            "admin:gestion:roles:update",
            "admin:gestion:roles:delete",
            "admin:gestion:permisos:read",
        ],
    },
    {
        "code": "ADMIN_CATALOGOS",
        "desc": "Admin Catalogos",
        "landing": "/admin/catalogos",
        "perms": [
            "admin:catalogos:centros_atencion:read",
            "admin:catalogos:centros_atencion:create",
            "admin:catalogos:centros_atencion:update",
            "admin:catalogos:centros_atencion:delete",
            "admin:catalogos:areas:read",
            "admin:catalogos:areas:create",
            "admin:catalogos:areas:update",
            "admin:catalogos:areas:delete",
            "admin:catalogos:vacunas:read",
            "admin:catalogos:vacunas:create",
            "admin:catalogos:vacunas:update",
            "admin:catalogos:vacunas:delete",
            "admin:catalogos:areas_clinicas:read",
            "admin:catalogos:areas_clinicas:create",
            "admin:catalogos:areas_clinicas:update",
            "admin:catalogos:areas_clinicas:delete",
            "admin:catalogos:centro_area_clinica:read",
            "admin:catalogos:centro_area_clinica:create",
            "admin:catalogos:centro_area_clinica:update",
            "admin:catalogos:centro_area_clinica:delete",
            "admin:catalogos:especialidades:read",
            "admin:catalogos:especialidades:create",
            "admin:catalogos:especialidades:update",
            "admin:catalogos:especialidades:delete",
        ],
    },
    {
        "code": "ADMIN_COMUNICADOS",
        "desc": "Admin Comunicados",
        "landing": "/comunicados/anuncios",
        "perms": [
            "comunicados:anuncios:read",
            "comunicados:anuncios:create",
            "comunicados:anuncios:update",
            "comunicados:anuncios:delete",
        ],
    },
    {
        "code": "ADMIN_REPORTES",
        "desc": "Admin Reportes",
        "landing": "/admin/reportes",
        "perms": ["admin:reportes:read"],
    },
    {
        "code": "ADMIN_ESTADISTICAS",
        "desc": "Admin Estadisticas",
        "landing": "/admin/estadisticas",
        "perms": ["admin:estadisticas:read"],
    },
    {
        "code": "ADMIN_AUTORIZACION",
        "desc": "Admin Autorizacion",
        "landing": "/admin/autorizacion/estudios",
        "perms": [
            "admin:autorizacion:estudios:read",
        ],
    },
    {
        "code": "ADMIN_LICENCIAS",
        "desc": "Admin Licencias",
        "landing": "/admin/licencias",
        "perms": ["admin:licencias:read"],
    },
    {
        "code": "ADMIN_CONCILIACION",
        "desc": "Admin Conciliacion",
        "landing": "/admin/conciliacion",
        "perms": ["admin:conciliacion:read"],
    },
    {
        "code": "ADMIN_SOLO_LECTURA",
        "desc": "Admin Solo Lectura",
        "landing": "/admin/usuarios",
        "perms": [
            "admin:gestion:usuarios:read",
            "admin:gestion:roles:read",
            "admin:gestion:permisos:read",
            "admin:catalogos:centros_atencion:read",
            "admin:catalogos:areas:read",
            "admin:catalogos:vacunas:read",
            "admin:catalogos:areas_clinicas:read",
            "admin:catalogos:especialidades:read",
            "admin:reportes:read",
        ],
    },
    {
        "code": "SISTEMA_AUDITORIA",
        "desc": "Sistema Auditoria",
        "landing": "/admin/reportes",
        "is_system": True,
        "perms": [
            "admin:reportes:read",
            "admin:gestion:usuarios:read",
        ],
    },
    {
        "code": "ROL_INACTIVO_PRUEBA",
        "desc": "Rol inactivo para pruebas",
        "landing": "/admin/roles",
        "is_active": False,
        "perms": [
            "admin:gestion:roles:read",
            "admin:gestion:permisos:read",
        ],
    },
    {
        "code": "CLINICO",
        "desc": "Clinico",
        "landing": "/clinico/consultas",
        "perms": [
            "clinico:consultas:read",
            "clinico:consultas:agenda:read",
            "clinico:consultas:create",
            "clinico:consultas:historial:read",
            "clinico:expedientes:read",
            "clinico:expedientes:create",
            "clinico:somatometria:read",
            "clinico:somatometria:update",
        ],
    },
    {
        "code": "RECEPCION",
        "desc": "Recepcion",
        "landing": "/recepcion/fichas/medicina-general",
        "perms": [
            "recepcion:fichas:medicina_general:read",
            "recepcion:fichas:medicina_general:create",
            "recepcion:fichas:especialidad:read",
            "recepcion:fichas:especialidad:create",
            "recepcion:fichas:urgencias:read",
            "recepcion:fichas:urgencias:create",
            "recepcion:incapacidad:read",
            "recepcion:citas:read",
            "recepcion:citas:write",
        ],
    },
    {
        "code": "FARMACIA",
        "desc": "Farmacia",
        "landing": "/farmacia/recetas",
        "perms": [
            "farmacia:recetas:dispensar",
            "farmacia:inventario:update",
            "farmacia:vacunas:read",
            "farmacia:vacunas:create",
            "farmacia:vacunas:update",
            "farmacia:vacunas:delete",
        ],
    },
    {
        "code": "URGENCIAS",
        "desc": "Urgencias",
        "landing": "/urgencias/triage",
        "perms": ["urgencias:triage:read"],
    },
]


CENTER_DEFS = [
    {
        "code": "CA-001",
        "name": "Centro de Atencion Local",
        "is_external": False,
        "is_active": True,
        "address": "Av. Demo 123, CDMX",
        "schedule": _build_schedule(
            "07:00", "14:00", "14:00", "20:00", "20:00", "23:00"
        ),
    },
    {
        "code": "HGR-002",
        "name": "Hospital General Reforma",
        "is_external": False,
        "is_active": True,
        "address": "Av. Reforma 240, CDMX",
        "schedule": _build_schedule(
            "06:00", "13:00", "13:00", "19:00", "19:00", "23:00"
        ),
    },
    {
        "code": "CLI-003",
        "name": "Clinica Familiar Norte",
        "is_external": False,
        "is_active": True,
        "address": "Calle Cedro 55, CDMX",
        "schedule": _build_schedule(
            "08:00", "15:00", "15:00", "21:00", "21:00", "23:30"
        ),
    },
    {
        "code": "SAN-004",
        "name": "Sanatorio del Sur",
        "is_external": True,
        "is_active": True,
        "address": "Av. Division del Norte 1200, CDMX",
        "schedule": _build_schedule(
            "07:00", "13:00", "13:00", "19:00", "19:00", "22:00"
        ),
    },
    {
        "code": "UMO-005",
        "name": "Unidad Movil Oriente",
        "is_external": True,
        "is_active": True,
        "address": "Calz. Zaragoza 3500, CDMX",
        "schedule": _build_schedule(
            "09:00", "14:00", "14:00", "18:00", "18:00", "21:00"
        ),
    },
    {
        "code": "URG-006",
        "name": "Centro de Urgencias Central",
        "is_external": False,
        "is_active": True,
        "address": "Eje Central 900, CDMX",
        "schedule": _build_schedule(
            "00:00", "07:59", "08:00", "15:59", "16:00", "23:59"
        ),
    },
    {
        "code": "ARC-007",
        "name": "Centro Archivado Poniente",
        "is_external": False,
        "is_active": False,
        "address": "Av. Constituyentes 1500, CDMX",
        "schedule": _build_schedule(
            "07:00", "14:00", "14:00", "20:00", "20:00", "23:00"
        ),
    },
]


AREA_TYPE_DEFS = [
    {
        "key": "ASISTENCIAL",
        "name": "Asistencial",
        "is_active": True,
        "fallback_code": 10,
    },
    {
        "key": "ADMINISTRATIVA",
        "name": "Administrativa",
        "is_active": True,
        "fallback_code": 20,
    },
    {
        "key": "DIAGNOSTICO",
        "name": "Diagnostico",
        "is_active": True,
        "fallback_code": 30,
    },
    {
        "key": "SOPORTE",
        "name": "Soporte",
        "is_active": True,
        "fallback_code": 40,
    },
]


AREA_DEFS = [
    {"name": "Urgencias Adulto", "type_key": "ASISTENCIAL", "is_active": True},
    {"name": "Consulta Externa", "type_key": "ASISTENCIAL", "is_active": True},
    {"name": "Triage", "type_key": "ASISTENCIAL", "is_active": True},
    {"name": "Farmacia Hospitalaria", "type_key": "SOPORTE", "is_active": True},
    {"name": "Archivo Clinico", "type_key": "ADMINISTRATIVA", "is_active": True},
    {"name": "Trabajo Social", "type_key": "ADMINISTRATIVA", "is_active": True},
    {"name": "Laboratorio Clinico", "type_key": "DIAGNOSTICO", "is_active": True},
    {"name": "Imagenologia", "type_key": "DIAGNOSTICO", "is_active": True},
    {
        "name": "Area Inactiva de Prueba",
        "type_key": "ADMINISTRATIVA",
        "is_active": False,
    },
]


USER_DEFS = [
    {
        "username": "admin",
        "email": "admin@sisem.local",
        "full_name": "Admin Sistema",
        "role": "ADMIN",
        "center_code": "CA-001",
    },
    {
        "username": "admin_usuarios",
        "email": "admin.usuarios@sisem.local",
        "full_name": "Admin Usuarios",
        "role": "ADMIN_USUARIOS",
        "center_code": "HGR-002",
    },
    {
        "username": "admin_expedientes",
        "email": "admin.expedientes@sisem.local",
        "full_name": "Admin Expedientes",
        "role": "ADMIN_EXPEDIENTES",
        "center_code": "CLI-003",
    },
    {
        "username": "admin_roles",
        "email": "admin.roles@sisem.local",
        "full_name": "Admin Roles",
        "role": "ADMIN_ROLES",
        "center_code": "CA-001",
    },
    {
        "username": "admin_catalogos",
        "email": "admin.catalogos@sisem.local",
        "full_name": "Admin Catalogos",
        "role": "ADMIN_CATALOGOS",
        "center_code": "SAN-004",
    },
    {
        "username": "admin_reportes",
        "email": "admin.reportes@sisem.local",
        "full_name": "Admin Reportes",
        "role": "ADMIN_REPORTES",
        "center_code": "CA-001",
    },
    {
        "username": "admin_estadisticas",
        "email": "admin.estadisticas@sisem.local",
        "full_name": "Admin Estadisticas",
        "role": "ADMIN_ESTADISTICAS",
        "center_code": "UMO-005",
    },
    {
        "username": "admin_autorizacion",
        "email": "admin.autorizacion@sisem.local",
        "full_name": "Admin Autorizacion",
        "role": "ADMIN_AUTORIZACION",
        "center_code": "URG-006",
    },
    {
        "username": "admin_licencias",
        "email": "admin.licencias@sisem.local",
        "full_name": "Admin Licencias",
        "role": "ADMIN_LICENCIAS",
        "center_code": "HGR-002",
    },
    {
        "username": "admin_conciliacion",
        "email": "admin.conciliacion@sisem.local",
        "full_name": "Admin Conciliacion",
        "role": "ADMIN_CONCILIACION",
        "center_code": "CLI-003",
    },
    {
        "username": "admin_lectura",
        "email": "admin.lectura@sisem.local",
        "full_name": "Admin Lectura",
        "role": "ADMIN_SOLO_LECTURA",
        "center_code": "CA-001",
    },
    {
        "username": "auditor_sistema",
        "email": "auditor.sistema@sisem.local",
        "full_name": "Auditor Sistema",
        "role": "SISTEMA_AUDITORIA",
        "center_code": "CA-001",
    },
    {
        "username": "clinico",
        "email": "clinico@sisem.local",
        "full_name": "Clinico Demo",
        "role": "CLINICO",
        "center_code": "HGR-002",
    },
    {
        "username": "recepcion",
        "email": "recepcion@sisem.local",
        "full_name": "Recepcion Demo",
        "role": "RECEPCION",
        "center_code": "CLI-003",
    },
    {
        "username": "farmacia",
        "email": "farmacia@sisem.local",
        "full_name": "Farmacia Demo",
        "role": "FARMACIA",
        "center_code": "SAN-004",
    },
    {
        "username": "urgencias",
        "email": "urgencias@sisem.local",
        "full_name": "Urgencias Demo",
        "role": "URGENCIAS",
        "center_code": "URG-006",
    },
    {
        "username": "usuario_inactivo",
        "email": "inactivo@sisem.local",
        "full_name": "Usuario Inactivo",
        "role": "CLINICO",
        "is_active": False,
        "center_code": "HGR-002",
    },
    {
        "username": "usuario_bloqueado",
        "email": "bloqueado@sisem.local",
        "full_name": "Usuario Bloqueado",
        "role": "RECEPCION",
        "is_blocked": True,
        "center_code": "CLI-003",
    },
    {
        "username": "usuario_onboarding",
        "email": "onboarding@sisem.local",
        "full_name": "Usuario Onboarding",
        "role": "FARMACIA",
        "requires_onboarding": True,
        "center_code": "SAN-004",
    },
    {
        "username": "usuario_cambiar_clave",
        "email": "cambiar@sisem.local",
        "full_name": "Usuario Cambiar Clave",
        "role": "URGENCIAS",
        "must_change_password": True,
        "center_code": "URG-006",
    },
    {
        "username": "usuario_sin_centros",
        "email": "sincentro@sisem.local",
        "full_name": "Usuario Sin Centro",
        "role": "ADMIN_ROLES",
        "center_code": None,
    },
    {
        "username": "usuario_onboarding_clinico",
        "email": "onboarding.clinico@sisem.local",
        "full_name": "Onboarding Clinico",
        "role": "CLINICO",
        "requires_onboarding": True,
        "center_code": "HGR-002",
    },
    {
        "username": "usuario_onboarding_recepcion",
        "email": "onboarding.recepcion@sisem.local",
        "full_name": "Onboarding Recepcion",
        "role": "RECEPCION",
        "requires_onboarding": True,
        "center_code": "CLI-003",
    },
    {
        "username": "usuario_onboarding_farmacia",
        "email": "onboarding.farmacia@sisem.local",
        "full_name": "Onboarding Farmacia",
        "role": "FARMACIA",
        "requires_onboarding": True,
        "center_code": "SAN-004",
    },
    {
        "username": "usuario_onboarding_urgencias",
        "email": "onboarding.urgencias@sisem.local",
        "full_name": "Onboarding Urgencias",
        "role": "URGENCIAS",
        "requires_onboarding": True,
        "center_code": "URG-006",
    },
    {
        "username": "usuario_cambiar_clave_clinico",
        "email": "changepass.clinico@sisem.local",
        "full_name": "Cambiar Clave Clinico",
        "role": "CLINICO",
        "must_change_password": True,
        "center_code": "HGR-002",
    },
    {
        "username": "usuario_cambiar_clave_admin",
        "email": "changepass.admin@sisem.local",
        "full_name": "Cambiar Clave Admin",
        "role": "ADMIN_REPORTES",
        "must_change_password": True,
        "center_code": "CA-001",
    },
    {
        "username": "usuario_inactivo_clinico",
        "email": "inactivo.clinico@sisem.local",
        "full_name": "Clinico Inactivo",
        "role": "CLINICO",
        "is_active": False,
        "center_code": "HGR-002",
    },
    {
        "username": "usuario_inactivo_admin",
        "email": "inactivo.admin@sisem.local",
        "full_name": "Admin Inactivo",
        "role": "ADMIN_CATALOGOS",
        "is_active": False,
        "center_code": "SAN-004",
    },
    {
        "username": "usuario_bloqueado_clinico",
        "email": "bloqueado.clinico@sisem.local",
        "full_name": "Clinico Bloqueado",
        "role": "CLINICO",
        "is_blocked": True,
        "center_code": "HGR-002",
    },
    {
        "username": "usuario_bloqueado_admin",
        "email": "bloqueado.admin@sisem.local",
        "full_name": "Admin Bloqueado",
        "role": "ADMIN_ESTADISTICAS",
        "is_blocked": True,
        "center_code": "UMO-005",
    },
    {
        "username": "usuario_multirol",
        "email": "multirol@sisem.local",
        "full_name": "Usuario Multirol",
        "role": "CLINICO",
        "extra_roles": ["RECEPCION", "FARMACIA"],
        "center_code": "CA-001",
    },
]

KAN89_REPRO_BASELINE_USERNAMES = (
    "admin",
    "usuario_inactivo_clinico",
    "usuario_bloqueado_clinico",
    "usuario_onboarding_clinico",
    "usuario_cambiar_clave_clinico",
)


USER_OVERRIDE_DEFS = [
    {
        "username": "usuario_multirol",
        "permission_code": "clinico:consultas:create",
        "effect": "DENY",
    },
    {
        "username": "usuario_multirol",
        "permission_code": "admin:catalogos:areas:read",
        "effect": "ALLOW",
        "expires_in_days": 30,
    },
]


DEMO_VISITS = [
    {
        "folio": "RCP-DEMO-0001",
        "no_exp": "81001", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.APPOINTMENT,
        "appointment_id": "APP-DEMO-0001",
        "doctor_id": 120,
        "notes": "Paciente de ejemplo en recepcion.",
        "status": "en_espera",
    },
    {
        "folio": "RCP-DEMO-0002",
        "no_exp": "81002", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.WALK_IN,
        "appointment_id": None,
        "doctor_id": None,
        "notes": "Ingreso espontaneo para validar cola.",
        "status": "en_espera",
    },
    {
        "folio": "SMT-DEMO-0001",
        "no_exp": "82001", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.APPOINTMENT,
        "appointment_id": "APP-DEMO-0101",
        "doctor_id": 121,
        "notes": "Paciente listo para captura de vitales.",
        "status": "en_somatometria",
    },
    {
        "folio": "SMT-DEMO-0002",
        "no_exp": "82002", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.WALK_IN,
        "appointment_id": None,
        "doctor_id": 121,
        "notes": "Caso demo para validar captura repetida de signos vitales.",
        "status": "en_somatometria",
    },
    {
        "folio": "SMT-DEMO-0003",
        "no_exp": "82003", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.APPOINTMENT,
        "appointment_id": "APP-DEMO-0103",
        "doctor_id": 123,
        "notes": "Caso demo con doctor alterno para validar cola mixta.",
        "status": "en_somatometria",
    },
    {
        "folio": "SMT-DEMO-0004",
        "no_exp": "82004", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.WALK_IN,
        "appointment_id": None,
        "doctor_id": None,
        "notes": "Paciente sin doctor asignado para validar flujo operativo.",
        "status": "en_somatometria",
    },
    {
        "folio": "DOC-DEMO-0001",
        "no_exp": "83001", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.APPOINTMENT,
        "appointment_id": "APP-DEMO-0201",
        "doctor_id": 122,
        "notes": "Paciente listo para doctor.",
        "status": "lista_para_doctor",
    },
    {
        "folio": "DOC-DEMO-0002",
        "no_exp": "83002", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.WALK_IN,
        "appointment_id": None,
        "doctor_id": 122,
        "notes": "Consulta en curso para validar cierre.",
        "status": "en_consulta",
    },
    {
        "folio": "DOC-DEMO-0003",
        "no_exp": "83003", "pk_num": 0,
        "arrival_type": Visit.ArrivalType.APPOINTMENT,
        "appointment_id": "APP-DEMO-0203",
        "doctor_id": 123,
        "notes": "Paciente demo adicional listo para iniciar consulta.",
        "status": "lista_para_doctor",
    },
]


def _assert_required_tables():
    existing_tables = set(connection.introspection.table_names())
    missing_tables = sorted(REQUIRED_TABLES - existing_tables)
    if missing_tables:
        raise RuntimeError(
            "Estructura incompleta para seed_e2e. "
            f"Faltan tablas: {', '.join(missing_tables)}"
        )


def _ensure_seed_tables():
    existing_tables = set(connection.introspection.table_names())

    if "cat_areas" not in existing_tables:
        print("[SEED] cat_areas no existe; se omite carga de areas demo")


def _table_exists(table_name):
    return table_name in set(connection.introspection.table_names())


def _seed_centers(admin_user):
    centers_by_code = {}

    for center_def in CENTER_DEFS:
        center, _ = CatCentroAtencion.objects.update_or_create(
            code=center_def["code"],
            defaults={
                "name": center_def["name"],
                "is_external": center_def["is_external"],
                "address": center_def["address"],
                "is_active": center_def.get("is_active", True),
                "created_by_id": admin_user.id_usuario,
                "updated_by_id": admin_user.id_usuario,
            },
        )
        centers_by_code[center.code] = center

    print(f"[SEED] Centros asegurados: {len(centers_by_code)}")
    return centers_by_code


def _seed_area_types(admin_user):
    if not _table_exists("cat_tpareas"):
        fallback_types = {
            area_type_def["key"]: {"id": area_type_def["fallback_code"]}
            for area_type_def in AREA_TYPE_DEFS
        }
        print("[SEED] cat_tpareas no existe; se usan codigos fallback para cat_areas")
        return fallback_types

    area_types = {}

    for area_type_def in AREA_TYPE_DEFS:
        area_type, _ = TiposAreas.objects.update_or_create(
            name=area_type_def["name"],
            defaults={
                "is_active": area_type_def.get("is_active", True),
                "created_by_id": admin_user.id_usuario,
                "updated_by_id": admin_user.id_usuario,
            },
        )
        area_types[area_type_def["key"]] = area_type

    print(f"[SEED] Tipos de area asegurados: {len(area_types)}")
    return area_types


def _seed_areas(admin_user, area_types):
    if not _table_exists("cat_areas"):
        print("[SEED] cat_areas no existe; no se insertan areas demo")
        return

    total = 0

    for area_def in AREA_DEFS:
        area_type_ref = area_types.get(area_def["type_key"])
        if not area_type_ref:
            raise RuntimeError(
                f"No existe tipo de area para key '{area_def['type_key']}'"
            )

        if isinstance(area_type_ref, dict):
            area_type_id = area_type_ref["id"]
        else:
            area_type_id = area_type_ref.id

        Areas.objects.update_or_create(
            name=area_def["name"],
            defaults={
                "code": area_type_id,
                "tipo_area_id": area_type_id,
                "is_active": area_def.get("is_active", True),
                "created_by_id": admin_user.id_usuario,
                "updated_by_id": admin_user.id_usuario,
            },
        )
        total += 1

    print(f"[SEED] Areas aseguradas: {total}")


def _split_full_name(full_name):
    parts = full_name.split()
    if not parts:
        return "", "Demo", ""
    if len(parts) == 1:
        return parts[0], "Demo", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def _resolve_user_center(user_def, centers_by_code, default_center):
    center_code = user_def.get("center_code", default_center.code)

    if center_code is None:
        return None

    center = centers_by_code.get(center_code)
    if not center:
        raise RuntimeError(
            f"Centro '{center_code}' no existe para usuario {user_def['username']}"
        )

    return center


def _get_or_create_user(username, email, full_name, center, admin_user=None, **flags):
    user, _ = SyUsuario.objects.get_or_create(
        usuario=username,
        defaults={
            "correo": email,
            "clave_hash": make_password(DEFAULT_PASSWORD),
            "terminos_acept": True,
            "cambiar_clave": False,
            "est_activo": True,
            "est_bloqueado": False,
            "usr_alta": admin_user,
        },
    )

    updated_fields = []

    if user.correo != email:
        user.correo = email
        updated_fields.append("correo")

    user.clave_hash = make_password(DEFAULT_PASSWORD)
    updated_fields.append("clave_hash")

    is_active = flags.get("is_active", True)
    if user.est_activo != is_active:
        user.est_activo = is_active
        updated_fields.append("est_activo")

    if is_active and user.fch_baja is not None:
        user.fch_baja = None
        updated_fields.append("fch_baja")
    elif not is_active and user.fch_baja is None:
        user.fch_baja = timezone.now()
        updated_fields.append("fch_baja")

    is_blocked = flags.get("is_blocked", False)
    if user.est_bloqueado != is_blocked:
        user.est_bloqueado = is_blocked
        updated_fields.append("est_bloqueado")

    must_change_password = flags.get("must_change_password", False)
    if user.cambiar_clave != must_change_password:
        user.cambiar_clave = must_change_password
        updated_fields.append("cambiar_clave")

    requires_onboarding = flags.get("requires_onboarding", False)
    desired_terms_accepted = not requires_onboarding
    if user.terminos_acept != desired_terms_accepted:
        user.terminos_acept = desired_terms_accepted
        updated_fields.append("terminos_acept")

    desired_terms_date = (
        None if requires_onboarding else (user.fch_terminos or timezone.now())
    )
    if user.fch_terminos != desired_terms_date:
        user.fch_terminos = desired_terms_date
        updated_fields.append("fch_terminos")

    if updated_fields:
        user.fch_modf = timezone.now()
        updated_fields.append("fch_modf")
        if admin_user:
            user.usr_modf = admin_user
            updated_fields.append("usr_modf")
        user.save(update_fields=sorted(set(updated_fields)))
        print(
            f"[SEED] Actualizado {username}: {', '.join(sorted(set(updated_fields)))}"
        )
    else:
        print(f"[SEED] Verificado {username}: OK")

    first_name, paternal_name, maternal_name = _split_full_name(full_name)
    DetUsuario.objects.update_or_create(
        id_usuario=user,
        defaults={
            "nombre": first_name,
            "paterno": paternal_name,
            "materno": maternal_name,
            "id_centro_atencion": center,
        },
    )

    return user


def _sync_role_permissions(role, permission_codes, permissions_map, admin_user):
    desired_permission_ids = {
        permissions_map[code].id_permiso
        for code in permission_codes
        if code in permissions_map
    }

    existing_relations = {
        relation.id_permiso_id: relation
        for relation in RelRolPermiso.objects.filter(id_rol=role)
    }

    for permission_id in desired_permission_ids:
        relation = existing_relations.get(permission_id)

        if relation:
            relation_updates = []

            if relation.fch_baja is not None:
                relation.fch_baja = None
                relation_updates.append("fch_baja")

            if relation.usr_baja_id is not None:
                relation.usr_baja = None
                relation_updates.append("usr_baja")

            if relation.usr_asignacion_id is None:
                relation.usr_asignacion = admin_user
                relation_updates.append("usr_asignacion")

            if relation_updates:
                relation.save(update_fields=relation_updates)
        else:
            RelRolPermiso.objects.create(
                id_rol=role,
                id_permiso_id=permission_id,
                usr_asignacion=admin_user,
            )

    now = timezone.now()
    for permission_id, relation in existing_relations.items():
        if permission_id in desired_permission_ids or relation.fch_baja is not None:
            continue

        relation.fch_baja = now
        relation.usr_baja = admin_user
        relation.save(update_fields=["fch_baja", "usr_baja"])


def _sync_user_roles(user, primary_role, extra_roles, admin_user):
    desired_roles = {primary_role.id_rol: True}
    for role in extra_roles:
        desired_roles[role.id_rol] = False

    existing_relations = {
        relation.id_rol_id: relation
        for relation in RelUsuarioRol.objects.filter(id_usuario=user)
    }

    for role_id, is_primary in desired_roles.items():
        relation = existing_relations.get(role_id)

        if relation:
            relation_updates = []

            if relation.fch_baja is not None:
                relation.fch_baja = None
                relation_updates.append("fch_baja")

            if relation.usr_baja_id is not None:
                relation.usr_baja = None
                relation_updates.append("usr_baja")

            if relation.is_primary != is_primary:
                relation.is_primary = is_primary
                relation_updates.append("is_primary")

            if relation.usr_asignacion_id is None:
                relation.usr_asignacion = admin_user
                relation_updates.append("usr_asignacion")

            if relation_updates:
                relation.save(update_fields=relation_updates)
        else:
            RelUsuarioRol.objects.create(
                id_usuario=user,
                id_rol_id=role_id,
                is_primary=is_primary,
                usr_asignacion=admin_user,
            )

    now = timezone.now()
    for role_id, relation in existing_relations.items():
        if role_id in desired_roles or relation.fch_baja is not None:
            continue

        relation.fch_baja = now
        relation.usr_baja = admin_user
        if relation.is_primary:
            relation.is_primary = False
            relation.save(update_fields=["fch_baja", "usr_baja", "is_primary"])
        else:
            relation.save(update_fields=["fch_baja", "usr_baja"])


def _seed_user_overrides(users_by_username, permissions_map, admin_user):
    total = 0

    for override_def in USER_OVERRIDE_DEFS:
        username = override_def["username"]
        permission_code = override_def["permission_code"]

        user = users_by_username.get(username)
        permission = permissions_map.get(permission_code)

        if not user:
            print(f"[SEED] Override omitido: usuario {username} no existe")
            continue
        if not permission:
            print(f"[SEED] Override omitido: permiso {permission_code} no existe")
            continue

        expires_in_days = override_def.get("expires_in_days")

        override, created = RelUsuarioOverride.objects.get_or_create(
            id_usuario=user,
            id_permiso=permission,
            defaults={
                "efecto": override_def["effect"],
                "fch_expira": (
                    timezone.now() + timedelta(days=expires_in_days)
                    if expires_in_days is not None
                    else None
                ),
                "fch_baja": None,
                "usr_asignacion": admin_user,
                "usr_baja": None,
            },
        )

        update_fields = []

        if override.efecto != override_def["effect"]:
            override.efecto = override_def["effect"]
            update_fields.append("efecto")

        expected_expiry = None
        if expires_in_days is not None:
            expected_expiry = override.fch_expira
            if created or expected_expiry is None:
                expected_expiry = timezone.now() + timedelta(days=expires_in_days)

        if override.fch_expira != expected_expiry:
            override.fch_expira = expected_expiry
            update_fields.append("fch_expira")

        if override.fch_baja is not None:
            override.fch_baja = None
            update_fields.append("fch_baja")

        if override.usr_baja_id is not None:
            override.usr_baja = None
            update_fields.append("usr_baja")

        if override.usr_asignacion_id != admin_user.id_usuario:
            override.usr_asignacion = admin_user
            update_fields.append("usr_asignacion")

        if update_fields:
            override.save(update_fields=sorted(set(update_fields)))

        total += 1

    print(f"[SEED] Overrides asegurados: {total}")


def _seed_demo_visits():
    if not _table_exists("rcp_visits"):
        print("[SEED] rcp_visits no existe; se omite carga de visitas demo")
        return

    total = 0
    for visit_def in DEMO_VISITS:
        Visit.objects.update_or_create(
            folio=visit_def["folio"],
            defaults={
                "no_exp":         visit_def["no_exp"],
                "pk_num":         visit_def["pk_num"],
                "arrival_type":   visit_def["arrival_type"],
                "appointment_id": visit_def["appointment_id"],
                "doctor_id":      visit_def["doctor_id"],
                "notes":          visit_def["notes"],
                "status":         visit_def["status"],
                "fch_baja":       None,
            },
        )
        total += 1

    print(f"[SEED] Visitas demo aseguradas: {total}")


def build_kan89_user_subset_snapshot(user_defs=USER_DEFS):
    baseline = []
    allowlist = set(KAN89_REPRO_BASELINE_USERNAMES)

    for user_def in user_defs:
        if user_def["username"] not in allowlist:
            continue

        baseline.append(
            {
                "username": user_def["username"],
                "email": user_def["email"],
                "is_active": user_def.get("is_active", True),
                "is_blocked": user_def.get("is_blocked", False),
                "requires_onboarding": user_def.get("requires_onboarding", False),
                "must_change_password": user_def.get("must_change_password", False),
            }
        )

    baseline.sort(key=lambda item: item["username"])
    return baseline


@transaction.atomic
def run():
    _ensure_seed_tables()
    _assert_required_tables()

    admin_user = _get_or_create_user(
        "admin",
        "admin@sisem.local",
        "Admin Sistema",
        center=None,
        admin_user=None,
    )

    permissions_map = {}
    for code, description in PERMISSIONS:
        permission, _ = Permisos.objects.update_or_create(
            codigo=code,
            defaults={
                "descripcion": description,
                "es_sistema": False,
                "is_active": True,
                "created_by_id": admin_user.id_usuario,
                "updated_by_id": admin_user.id_usuario,
            },
        )
        permissions_map[code] = permission

    print(f"[SEED] Permisos asegurados: {len(permissions_map)}")

    role_field_names = {field.name for field in Roles._meta.get_fields()}
    role_map = {}
    for role_def in ROLE_DEFS:
        role_defaults = {
            "desc_rol": role_def["desc"],
            "landing_route": role_def["landing"],
            "is_admin": role_def.get("is_admin", False),
            "es_sistema": role_def.get("is_system", False),
            "is_active": role_def.get("is_active", True),
        }
        if "created_by_id" in role_field_names:
            role_defaults["created_by_id"] = admin_user.id_usuario
        if "updated_by_id" in role_field_names:
            role_defaults["updated_by_id"] = admin_user.id_usuario

        role, _ = Roles.objects.update_or_create(
            rol=role_def["code"],
            defaults=role_defaults,
        )

        role_map[role_def["code"]] = role

        if role_def.get("is_admin"):
            continue

        _sync_role_permissions(
            role,
            role_def.get("perms", []),
            permissions_map,
            admin_user,
        )

    print(f"[SEED] Roles asegurados: {len(role_map)}")

    centers_by_code = _seed_centers(admin_user)
    area_types = _seed_area_types(admin_user)
    _seed_areas(admin_user, area_types)

    default_center = centers_by_code["CA-001"]

    users_by_username = {}
    for user_def in USER_DEFS:
        role = role_map.get(user_def["role"])
        if not role:
            raise RuntimeError(
                f"Rol principal '{user_def['role']}' no existe para {user_def['username']}"
            )

        center = _resolve_user_center(user_def, centers_by_code, default_center)

        user = _get_or_create_user(
            user_def["username"],
            user_def["email"],
            user_def["full_name"],
            center,
            admin_user=admin_user,
            is_active=user_def.get("is_active", True),
            is_blocked=user_def.get("is_blocked", False),
            requires_onboarding=user_def.get("requires_onboarding", False),
            must_change_password=user_def.get("must_change_password", False),
        )

        if user.usuario == "admin":
            admin_user = user

        users_by_username[user.usuario] = user

        extra_roles = []
        for role_code in user_def.get("extra_roles") or []:
            extra_role = role_map.get(role_code)
            if not extra_role:
                raise RuntimeError(
                    f"Rol extra '{role_code}' no existe para {user_def['username']}"
                )
            extra_roles.append(extra_role)

        _sync_user_roles(user, role, extra_roles, admin_user)

    print(f"[SEED] Usuarios asegurados: {len(users_by_username)}")

    _seed_user_overrides(users_by_username, permissions_map, admin_user)
    _seed_demo_visits()

    baseline_snapshot = build_kan89_user_subset_snapshot()
    print(
        f"[SEED][KAN-89] baseline users ({len(baseline_snapshot)}): {baseline_snapshot}"
    )


if __name__ == "__main__":
    run()
