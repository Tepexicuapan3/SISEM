import {
  Activity,
  Ambulance,
  Archive,
  BookOpen,
  CalendarClock,
  Clock,
  ClipboardList,
  Database,
  FileText,
  FolderOpen,
  Key,
  LayoutDashboard,
  Package,
  Pill,
  ScrollText,
  Shield,
  Stethoscope,
  ShieldUser,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

/**
 * Configuracion de navegacion basada en permisos.
 *
 * Razon industria:
 * - Mantiene el sidebar alineado a rutas reales.
 * - Usa permisos como filtro UX (backend siempre valida).
 *
 * Nota: `NavItem`/`NavSection` (los tipos) siguen vigentes -- son el shape
 * canonico que usan `useNavigation`, `mapNavigationMenu`, `NavMain`,
 * `SidebarBreadcrumbs` y `ModuleSearch`. Lo deprecado es la CONSTANTE
 * `NAV_CONFIG` (ver mas abajo), no los tipos.
 */

export interface NavItem {
  title: string;
  url?: string;
  icon?: LucideIcon;
  permissions?: string[];
  items?: NavItem[];
  badge?: string;
}

export interface NavSection {
  title: string;
  icon?: LucideIcon;
  items: NavItem[];
  permissions?: string[];
}

// Badge reutilizable para modulos aun no implementados.
export const PLACEHOLDER_BADGE = "Dev";

/**
 * @deprecated Ya NO es la fuente de datos del sidebar/breadcrumbs/buscador.
 * La fuente real es el catalogo `cat_modulos` servido por
 * `GET /navigation-menu` (ver `useNavigationMenu`/`useNavigation`).
 * Este archivo queda como FALLBACK PERMANENTE -- se usa cuando el endpoint
 * falla, hace timeout, el feature flag backend esta OFF (`source !== "db"`)
 * o el arbol viene vacio, para que el sidebar nunca quede sin menu.
 * NO se borra. Editar navegacion real = editar `cat_modulos` (Django admin),
 * no este archivo. Si se edita este archivo, revisar que el seed
 * (`backend/apps/administracion/management/seeds/navigation_seed.py`) siga
 * siendo transcripcion fiel para no romper la paridad flag-OFF.
 */
export const NAV_CONFIG: NavSection[] = [
  {
    title: "Administracion",
    items: [
      {
        title: "Panel",
        icon: ShieldUser,
        items: [
          {
            title: "Usuarios",
            url: "/admin/usuarios",
            permissions: ["admin:gestion:usuarios:read"],
          },
          {
            title: "Médicos",
            url: "/admin/medicos",
            permissions: ["admin:gestion:medicos:read"],
          },
          {
            title: "Expedientes",
            url: "/admin/expedientes",
            permissions: ["admin:gestion:expedientes:read"],
            badge: PLACEHOLDER_BADGE,
          },
          {
            title: "Roles",
            url: "/admin/roles",
            permissions: ["admin:gestion:roles:read"],
          },
          {
            title: "Conexiones",
            url: "/admin/conexiones",
            permissions: ["admin:usuarios:sesiones:read"],
          },
        ],
      },
      {
        title: "Catalogos",
        icon: BookOpen,
        items: [
          {
            title: "Areas",
            url: "/admin/catalogos/areas",
            permissions: ["admin:catalogos:areas:read"],
          },
          {
            title: "Centros de atencion",
            url: "/admin/catalogos/centros-atencion",
            permissions: ["admin:catalogos:centros_atencion:read"],
          },
          {
            title: "Autorizadores",
            url: "/admin/catalogos/autorizadores",
            permissions: ["admin:catalogos:autorizadores:read"],
          },
          {
            title: "Bajas",
            url: "/admin/catalogos/bajas",
            permissions: ["admin:catalogos:bajas:read"],
          },
          {
            title: "Calidad laboral",
            url: "/admin/catalogos/calidad-laboral",
            permissions: ["admin:catalogos:calidad_laboral:read"],
          },
          {
            title: "Estado civil",
            url: "/admin/catalogos/edo-civil",
            permissions: ["admin:catalogos:edo_civil:read"],
          },
          {
            title: "Sucursales",
            url: "/admin/catalogos/sucursales",
            permissions: ["admin:catalogos:sucursales:read"],
          },
          {
            title: "Enfermedades",
            url: "/admin/catalogos/enfermedades",
            permissions: ["admin:catalogos:enfermedades:read"],
          },
          {
            title: "Escolaridad",
            url: "/admin/catalogos/escolaridad",
            permissions: ["admin:catalogos:escolaridad:read"],
          },
          {
            title: "Tipos de personal",
            url: "/admin/catalogos/tipo-personal",
            permissions: ["admin:catalogos:tipo_personal:read"],
          },
          {
            title: "Escuelas",
            url: "/admin/catalogos/escuelas",
            permissions: ["admin:catalogos:escuelas:read"],
          },
          {
            title: "Discapacidades",
            url: "/admin/catalogos/discapacidades",
            permissions: ["admin:catalogos:discapacidades:read"],
          },
          {
            title: "Especialidades",
            url: "/admin/catalogos/especialidades",
            permissions: ["admin:catalogos:especialidades:read"],
          },
          {
            title: "Estudios medicos",
            url: "/admin/catalogos/estudios-medicos",
            permissions: ["admin:catalogos:estudios_med:read"],
          },
          {
            title: "Grupos de medicamentos",
            url: "/admin/catalogos/grupos-medicamentos",
            permissions: ["admin:catalogos:grupos_medicamentos:read"],
          },
          {
            title: "Ocupaciones",
            url: "/admin/catalogos/ocupaciones",
            permissions: ["admin:catalogos:ocupaciones:read"],
          },
          {
            title: "Origen de consulta",
            url: "/admin/catalogos/origen-consulta",
            permissions: ["admin:catalogos:origen_cons:read"],
          },
          {
            title: "Parentescos",
            url: "/admin/catalogos/parentescos",
            permissions: ["admin:catalogos:parentescos:read"],
          },
          {
            title: "Pases",
            url: "/admin/catalogos/pases",
            permissions: ["admin:catalogos:pases:read"],
          },
          {
            title: "Tipos de areas",
            url: "/admin/catalogos/tipos-areas",
            permissions: ["admin:catalogos:tipos_areas:read"],
          },
          {
            title: "Tipos de autorizacion",
            url: "/admin/catalogos/tipos-autorizacion",
            permissions: ["admin:catalogos:tp_autorizacion:read"],
          },
          {
            title: "Tipos de citas",
            url: "/admin/catalogos/tipos-citas",
            permissions: ["admin:catalogos:tipo_citas:read"],
          },
          {
            title: "Tipos de consulta",
            url: "/admin/catalogos/tipos-consulta",
            permissions: ["admin:catalogos:tipo_consulta:read"],
          },
          {
            title: "Religiones",
            url: "/admin/catalogos/religiones",
            permissions: ["admin:catalogos:religion:read"],
          },
          {
            title: "Tipos de residencia",
            url: "/admin/catalogos/tipos-residencia",
            permissions: ["admin:catalogos:tipo_residencia:read"],
          },
          {
            title: "Licencias",
            url: "/admin/catalogos/licencias",
            permissions: ["admin:catalogos:licencias:read"],
          },
          {
            title: "Tipos sanguineos",
            url: "/admin/catalogos/tipos-sanguineo",
            permissions: ["admin:catalogos:tipos_sanguineo:read"],
          },
          {
            title: "Turnos",
            url: "/admin/catalogos/turnos",
            permissions: ["admin:catalogos:turnos:read"],
          },
          {
            title: "Vacunas",
            url: "/admin/catalogos/vacunas",
            permissions: ["admin:catalogos:vacunas:read"],
          },
          {
            title: "Áreas clínicas",
            url: "/admin/catalogos/areas-clinicas",
            permissions: ["admin:catalogos:areas_clinicas:read"],
          },
          {
            title: "Áreas clínicas por centro",
            url: "/admin/catalogos/centro-area-clinica",
            permissions: ["admin:catalogos:centro_area_clinica:read"],
          },
          {
            title: "Catálogo CIES",
            url: "/admin/catalogos/cies",
            permissions: ["admin:catalogos:cies:upload"],
          },
        ],
      },
      {
        title: "Reportes y Analitica Operativa",
        icon: FileText,
        items: [
          {
            title: "Informe Diario de Consulta Médica",
            url: "/admin/reportes/consultas-diario",
            permissions: ["clinico:reportes:read"],
          },
          {
            title: "Informe de Pases",
            url: "/admin/reportes/pases",
            permissions: ["clinico:pases:read"],
          },
        ],
      },
      {
        title: "Estadisticas",
        url: "/admin/estadisticas",
        icon: Activity,
        permissions: ["admin:estadisticas:read"],
        badge: PLACEHOLDER_BADGE,
      },
      {
        title: "Autorizacion",
        icon: Shield,
        items: [
          {
            title: "Recetas",
            url: "/admin/autorizacion/recetas",
            permissions: ["admin:autorizacion:recetas:read"],
            badge: PLACEHOLDER_BADGE,
          },
          {
            title: "Estudios",
            url: "/admin/autorizacion/estudios",
            permissions: ["admin:autorizacion:estudios:read"],
            badge: PLACEHOLDER_BADGE,
          },
        ],
      },
      {
        title: "Licencias",
        url: "/admin/licencias",
        icon: Key,
        permissions: ["admin:licencias:read"],
        badge: PLACEHOLDER_BADGE,
      },
      {
        title: "Conciliacion",
        url: "/admin/conciliacion",
        icon: Database,
        permissions: ["admin:conciliacion:read"],
        badge: PLACEHOLDER_BADGE,
      },
    ],
  },
  {
    title: "Clinico",
    items: [
      {
        title: "Consultas",
        icon: Stethoscope,
        items: [
          {
            title: "Panel",
            url: "/clinico/consultas",
            permissions: ["clinico:consultas:read"],
          },
          {
            title: "Agenda",
            url: "/clinico/consultas/agenda",
            permissions: ["clinico:consultas:agenda:read"],
          },
          {
            title: "Nueva Consulta",
            url: "/clinico/consultas/nueva",
            permissions: ["clinico:consultas:create"],
          },
          {
            title: "Historial",
            url: "/clinico/consultas/historial",
            permissions: ["clinico:consultas:historial:read"],
          },
          {
            title: "Bandeja",
            url: "/clinico/consultas/doctor",
            permissions: ["clinico:consultas:read"],
          },
        ],
      },
      {
        title: "Expedientes",
        icon: FolderOpen,
        permissions: ["clinico:expedientes:read"],
        items: [
          {
            title: "Listado",
            url: "/clinico/expedientes",
            permissions: ["clinico:expedientes:read"],
          },
          {
            title: "Nuevo Expediente",
            url: "/clinico/expedientes/nuevo",
            permissions: ["clinico:expedientes:create"],
            badge: PLACEHOLDER_BADGE,
          },
        ],
      },
      {
        title: "Somatometria",
        url: "/clinico/somatometria",
        icon: Activity,
        permissions: ["clinico:somatometria:read"],
      },
    ],
  },
  {
    title: "Recepcion",
    items: [
      {
        title: "Citas y check-in",
        url: "/recepcion/agenda",
        icon: CalendarClock,
        permissions: [
          "recepcion:fichas:medicina_general:create",
          "recepcion:fichas:especialidad:create",
          "recepcion:fichas:urgencias:create",
          "clinico:consultas:read",
          "clinico:somatometria:read",
        ],
      },
      {
        title: "Archivo de fichas",
        url: "/recepcion/fichas",
        icon: Archive,
        permissions: [
          "recepcion:fichas:medicina_general:create",
          "recepcion:fichas:especialidad:create",
          "recepcion:fichas:urgencias:create",
          "clinico:consultas:read",
          "clinico:somatometria:read",
        ],
      },
      {
        title: "Turnos de fichas",
        url: "/recepcion/turnos",
        icon: Clock,
        permissions: [
          "recepcion:fichas:medicina_general:create",
          "recepcion:fichas:especialidad:create",
          "recepcion:fichas:urgencias:create",
        ],
      },
    ],
  },
  {
    title: "Farmacia",
    items: [
      {
        title: "Inventario de vacunas",
        url: "/farmacia/vacunas",
        icon: Pill,
        permissions: ["farmacia:vacunas:read"],
      },
      {
        title: "Recetas",
        url: "/farmacia/recetas",
        icon: Pill,
        permissions: ["farmacia:recetas:dispensar"],
        badge: PLACEHOLDER_BADGE,
      },
      {
        title: "Inventario",
        url: "/farmacia/inventario",
        icon: Database,
        permissions: ["farmacia:inventario:update"],
        badge: PLACEHOLDER_BADGE,
      },
    ],
  },
  {
    title: "Almacén",
    permissions: ["almacen:inventario:read"],
    items: [
      {
        title: "Dashboard",
        url: "/almacen/dashboard",
        icon: Warehouse,
      },
      {
        title: "Catálogos",
        icon: BookOpen,
        items: [
          { title: "Insumos",          url: "/almacen/insumos" },
          { title: "Categorías",       url: "/almacen/categorias" },
          { title: "Proveedores",      url: "/almacen/proveedores" },
          { title: "Unidades de medida", url: "/almacen/unidades-medida" },
          { title: "Almacenes",        url: "/almacen/almacenes" },
        ],
      },
      {
        title: "Movimientos",
        icon: Package,
        items: [
          { title: "Entradas",              url: "/almacen/entradas" },
          { title: "Salidas / Mermas",      url: "/almacen/salidas" },
          { title: "Consumos por consulta", url: "/almacen/consumos" },
        ],
      },
      {
        title: "Inventario",
        icon: ClipboardList,
        items: [
          { title: "Existencias",     url: "/almacen/existencias" },
          { title: "Kardex",          url: "/almacen/kardex" },
          { title: "Conteos físicos", url: "/almacen/conteos" },
        ],
      },
    ],
  },
  {
    title: "Servicios",
    items: [
      {
        title: "Contratos de oxígeno",
        url: "/servicios/contratos-oxigeno",
        icon: ScrollText,
        permissions: ["servicios:contratos_oxigeno:read"],
      },
    ],
  },
  {
    title: "Urgencias",
    items: [
      {
        title: "Triage",
        url: "/urgencias/triage",
        icon: Ambulance,
        permissions: ["urgencias:triage:read"],
        badge: PLACEHOLDER_BADGE,
      },
    ],
  },
  {
    title: "Core",
    items: [
      {
        title: "Dashboard",
        url: "/dashboard",
        icon: LayoutDashboard,
      },
    ],
  },
];

// Acciones globales disponibles para cualquier usuario autenticado.
export const NAV_SECONDARY: NavItem[] = [
  {
    title: "Soporte",
    url: "/soporte",
    icon: Shield,
  },
  {
    title: "Enviar Feedback",
    url: "/feedback",
    icon: BookOpen,
  },
];
