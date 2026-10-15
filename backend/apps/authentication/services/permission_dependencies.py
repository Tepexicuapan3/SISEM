from typing import Dict, List, TypedDict


class PermissionDependencyState(TypedDict):
    granted: bool
    requiredPermissions: List[str]
    missingPermissions: List[str]


class PermissionRequirement(TypedDict, total=False):
    allOf: List[str]
    anyOf: List[str]


class PermissionRequirementState(TypedDict):
    granted: bool
    missingAllOf: List[str]
    missingAnyOf: List[str]


WRITE_ACTIONS = {
    "create",
    "update",
    "delete",
    "manage",
    "assign",
    "revoke",
}


EXPLICIT_PERMISSION_DEPENDENCIES: Dict[str, List[str]] = {
    "admin:gestion:usuarios:create": ["admin:gestion:roles:read"],
    "admin:gestion:usuarios:update": [
        "admin:gestion:roles:read",
        "admin:gestion:permisos:read",
    ],
    "admin:gestion:roles:create": ["admin:gestion:permisos:read"],
    "admin:gestion:roles:update": ["admin:gestion:permisos:read"],
    # Designacion de autorizadores (change cancelacion-nota-cascada): `write`
    # y `global` no estan en WRITE_ACTIONS, asi que la dependencia de lectura
    # se declara explicita.
    "admin:autorizadores:designacion:write": ["admin:autorizadores:designacion:read"],
    "admin:autorizadores:designacion:global": ["admin:autorizadores:designacion:write"],
}


CAPABILITY_REQUIREMENTS: Dict[str, PermissionRequirement] = {
    "admin.users.read": {"allOf": ["admin:gestion:usuarios:read"]},
    "admin.users.create": {"allOf": ["admin:gestion:usuarios:create"]},
    "admin.users.update": {"allOf": ["admin:gestion:usuarios:update"]},
    "admin.users.rolesCatalog.read": {"allOf": ["admin:gestion:roles:read"]},
    "admin.users.permissionsCatalog.read": {
        "allOf": ["admin:gestion:permisos:read"]
    },
    "admin.users.clinicsCatalog.read": {
        "allOf": ["admin:catalogos:centros_atencion:read"]
    },
    "admin.users.editFull": {
        "allOf": [
            "admin:gestion:usuarios:read",
            "admin:gestion:usuarios:update",
            "admin:gestion:roles:read",
            "admin:gestion:permisos:read",
        ]
    },
    "admin.roles.read": {"allOf": ["admin:gestion:roles:read"]},
    "admin.roles.create": {"allOf": ["admin:gestion:roles:create"]},
    "admin.roles.update": {"allOf": ["admin:gestion:roles:update"]},
    "admin.roles.delete": {"allOf": ["admin:gestion:roles:delete"]},
    "admin.roles.permissionsCatalog.read": {
        "allOf": ["admin:gestion:permisos:read"]
    },
    "admin.roles.editFull": {
        "allOf": [
            "admin:gestion:roles:read",
            "admin:gestion:roles:update",
            "admin:gestion:permisos:read",
        ]
    },
    "admin.catalogs.areas.read": {"allOf": ["admin:catalogos:areas:read"]},
    "admin.catalogs.areas.create": {
        "allOf": ["admin:catalogos:areas:create"]
    },
    "admin.catalogs.areas.update": {
        "allOf": ["admin:catalogos:areas:update"]
    },
    "admin.catalogs.areas.delete": {
        "allOf": ["admin:catalogos:areas:delete"]
    },
    "admin.catalogs.centers.read": {
        "allOf": ["admin:catalogos:centros_atencion:read"]
    },
    "admin.catalogs.centers.create": {
        "allOf": ["admin:catalogos:centros_atencion:create"]
    },
    "admin.catalogs.centers.update": {
        "allOf": ["admin:catalogos:centros_atencion:update"]
    },
    "admin.catalogs.centers.delete": {
        "allOf": ["admin:catalogos:centros_atencion:delete"]
    },
    "admin.catalogs.escolaridad.read": {"allOf": ["admin:catalogos:escolaridad:read"]},
    "admin.catalogs.escolaridad.create": {"allOf": ["admin:catalogos:escolaridad:create"]},
    "admin.catalogs.escolaridad.update": {"allOf": ["admin:catalogos:escolaridad:update"]},
    "admin.catalogs.escolaridad.delete": {"allOf": ["admin:catalogos:escolaridad:delete"]},
    "admin.catalogs.discapacidades.read": {"allOf": ["admin:catalogos:discapacidades:read"]},
    "admin.catalogs.discapacidades.create": {"allOf": ["admin:catalogos:discapacidades:create"]},
    "admin.catalogs.discapacidades.update": {"allOf": ["admin:catalogos:discapacidades:update"]},
    "admin.catalogs.discapacidades.delete": {"allOf": ["admin:catalogos:discapacidades:delete"]},
    "admin.catalogs.calidadLaboral.read": {"allOf": ["admin:catalogos:calidad_laboral:read"]},
    "admin.catalogs.calidadLaboral.create": {"allOf": ["admin:catalogos:calidad_laboral:create"]},
    "admin.catalogs.calidadLaboral.update": {"allOf": ["admin:catalogos:calidad_laboral:update"]},
    "admin.catalogs.calidadLaboral.delete": {"allOf": ["admin:catalogos:calidad_laboral:delete"]},
    "admin.catalogs.origenConsulta.read": {"allOf": ["admin:catalogos:origen_cons:read"]},
    "admin.catalogs.origenConsulta.create": {"allOf": ["admin:catalogos:origen_cons:create"]},
    "admin.catalogs.origenConsulta.update": {"allOf": ["admin:catalogos:origen_cons:update"]},
    "admin.catalogs.origenConsulta.delete": {"allOf": ["admin:catalogos:origen_cons:delete"]},
    "admin.catalogs.parentescos.read": {"allOf": ["admin:catalogos:parentescos:read"]},
    "admin.catalogs.parentescos.create": {"allOf": ["admin:catalogos:parentescos:create"]},
    "admin.catalogs.parentescos.update": {"allOf": ["admin:catalogos:parentescos:update"]},
    "admin.catalogs.parentescos.delete": {"allOf": ["admin:catalogos:parentescos:delete"]},
    # Designacion de autorizadores (reemplazo de la pantalla antigua de Autorizadores).
    "admin.catalogs.designacionAutorizadores.read": {"allOf": ["admin:autorizadores:designacion:read"]},
    "admin.catalogs.designacionAutorizadores.write": {"allOf": ["admin:autorizadores:designacion:write"]},
    "admin.catalogs.designacionAutorizadores.global": {"allOf": ["admin:autorizadores:designacion:global"]},
    "admin.catalogs.gruposMedicamentos.read": {"allOf": ["admin:catalogos:grupos_medicamentos:read"]},
    "admin.catalogs.gruposMedicamentos.create": {"allOf": ["admin:catalogos:grupos_medicamentos:create"]},
    "admin.catalogs.gruposMedicamentos.update": {"allOf": ["admin:catalogos:grupos_medicamentos:update"]},
    "admin.catalogs.gruposMedicamentos.delete": {"allOf": ["admin:catalogos:grupos_medicamentos:delete"]},
    "admin.catalogs.ocupaciones.read": {"allOf": ["admin:catalogos:ocupaciones:read"]},
    "admin.catalogs.ocupaciones.create": {"allOf": ["admin:catalogos:ocupaciones:create"]},
    "admin.catalogs.ocupaciones.update": {"allOf": ["admin:catalogos:ocupaciones:update"]},
    "admin.catalogs.ocupaciones.delete": {"allOf": ["admin:catalogos:ocupaciones:delete"]},
    "admin.catalogs.licencias.read": {"allOf": ["admin:catalogos:licencias:read"]},
    "admin.catalogs.licencias.create": {"allOf": ["admin:catalogos:licencias:create"]},
    "admin.catalogs.licencias.update": {"allOf": ["admin:catalogos:licencias:update"]},
    "admin.catalogs.licencias.delete": {"allOf": ["admin:catalogos:licencias:delete"]},
    "admin.catalogs.tipo-personal.read": {"allOf": ["admin:catalogos:tipo_personal:read"]},
    "admin.catalogs.tipo-personal.create": {"allOf": ["admin:catalogos:tipo_personal:create"]},
    "admin.catalogs.tipo-personal.update": {"allOf": ["admin:catalogos:tipo_personal:update"]},
    "admin.catalogs.tipo-personal.delete": {"allOf": ["admin:catalogos:tipo_personal:delete"]},
    "admin.catalogs.tiposAreas.read": {"allOf": ["admin:catalogos:tipos_areas:read"]},
    "admin.catalogs.tiposAreas.create": {"allOf": ["admin:catalogos:tipos_areas:create"]},
    "admin.catalogs.tiposAreas.update": {"allOf": ["admin:catalogos:tipos_areas:update"]},
    "admin.catalogs.tiposAreas.delete": {"allOf": ["admin:catalogos:tipos_areas:delete"]},
    "admin.catalogs.tipos-citas.read": {"allOf": ["admin:catalogos:tipo_citas:read"]},
    "admin.catalogs.tipos-citas.create": {"allOf": ["admin:catalogos:tipo_citas:create"]},
    "admin.catalogs.tipos-citas.update": {"allOf": ["admin:catalogos:tipo_citas:update"]},
    "admin.catalogs.tipos-citas.delete": {"allOf": ["admin:catalogos:tipo_citas:delete"]},
    "admin.catalogs.tipos-consulta.read": {"allOf": ["admin:catalogos:tipo_consulta:read"]},
    "admin.catalogs.tipos-consulta.create": {"allOf": ["admin:catalogos:tipo_consulta:create"]},
    "admin.catalogs.tipos-consulta.update": {"allOf": ["admin:catalogos:tipo_consulta:update"]},
    "admin.catalogs.tipos-consulta.delete": {"allOf": ["admin:catalogos:tipo_consulta:delete"]},
    "admin.catalogs.religiones.read": {"allOf": ["admin:catalogos:religion:read"]},
    "admin.catalogs.religiones.create": {"allOf": ["admin:catalogos:religion:create"]},
    "admin.catalogs.religiones.update": {"allOf": ["admin:catalogos:religion:update"]},
    "admin.catalogs.religiones.delete": {"allOf": ["admin:catalogos:religion:delete"]},
    "admin.catalogs.tipos-residencia.read": {"allOf": ["admin:catalogos:tipo_residencia:read"]},
    "admin.catalogs.tipos-residencia.create": {"allOf": ["admin:catalogos:tipo_residencia:create"]},
    "admin.catalogs.tipos-residencia.update": {"allOf": ["admin:catalogos:tipo_residencia:update"]},
    "admin.catalogs.tipos-residencia.delete": {"allOf": ["admin:catalogos:tipo_residencia:delete"]},
    "admin.catalogs.escuelas.read": {"allOf": ["admin:catalogos:escuelas:read"]},
    "admin.catalogs.escuelas.create": {"allOf": ["admin:catalogos:escuelas:create"]},
    "admin.catalogs.escuelas.update": {"allOf": ["admin:catalogos:escuelas:update"]},
    "admin.catalogs.escuelas.delete": {"allOf": ["admin:catalogos:escuelas:delete"]},
    "admin.catalogs.estudiosMedicos.read": {"allOf": ["admin:catalogos:estudios_med:read"]},
    "admin.catalogs.estudiosMedicos.create": {"allOf": ["admin:catalogos:estudios_med:create"]},
    "admin.catalogs.estudiosMedicos.update": {"allOf": ["admin:catalogos:estudios_med:update"]},
    "admin.catalogs.estudiosMedicos.delete": {"allOf": ["admin:catalogos:estudios_med:delete"]},
    "admin.catalogs.sucursales.read": {"allOf": ["admin:catalogos:sucursales:read"]},
    "admin.catalogs.sucursales.create": {"allOf": ["admin:catalogos:sucursales:create"]},
    "admin.catalogs.sucursales.update": {"allOf": ["admin:catalogos:sucursales:update"]},
    "admin.catalogs.sucursales.delete": {"allOf": ["admin:catalogos:sucursales:delete"]},
    "admin.catalogs.turnos.read": {"allOf": ["admin:catalogos:turnos:read"]},
    "admin.catalogs.turnos.create": {"allOf": ["admin:catalogos:turnos:create"]},
    "admin.catalogs.turnos.update": {"allOf": ["admin:catalogos:turnos:update"]},
    "admin.catalogs.turnos.delete": {"allOf": ["admin:catalogos:turnos:delete"]},
    "admin.catalogs.vacunas.read": {"allOf": ["admin:catalogos:vacunas:read"]},
    "admin.catalogs.vacunas.create": {"allOf": ["admin:catalogos:vacunas:create"]},
    "admin.catalogs.vacunas.update": {"allOf": ["admin:catalogos:vacunas:update"]},
    "admin.catalogs.vacunas.delete": {"allOf": ["admin:catalogos:vacunas:delete"]},
    "admin.catalogs.areas_clinicas.read": {"allOf": ["admin:catalogos:areas_clinicas:read"]},
    "admin.catalogs.areas_clinicas.create": {"allOf": ["admin:catalogos:areas_clinicas:create"]},
    "admin.catalogs.areas_clinicas.update": {"allOf": ["admin:catalogos:areas_clinicas:update"]},
    "admin.catalogs.areas_clinicas.delete": {"allOf": ["admin:catalogos:areas_clinicas:delete"]},
    "admin.catalogs.centroAreaClinica.read": {"allOf": ["admin:catalogos:centro_area_clinica:read"]},
    "admin.catalogs.centroAreaClinica.create": {"allOf": ["admin:catalogos:centro_area_clinica:create"]},
    "admin.catalogs.centroAreaClinica.update": {"allOf": ["admin:catalogos:centro_area_clinica:update"]},
    "admin.catalogs.centroAreaClinica.delete": {"allOf": ["admin:catalogos:centro_area_clinica:delete"]},
    "admin.catalogs.especialidades.read": {"allOf": ["admin:catalogos:especialidades:read"]},
    "admin.catalogs.especialidades.create": {"allOf": ["admin:catalogos:especialidades:create"]},
    "admin.catalogs.especialidades.update": {"allOf": ["admin:catalogos:especialidades:update"]},
    "admin.catalogs.especialidades.delete": {"allOf": ["admin:catalogos:especialidades:delete"]},
    "admin.catalogs.edo_civil.read": {"allOf": ["admin:catalogos:edo_civil:read"]},
    "admin.catalogs.edo_civil.create": {"allOf": ["admin:catalogos:edo_civil:create"]},
    "admin.catalogs.edo_civil.update": {"allOf": ["admin:catalogos:edo_civil:update"]},
    "admin.catalogs.edo_civil.delete": {"allOf": ["admin:catalogos:edo_civil:delete"]},
    "admin.catalogs.enfermedades.read": {"allOf": ["admin:catalogos:enfermedades:read"]},
    "admin.catalogs.enfermedades.create": {"allOf": ["admin:catalogos:enfermedades:create"]},
    "admin.catalogs.enfermedades.update": {"allOf": ["admin:catalogos:enfermedades:update"]},
    "admin.catalogs.enfermedades.delete": {"allOf": ["admin:catalogos:enfermedades:delete"]},
    "admin.catalogs.tiposAutorizacion.read": {"allOf": ["admin:catalogos:tp_autorizacion:read"]},
    "admin.catalogs.tiposAutorizacion.create": {"allOf": ["admin:catalogos:tp_autorizacion:create"]},
    "admin.catalogs.tiposAutorizacion.update": {"allOf": ["admin:catalogos:tp_autorizacion:update"]},
    "admin.catalogs.tiposAutorizacion.delete": {"allOf": ["admin:catalogos:tp_autorizacion:delete"]},
    "admin.catalogs.bajas.read": {"allOf": ["admin:catalogos:bajas:read"]},
    "admin.catalogs.bajas.create": {"allOf": ["admin:catalogos:bajas:create"]},
    "admin.catalogs.bajas.update": {"allOf": ["admin:catalogos:bajas:update"]},
    "admin.catalogs.bajas.delete": {"allOf": ["admin:catalogos:bajas:delete"]},
    "admin.catalogs.pases.read": {"allOf": ["admin:catalogos:pases:read"]},
    "admin.catalogs.pases.create": {"allOf": ["admin:catalogos:pases:create"]},
    "admin.catalogs.pases.update": {"allOf": ["admin:catalogos:pases:update"]},
    "admin.catalogs.pases.delete": {"allOf": ["admin:catalogos:pases:delete"]},
    "admin.catalogs.tiposSanguineo.read": {"allOf": ["admin:catalogos:tipos_sanguineo:read"]},
    "admin.catalogs.tiposSanguineo.create": {"allOf": ["admin:catalogos:tipos_sanguineo:create"]},
    "admin.catalogs.tiposSanguineo.update": {"allOf": ["admin:catalogos:tipos_sanguineo:update"]},
    "admin.catalogs.tiposSanguineo.delete": {"allOf": ["admin:catalogos:tipos_sanguineo:delete"]},
    "admin.catalogs.cies.upload": {"allOf": ["admin:catalogos:cies:upload"]},
    "admin.catalogs.cie9mc.read": {"allOf": ["admin:catalogos:cie9_mc:read"]},
    "admin.catalogs.cie9mc.create": {"allOf": ["admin:catalogos:cie9_mc:create"]},
    "admin.catalogs.cie9mc.update": {"allOf": ["admin:catalogos:cie9_mc:update"]},
    "admin.catalogs.cie9mc.delete": {"allOf": ["admin:catalogos:cie9_mc:delete"]},
    "admin.catalogs.tiposcirugia.read": {"allOf": ["admin:catalogos:tipos_cirugia:read"]},
    "admin.catalogs.tiposcirugia.create": {"allOf": ["admin:catalogos:tipos_cirugia:create"]},
    "admin.catalogs.tiposcirugia.update": {"allOf": ["admin:catalogos:tipos_cirugia:update"]},
    "admin.catalogs.tiposcirugia.delete": {"allOf": ["admin:catalogos:tipos_cirugia:delete"]},
    "admin.catalogs.clasificacionescirugia.read": {"allOf": ["admin:catalogos:clasificaciones_cirugia:read"]},
    "admin.catalogs.clasificacionescirugia.create": {"allOf": ["admin:catalogos:clasificaciones_cirugia:create"]},
    "admin.catalogs.clasificacionescirugia.update": {"allOf": ["admin:catalogos:clasificaciones_cirugia:update"]},
    "admin.catalogs.clasificacionescirugia.delete": {"allOf": ["admin:catalogos:clasificaciones_cirugia:delete"]},
    "admin.catalogs.motivoscancelacioncirugia.read": {"allOf": ["admin:catalogos:motivos_cancelacion_cirugia:read"]},
    "admin.catalogs.motivoscancelacioncirugia.create": {"allOf": ["admin:catalogos:motivos_cancelacion_cirugia:create"]},
    "admin.catalogs.motivoscancelacioncirugia.update": {"allOf": ["admin:catalogos:motivos_cancelacion_cirugia:update"]},
    "admin.catalogs.motivoscancelacioncirugia.delete": {"allOf": ["admin:catalogos:motivos_cancelacion_cirugia:delete"]},
    "admin.catalogs.motivoscancelacionnota.read": {"allOf": ["admin:catalogos:motivos_cancelacion_nota:read"]},
    "admin.catalogs.motivoscancelacionnota.create": {"allOf": ["admin:catalogos:motivos_cancelacion_nota:create"]},
    "admin.catalogs.motivoscancelacionnota.update": {"allOf": ["admin:catalogos:motivos_cancelacion_nota:update"]},
    "admin.catalogs.motivoscancelacionnota.delete": {"allOf": ["admin:catalogos:motivos_cancelacion_nota:delete"]},
    "admin.catalogs.motivostraslado.read": {"allOf": ["admin:catalogos:motivos_traslado:read"]},
    "admin.catalogs.motivostraslado.create": {"allOf": ["admin:catalogos:motivos_traslado:create"]},
    "admin.catalogs.motivostraslado.update": {"allOf": ["admin:catalogos:motivos_traslado:update"]},
    "admin.catalogs.motivostraslado.delete": {"allOf": ["admin:catalogos:motivos_traslado:delete"]},
    "admin.catalogs.tipostraslado.read": {"allOf": ["admin:catalogos:tipos_traslado:read"]},
    "admin.catalogs.tipostraslado.create": {"allOf": ["admin:catalogos:tipos_traslado:create"]},
    "admin.catalogs.tipostraslado.update": {"allOf": ["admin:catalogos:tipos_traslado:update"]},
    "admin.catalogs.tipostraslado.delete": {"allOf": ["admin:catalogos:tipos_traslado:delete"]},
    "admin.catalogs.tiposservicioambulancia.read": {"allOf": ["admin:catalogos:tipos_servicio_ambulancia:read"]},
    "admin.catalogs.tiposservicioambulancia.create": {"allOf": ["admin:catalogos:tipos_servicio_ambulancia:create"]},
    "admin.catalogs.tiposservicioambulancia.update": {"allOf": ["admin:catalogos:tipos_servicio_ambulancia:update"]},
    "admin.catalogs.tiposservicioambulancia.delete": {"allOf": ["admin:catalogos:tipos_servicio_ambulancia:delete"]},
    "admin.catalogs.destinosambulancia.read": {"allOf": ["admin:catalogos:destinos_ambulancia:read"]},
    "admin.catalogs.destinosambulancia.create": {"allOf": ["admin:catalogos:destinos_ambulancia:create"]},
    "admin.catalogs.destinosambulancia.update": {"allOf": ["admin:catalogos:destinos_ambulancia:update"]},
    "admin.catalogs.destinosambulancia.delete": {"allOf": ["admin:catalogos:destinos_ambulancia:delete"]},
    # Catalogos genericos (GenericCatalogPage) -- la clave la arma el
    # frontend como `admin.catalogs.${catalog.slug}.read` a partir de
    # `catalog-definitions.ts` (slug con GUIONES, no camelCase/underscore).
    # Debe coincidir caracter por caracter con ese slug o la pantalla queda
    # bloqueada para TODOS (incluido admin), porque "admin." es un prefijo
    # estricto que no cae al fallback de permisos crudos.
    "admin.catalogs.edo-civil.read": {"allOf": ["admin:catalogos:edo_civil:read"]},
    "admin.catalogs.tipos-areas.read": {"allOf": ["admin:catalogos:tipos_areas:read"]},
    "admin.catalogs.areas-clinicas.read": {"allOf": ["admin:catalogos:areas_clinicas:read"]},
    "admin.catalogs.centro-area-clinica.read": {"allOf": ["admin:catalogos:centro_area_clinica:read"]},
    # Gestion de menus (arbol de navegacion / cat_modulos)
    "admin.menus.read": {"allOf": ["admin:gestion:modulos:read"]},
    "admin.menus.create": {"allOf": ["admin:gestion:modulos:create"]},
    "admin.menus.update": {"allOf": ["admin:gestion:modulos:update"]},
    "admin.menus.delete": {"allOf": ["admin:gestion:modulos:delete"]},
    # Solicitudes ARCO
    "admin.arco.write": {"allOf": ["admin:arco:write"]},
    # Médicos
    "admin.medicos.read":        {"allOf": ["admin:gestion:medicos:read"]},
    "admin.medicos.create":      {"allOf": ["admin:gestion:medicos:create"]},
    "admin.medicos.update":      {"allOf": ["admin:gestion:medicos:update"]},
    "admin.medicos.horarios":    {"allOf": ["admin:gestion:medicos:horarios"]},
    "admin.medicos.excepciones": {"allOf": ["admin:gestion:medicos:excepciones"]},
    "admin.medicos.coberturas":  {"allOf": ["admin:gestion:medicos:coberturas"]},
    "farmacia.vacunas.read": {"allOf": ["farmacia:vacunas:read"]},
    "farmacia.vacunas.create": {"allOf": ["farmacia:vacunas:create"]},
    "farmacia.vacunas.update": {"allOf": ["farmacia:vacunas:update"]},
    "farmacia.vacunas.delete": {"allOf": ["farmacia:vacunas:delete"]},
    "flow.visits.queue.read": {
        "anyOf": [
            "recepcion:fichas:medicina_general:create",
            "recepcion:fichas:especialidad:create",
            "recepcion:fichas:urgencias:create",
            "clinico:consultas:read",
            "clinico:somatometria:read",
        ]
    },
    "flow.recepcion.queue.write": {
        "anyOf": [
            "recepcion:fichas:medicina_general:create",
            "recepcion:fichas:especialidad:create",
            "recepcion:fichas:urgencias:create",
        ]
    },
    "flow.somatometria.queue.read": {
        "allOf": ["clinico:somatometria:read"]
    },
    "flow.somatometria.capture": {
        "allOf": ["clinico:somatometria:read"]
    },
    # D6 (change `somatometria-modulo-integral`): permiso base
    # `clinico:somatometria:update`, NO `:edit` -- "edit" no esta en
    # `WRITE_ACTIONS`, y usar `:update` deja que `_infer_read_dependency`
    # derive automaticamente `clinico:somatometria:read` sin tocar ese set
    # global (que afecta a TODOS los permisos del sistema). La capability
    # conserva el verbo de UI ("edit").
    "flow.somatometria.edit": {
        "allOf": ["clinico:somatometria:update"]
    },
    "flow.doctor.queue.read": {
        "allOf": ["clinico:consultas:read"]
    },
    "flow.doctor.consultation.start": {
        "allOf": ["clinico:consultas:read"]
    },
    "flow.doctor.consultation.close": {
        "allOf": ["clinico:consultas:read"]
    },
    # Cancelacion de nota cerrada en cascada (change `cancelacion-nota-cascada`).
    "clinico.notas.cancel": {"allOf": ["clinico:notas:cancel"]},
    # ── Citas médicas ──────────────────────────────────────────────────────────
    "recepcion:citas:read": {
        "allOf": ["recepcion:citas:read"]
    },
    "recepcion:citas:write": {
        "allOf": ["recepcion:citas:write"]
    },
    # Documentos imprimibles (change `documentos-imprimibles`): mapean a permisos
    # EXISTENTES (sin seeds nuevos) para no dejar fuera a usuarios actuales.
    "documentos.ficha.imprimir": {
        "anyOf": [
            "recepcion:fichas:medicina_general:create",
            "recepcion:fichas:especialidad:create",
            "recepcion:fichas:urgencias:create",
            "clinico:consultas:read",
        ]
    },
    "documentos.receta.imprimir": {
        "anyOf": ["clinico:consultas:read", "farmacia:recetas:dispensar"]
    },
    "documentos.nota.imprimir": {"allOf": ["clinico:consultas:read"]},
}


STRICT_CAPABILITY_PREFIXES: List[str] = [
    "flow.recepcion.",
    "flow.somatometria.",
    "flow.visits.",
]


def _normalize_permission(permission_code: str) -> str:
    return permission_code.strip()


def _merge_unique(values: List[str]) -> List[str]:
    return sorted(set(values))


def _infer_read_dependency(permission_code: str):
    segments = [segment.strip() for segment in permission_code.split(":")]
    if len(segments) < 2:
        return None

    action = segments[-1].lower()
    if action not in WRITE_ACTIONS:
        return None

    read_segments = [*segments]
    read_segments[-1] = "read"
    return ":".join(read_segments)


def get_permission_direct_dependencies(permission_code: str) -> List[str]:
    normalized_permission = _normalize_permission(permission_code)
    if not normalized_permission:
        return []

    explicit = EXPLICIT_PERMISSION_DEPENDENCIES.get(normalized_permission, [])
    dependencies = set(explicit)

    inferred = _infer_read_dependency(normalized_permission)
    if inferred and inferred != normalized_permission:
        dependencies.add(inferred)

    return sorted(dependencies)


def get_permission_dependency_closure(permission_code: str) -> List[str]:
    normalized_permission = _normalize_permission(permission_code)
    if not normalized_permission:
        return []

    visited = set()
    stack = [normalized_permission]

    while stack:
        current = stack.pop()
        if not current or current in visited:
            continue

        visited.add(current)

        for dependency in get_permission_direct_dependencies(current):
            if dependency not in visited:
                stack.append(dependency)

    return sorted(visited)


def evaluate_permission_dependencies(
    permission_code: str,
    granted_permissions: List[str],
) -> PermissionDependencyState:
    normalized_permission = _normalize_permission(permission_code)
    if not normalized_permission:
        return {
            "granted": False,
            "requiredPermissions": [],
            "missingPermissions": [],
        }

    if "*" in granted_permissions:
        return {
            "granted": True,
            "requiredPermissions": [normalized_permission],
            "missingPermissions": [],
        }

    granted = set(granted_permissions)
    required_permissions = get_permission_dependency_closure(normalized_permission)
    missing_permissions = [
        permission for permission in required_permissions if permission not in granted
    ]

    return {
        "granted": len(missing_permissions) == 0,
        "requiredPermissions": required_permissions,
        "missingPermissions": missing_permissions,
    }


def evaluate_permission_requirement(
    requirement: PermissionRequirement,
    granted_permissions: List[str],
) -> PermissionRequirementState:
    all_of = requirement.get("allOf", [])
    any_of = requirement.get("anyOf", [])

    all_states = [
        evaluate_permission_dependencies(permission, granted_permissions)
        for permission in all_of
    ]
    missing_all_of = _merge_unique(
        [
            missing
            for state in all_states
            for missing in state["missingPermissions"]
        ]
    )

    any_states = [
        evaluate_permission_dependencies(permission, granted_permissions)
        for permission in any_of
    ]
    has_any = len(any_states) == 0 or any(state["granted"] for state in any_states)
    missing_any_of = (
        []
        if has_any
        else _merge_unique(
            [
                required
                for state in any_states
                for required in state["requiredPermissions"]
            ]
        )
    )

    return {
        "granted": len(missing_all_of) == 0 and has_any,
        "missingAllOf": missing_all_of,
        "missingAnyOf": missing_any_of,
    }


def project_effective_permissions(granted_permissions: List[str]) -> List[str]:
    if "*" in granted_permissions:
        return ["*"]

    effective = []
    for permission in granted_permissions:
        state = evaluate_permission_dependencies(permission, granted_permissions)
        if state["granted"]:
            effective.append(permission)

    return sorted(set(effective))


def resolve_capabilities(granted_permissions: List[str]) -> Dict[str, PermissionRequirementState]:
    if "*" in granted_permissions:
        return {
            key: {
                "granted": True,
                "missingAllOf": [],
                "missingAnyOf": [],
            }
            for key in CAPABILITY_REQUIREMENTS
        }

    return {
        key: evaluate_permission_requirement(requirement, granted_permissions)
        for key, requirement in CAPABILITY_REQUIREMENTS.items()
    }


def build_permission_context(granted_permissions: List[str]):
    effective_permissions = project_effective_permissions(granted_permissions)
    capabilities = resolve_capabilities(granted_permissions)

    return {
        "effectivePermissions": effective_permissions,
        "capabilities": capabilities,
        "permissionDependenciesVersion": "v1",
        "strictCapabilityPrefixes": STRICT_CAPABILITY_PREFIXES,
    }
