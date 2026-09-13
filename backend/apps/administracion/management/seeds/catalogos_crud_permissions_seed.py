"""
Alta de los permisos create/update/delete de los catalogos administrativos
que se migraron de GenericCatalogPage (solo lectura) a CRUD completo en el
change "catalogos-crud" (ver engram topic_key catalogos/*-crud).

`permission_dependencies.py` ya mapea estas capabilities en codigo, pero ese
mapeo no alcanza: el codigo tiene que existir tambien como fila real en
`cat_permisos` (lo que este seed hace) y estar asignado a algun rol (lo que
hace el management command `seed_catalogos_crud_permissions`, via
`rel_rol_permisos`) para que `hasCapability` en el frontend deje de bloquear
los botones de crear/editar/eliminar.
"""

CATALOGOS_CRUD_PERMISSIONS_SEED: list[tuple[str, str]] = [
    ("admin:catalogos:enfermedades:read", "Ver catalogo de enfermedades"),
    ("admin:catalogos:enfermedades:create", "Crear en catalogo de enfermedades"),
    ("admin:catalogos:enfermedades:update", "Editar catalogo de enfermedades"),
    ("admin:catalogos:enfermedades:delete", "Eliminar en catalogo de enfermedades"),

    ("admin:catalogos:tp_autorizacion:read", "Ver catalogo de tipos de autorizacion"),
    ("admin:catalogos:tp_autorizacion:create", "Crear en catalogo de tipos de autorizacion"),
    ("admin:catalogos:tp_autorizacion:update", "Editar catalogo de tipos de autorizacion"),
    ("admin:catalogos:tp_autorizacion:delete", "Eliminar en catalogo de tipos de autorizacion"),

    ("admin:catalogos:bajas:read", "Ver catalogo de bajas"),
    ("admin:catalogos:bajas:create", "Crear en catalogo de bajas"),
    ("admin:catalogos:bajas:update", "Editar catalogo de bajas"),
    ("admin:catalogos:bajas:delete", "Eliminar en catalogo de bajas"),

    ("admin:catalogos:pases:read", "Ver catalogo de pases"),
    ("admin:catalogos:pases:create", "Crear en catalogo de pases"),
    ("admin:catalogos:pases:update", "Editar catalogo de pases"),
    ("admin:catalogos:pases:delete", "Eliminar en catalogo de pases"),

    ("admin:catalogos:tipos_sanguineo:read", "Ver catalogo de tipos sanguineos"),
    ("admin:catalogos:tipos_sanguineo:create", "Crear en catalogo de tipos sanguineos"),
    ("admin:catalogos:tipos_sanguineo:update", "Editar catalogo de tipos sanguineos"),
    ("admin:catalogos:tipos_sanguineo:delete", "Eliminar en catalogo de tipos sanguineos"),

    ("admin:catalogos:grupos_medicamentos:read", "Ver catalogo de grupos de medicamentos"),
    ("admin:catalogos:grupos_medicamentos:create", "Crear en catalogo de grupos de medicamentos"),
    ("admin:catalogos:grupos_medicamentos:update", "Editar catalogo de grupos de medicamentos"),
    ("admin:catalogos:grupos_medicamentos:delete", "Eliminar en catalogo de grupos de medicamentos"),

    ("admin:catalogos:ocupaciones:read", "Ver catalogo de ocupaciones"),
    ("admin:catalogos:ocupaciones:create", "Crear en catalogo de ocupaciones"),
    ("admin:catalogos:ocupaciones:update", "Editar catalogo de ocupaciones"),
    ("admin:catalogos:ocupaciones:delete", "Eliminar en catalogo de ocupaciones"),

    ("admin:catalogos:licencias:read", "Ver catalogo de licencias"),
    ("admin:catalogos:licencias:create", "Crear en catalogo de licencias"),
    ("admin:catalogos:licencias:update", "Editar catalogo de licencias"),
    ("admin:catalogos:licencias:delete", "Eliminar en catalogo de licencias"),

    ("admin:catalogos:calidad_laboral:read", "Ver catalogo de calidad laboral"),
    ("admin:catalogos:calidad_laboral:create", "Crear en catalogo de calidad laboral"),
    ("admin:catalogos:calidad_laboral:update", "Editar catalogo de calidad laboral"),
    ("admin:catalogos:calidad_laboral:delete", "Eliminar en catalogo de calidad laboral"),

    ("admin:catalogos:origen_cons:read", "Ver catalogo de origen de consulta"),
    ("admin:catalogos:origen_cons:create", "Crear en catalogo de origen de consulta"),
    ("admin:catalogos:origen_cons:update", "Editar catalogo de origen de consulta"),
    ("admin:catalogos:origen_cons:delete", "Eliminar en catalogo de origen de consulta"),

    ("admin:catalogos:parentescos:read", "Ver catalogo de parentescos"),
    ("admin:catalogos:parentescos:create", "Crear en catalogo de parentescos"),
    ("admin:catalogos:parentescos:update", "Editar catalogo de parentescos"),
    ("admin:catalogos:parentescos:delete", "Eliminar en catalogo de parentescos"),

    ("admin:catalogos:autorizadores:read", "Ver catalogo de autorizadores"),
    ("admin:catalogos:autorizadores:create", "Crear en catalogo de autorizadores"),
    ("admin:catalogos:autorizadores:update", "Editar catalogo de autorizadores"),
    ("admin:catalogos:autorizadores:delete", "Eliminar en catalogo de autorizadores"),

    ("admin:catalogos:estudios_med:read", "Ver catalogo de estudios medicos"),
    ("admin:catalogos:estudios_med:create", "Crear en catalogo de estudios medicos"),
    ("admin:catalogos:estudios_med:update", "Editar catalogo de estudios medicos"),
    ("admin:catalogos:estudios_med:delete", "Eliminar en catalogo de estudios medicos"),

    ("admin:catalogos:sucursales:read", "Ver catalogo de sucursales"),
    ("admin:catalogos:sucursales:create", "Crear en catalogo de sucursales"),
    ("admin:catalogos:sucursales:update", "Editar catalogo de sucursales"),
    ("admin:catalogos:sucursales:delete", "Eliminar en catalogo de sucursales"),

    ("admin:catalogos:discapacidades:read", "Ver catalogo de discapacidades"),
    ("admin:catalogos:discapacidades:create", "Crear en catalogo de discapacidades"),
    ("admin:catalogos:discapacidades:update", "Editar catalogo de discapacidades"),
    ("admin:catalogos:discapacidades:delete", "Eliminar en catalogo de discapacidades"),

    ("admin:catalogos:religion:read", "Ver catalogo de religiones"),
    ("admin:catalogos:religion:create", "Crear en catalogo de religiones"),
    ("admin:catalogos:religion:update", "Editar catalogo de religiones"),
    ("admin:catalogos:religion:delete", "Eliminar en catalogo de religiones"),

    ("admin:catalogos:tipo_residencia:read", "Ver catalogo de tipos de residencia"),
    ("admin:catalogos:tipo_residencia:create", "Crear en catalogo de tipos de residencia"),
    ("admin:catalogos:tipo_residencia:update", "Editar catalogo de tipos de residencia"),
    ("admin:catalogos:tipo_residencia:delete", "Eliminar en catalogo de tipos de residencia"),

    ("admin:catalogos:cie9_mc:read", "Ver catalogo CIE-9-MC (procedimientos, NOM-024)"),
    ("admin:catalogos:cie9_mc:create", "Crear en catalogo CIE-9-MC"),
    ("admin:catalogos:cie9_mc:update", "Editar catalogo CIE-9-MC"),
    ("admin:catalogos:cie9_mc:delete", "Eliminar en catalogo CIE-9-MC"),
]
