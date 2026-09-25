/**
 * ARCHIVO AUTO-GENERADO — NO EDITAR A MANO.
 *
 * Generado por `pnpm run gen:menu-destinations`
 * (frontend/scripts/gen-menu-destinations.ts) a partir de los
 * `RouteObject[]` reales de los `*.routes.config.tsx` bajo
 * `src/app/router/modules/`, leyendo los props vivos de `<ProtectedRoute>`
 * (`requiredPermission`, `fallbackRequirement.allOf/anyOf`,
 * `requiredAllPermissions`, `requiredAnyPermissions`).
 *
 * Los labels humanos (nombres amigables para el selector de destino) NO se
 * derivan aca — viven a mano en `menu-destinations.labels.ts`.
 *
 * El test anti-drift (`src/test/unit/navigation/menu-destinations.test.ts`)
 * falla el CI si: (a) este archivo queda desincronizado de correr la
 * derivacion en vivo de nuevo, o (b) algun path derivado no tiene su label
 * correspondiente en el archivo a mano.
 *
 * Para regenerar: `pnpm run gen:menu-destinations`.
 */

export interface MenuDestination {
  path: string;
  permissions: string[];
  capability?: string;
}

export const MENU_DESTINATIONS: MenuDestination[] = [
  {"path":"/admin/autorizacion/estudios","permissions":["admin:autorizacion:estudios:read"]},
  {"path":"/admin/catalogos","permissions":[]},
  {"path":"/admin/catalogos/areas","permissions":["admin:catalogos:areas:read"],"capability":"admin.catalogs.areas.read"},
  {"path":"/admin/catalogos/areas-clinicas","permissions":["admin:catalogos:areas_clinicas:read"]},
  {"path":"/admin/catalogos/autorizadores","permissions":["admin:catalogos:autorizadores:read"]},
  {"path":"/admin/catalogos/bajas","permissions":["admin:catalogos:bajas:read"]},
  {"path":"/admin/catalogos/calidad-laboral","permissions":["admin:catalogos:calidad_laboral:read"]},
  {"path":"/admin/catalogos/centro-area-clinica","permissions":["admin:catalogos:centro_area_clinica:read"]},
  {"path":"/admin/catalogos/centros-atencion","permissions":["admin:catalogos:centros_atencion:read"],"capability":"admin.catalogs.centers.read"},
  {"path":"/admin/catalogos/cie9-mc","permissions":["admin:catalogos:cie9_mc:read"],"capability":"admin.catalogs.cie9mc.read"},
  {"path":"/admin/catalogos/cies","permissions":["admin:catalogos:cies:upload"]},
  {"path":"/admin/catalogos/clasificaciones-cirugia","permissions":["admin:catalogos:clasificaciones_cirugia:read"],"capability":"admin.catalogs.clasificacionescirugia.read"},
  {"path":"/admin/catalogos/destinos-ambulancia","permissions":["admin:catalogos:destinos_ambulancia:read"],"capability":"admin.catalogs.destinosambulancia.read"},
  {"path":"/admin/catalogos/discapacidades","permissions":["admin:catalogos:discapacidades:read"]},
  {"path":"/admin/catalogos/edo-civil","permissions":["admin:catalogos:edo_civil:read"]},
  {"path":"/admin/catalogos/enfermedades","permissions":["admin:catalogos:enfermedades:read"]},
  {"path":"/admin/catalogos/escolaridad","permissions":["admin:catalogos:escolaridad:read"],"capability":"admin.catalogs.escolaridad.read"},
  {"path":"/admin/catalogos/escuelas","permissions":["admin:catalogos:escuelas:read"]},
  {"path":"/admin/catalogos/especialidades","permissions":["admin:catalogos:especialidades:read"]},
  {"path":"/admin/catalogos/estudios-medicos","permissions":["admin:catalogos:estudios_med:read"]},
  {"path":"/admin/catalogos/grupos-medicamentos","permissions":["admin:catalogos:grupos_medicamentos:read"]},
  {"path":"/admin/catalogos/licencias","permissions":["admin:catalogos:licencias:read"]},
  {"path":"/admin/catalogos/motivos-cancelacion-cirugia","permissions":["admin:catalogos:motivos_cancelacion_cirugia:read"],"capability":"admin.catalogs.motivoscancelacioncirugia.read"},
  {"path":"/admin/catalogos/motivos-traslado","permissions":["admin:catalogos:motivos_traslado:read"],"capability":"admin.catalogs.motivostraslado.read"},
  {"path":"/admin/catalogos/ocupaciones","permissions":["admin:catalogos:ocupaciones:read"]},
  {"path":"/admin/catalogos/origen-consulta","permissions":["admin:catalogos:origen_cons:read"]},
  {"path":"/admin/catalogos/parentescos","permissions":["admin:catalogos:parentescos:read"]},
  {"path":"/admin/catalogos/pases","permissions":["admin:catalogos:pases:read"]},
  {"path":"/admin/catalogos/religiones","permissions":["admin:catalogos:religion:read"]},
  {"path":"/admin/catalogos/sucursales","permissions":["admin:catalogos:sucursales:read"]},
  {"path":"/admin/catalogos/tipo-personal","permissions":["admin:catalogos:tipo_personal:read"]},
  {"path":"/admin/catalogos/tipos-areas","permissions":["admin:catalogos:tipos_areas:read"]},
  {"path":"/admin/catalogos/tipos-autorizacion","permissions":["admin:catalogos:tp_autorizacion:read"]},
  {"path":"/admin/catalogos/tipos-cirugia","permissions":["admin:catalogos:tipos_cirugia:read"],"capability":"admin.catalogs.tiposcirugia.read"},
  {"path":"/admin/catalogos/tipos-citas","permissions":["admin:catalogos:tipo_citas:read"]},
  {"path":"/admin/catalogos/tipos-consulta","permissions":["admin:catalogos:tipo_consulta:read"]},
  {"path":"/admin/catalogos/tipos-residencia","permissions":["admin:catalogos:tipo_residencia:read"]},
  {"path":"/admin/catalogos/tipos-sanguineo","permissions":["admin:catalogos:tipos_sanguineo:read"]},
  {"path":"/admin/catalogos/tipos-servicio-ambulancia","permissions":["admin:catalogos:tipos_servicio_ambulancia:read"],"capability":"admin.catalogs.tiposservicioambulancia.read"},
  {"path":"/admin/catalogos/tipos-traslado","permissions":["admin:catalogos:tipos_traslado:read"],"capability":"admin.catalogs.tipostraslado.read"},
  {"path":"/admin/catalogos/turnos","permissions":["admin:catalogos:turnos:read"],"capability":"admin.catalogs.turnos.read"},
  {"path":"/admin/catalogos/vacunas","permissions":["admin:catalogos:vacunas:read"],"capability":"admin.catalogs.vacunas.read"},
  {"path":"/admin/conciliacion","permissions":["admin:conciliacion:read"]},
  {"path":"/admin/conexiones","permissions":["admin:usuarios:sesiones:read"]},
  {"path":"/admin/estadisticas","permissions":["admin:estadisticas:read"]},
  {"path":"/admin/expedientes","permissions":["admin:gestion:expedientes:read"]},
  {"path":"/admin/licencias","permissions":["admin:licencias:read"]},
  {"path":"/admin/medicos","permissions":["admin:gestion:medicos:read"],"capability":"admin.medicos.read"},
  {"path":"/admin/menus","permissions":["admin:gestion:modulos:read"],"capability":"admin.menus.read"},
  {"path":"/admin/reportes/ambulancias","permissions":["clinico:ambulancias:read"],"capability":"clinico.reportes.ambulancias.read"},
  {"path":"/admin/reportes/cirugias","permissions":["clinico:cirugias:read"],"capability":"clinico.reportes.cirugias.read"},
  {"path":"/admin/reportes/consultas-diario","permissions":["clinico:reportes:read"],"capability":"clinico.reportes.read"},
  {"path":"/admin/reportes/incapacidades","permissions":["clinico:reportes:read"],"capability":"clinico.reportes.read"},
  {"path":"/admin/reportes/pases","permissions":["clinico:pases:read"],"capability":"clinico.pases.read"},
  {"path":"/admin/roles","permissions":["admin:gestion:roles:read"],"capability":"admin.roles.read"},
  {"path":"/admin/usuarios","permissions":["admin:gestion:usuarios:read"],"capability":"admin.users.read"},
  {"path":"/almacen/almacenes","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/categorias","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/consumos","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/conteos","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/dashboard","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/entradas","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/existencias","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/insumos","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/kardex","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/proveedores","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/salidas","permissions":["almacen:inventario:read"]},
  {"path":"/almacen/unidades-medida","permissions":["almacen:inventario:read"]},
  {"path":"/clinico/ambulancias","permissions":["clinico:ambulancias:read"]},
  {"path":"/clinico/autorizacion-recetas","permissions":["clinico:recetas:authorize"]},
  {"path":"/clinico/cirugias","permissions":["clinico:cirugias:read"]},
  {"path":"/clinico/consultas","permissions":["clinico:consultas:read"]},
  {"path":"/clinico/consultas/agenda","permissions":["clinico:consultas:read"]},
  {"path":"/clinico/consultas/doctor","permissions":["clinico:consultas:read"]},
  {"path":"/clinico/consultas/historial","permissions":["clinico:consultas:read"]},
  {"path":"/clinico/consultas/nueva","permissions":["clinico:consultas:create"]},
  {"path":"/clinico/expedientes","permissions":["clinico:expedientes:read"]},
  {"path":"/clinico/expedientes/nuevo","permissions":["clinico:expedientes:create"]},
  {"path":"/clinico/somatometria","permissions":["clinico:somatometria:read"]},
  {"path":"/dashboard","permissions":[]},
  {"path":"/farmacia/inventario","permissions":["farmacia:inventario:update"]},
  {"path":"/farmacia/recetas","permissions":["farmacia:recetas:dispensar"]},
  {"path":"/farmacia/vacunas","permissions":["farmacia:vacunas:read"],"capability":"farmacia.vacunas.read"},
  {"path":"/recepcion/agenda","permissions":["recepcion:fichas:medicina_general:create","recepcion:fichas:especialidad:create","recepcion:fichas:urgencias:create","clinico:consultas:read","clinico:somatometria:read"]},
  {"path":"/recepcion/agendar-cita","permissions":[]},
  {"path":"/recepcion/checkin","permissions":[]},
  {"path":"/recepcion/checkin/qr","permissions":["recepcion:fichas:medicina_general:create","recepcion:fichas:especialidad:create","recepcion:fichas:urgencias:create","clinico:consultas:read","clinico:somatometria:read"]},
  {"path":"/recepcion/fichas","permissions":["recepcion:fichas:medicina_general:create","recepcion:fichas:especialidad:create","recepcion:fichas:urgencias:create","clinico:consultas:read","clinico:somatometria:read"]},
  {"path":"/recepcion/incapacidad","permissions":["recepcion:incapacidad:read","clinico:consultas:read"]},
  {"path":"/recepcion/turnos","permissions":[]},
  {"path":"/servicios/contratos-oxigeno","permissions":["servicios:contratos_oxigeno:read"]},
  {"path":"/urgencias/triage","permissions":["urgencias:triage:read"]},
];
