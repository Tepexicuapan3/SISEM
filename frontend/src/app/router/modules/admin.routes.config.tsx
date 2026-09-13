import { Navigate, type RouteObject } from "react-router-dom";
import { ProtectedRoute } from "@routes/guards/ProtectedRoute";
import UsersPage from "@/domains/auth-access/pages/admin/users/UsersPage";
import RolesPage from "@/domains/auth-access/pages/admin/roles/RolesPage";
import SessionsPage from "@/domains/auth-access/pages/admin/sessions/SessionsPage";
import CatalogosHubPage from "@features/admin/modules/catalogos/pages/CatalogosHubPage";
import { ReporteConsultasDiarioPage } from "@features/admin/modules/reportes/pages/ReporteConsultasDiarioPage";
import { ReportePasesPage } from "@features/admin/modules/reportes/pages/ReportePasesPage";
import AreasPage from "@features/admin/modules/catalogos/areas/pages/AreasPage";
import CentrosAtencionPage from "@features/admin/modules/catalogos/centros-atencion/pages/CentrosAtencionPage";
import CiesPage from "@features/admin/modules/catalogos/cies/pages/CiesPage";
import AutorizadoresPage from "@features/admin/modules/catalogos/autorizadores/pages/AutorizadoresPage";
import BajasPage from "@features/admin/modules/catalogos/bajas/pages/BajasPage";
import CalidadLaboralPage from "@features/admin/modules/catalogos/calidad-laboral/pages/CalidadLaboralPage";
import EdoCivilPage from "@features/admin/modules/catalogos/edo-civil/pages/EdoCivilPage";
import DiscapacidadesPage from "@features/admin/modules/catalogos/discapacidades/pages/DiscapacidadesPage";
import EnfermedadesPage from "@features/admin/modules/catalogos/enfermedades/pages/EnfermedadesPage";
import EscolaridadPage from "@features/admin/modules/catalogos/escolaridad/pages/EscolaridadPage";
import TipoPersonalPage from "@features/admin/modules/catalogos/tipo-personal/pages/TipoPersonalPage";
import EscuelasPage from "@features/admin/modules/catalogos/escuelas/pages/EscuelasPage";
import EspecialidadesPage from "@features/admin/modules/catalogos/especialidades/pages/EspecialidadesPage";
import EstudiosMedicosPage from "@features/admin/modules/catalogos/estudios-medicos/pages/EstudiosMedicosPage";
import GruposMedicamentosPage from "@features/admin/modules/catalogos/grupos-medicamentos/pages/GruposMedicamentosPage";
import OcupacionesPage from "@features/admin/modules/catalogos/ocupaciones/pages/OcupacionesPage";
import OrigenConsultaPage from "@features/admin/modules/catalogos/origen-consulta/pages/OrigenConsultaPage";
import ParentescosPage from "@features/admin/modules/catalogos/parentescos/pages/ParentescosPage";
import PasesPage from "@features/admin/modules/catalogos/pases/pages/PasesPage";
import TiposAreasPage from "@features/admin/modules/catalogos/tipos-areas/pages/TiposAreasPage";
import TiposAutorizacionPage from "@features/admin/modules/catalogos/tipos-autorizacion/pages/TiposAutorizacionPage";
import TiposCitasPage from "@features/admin/modules/catalogos/tipos-citas/pages/TiposCitasPage";
import TiposConsultaPage from "@features/admin/modules/catalogos/tipos-consulta/pages/TiposConsultaPage";
import ReligionesPage from "@features/admin/modules/catalogos/religiones/pages/ReligionesPage";
import TiposResidenciaPage from "@features/admin/modules/catalogos/tipos-residencia/pages/TiposResidenciaPage";
import LicenciasPage from "@features/admin/modules/catalogos/licencias/pages/LicenciasPage";
import TiposSanguineoPage from "@features/admin/modules/catalogos/tipos-sanguineo/pages/TiposSanguineoPage";
import TurnosPage from "@features/admin/modules/catalogos/turnos/pages/TurnosPage";
import VacunasPage from "@features/admin/modules/catalogos/vacunas/pages/VacunasPage";
import AreasClinicasPage from "@features/admin/modules/catalogos/areas-clinicas/pages/AreasClinicasPage";
import CentrosAreasClinicasPage from "@features/admin/modules/catalogos/centro-area-clinica/pages/CentrosAreasClinicasPage";
import SucursalesPage from "@features/admin/modules/catalogos/sucursales/pages/SucursalesPage";
import PlaceholderPage from "@shared/components/PlaceholderPage";
import MedicosPage from "@features/admin/modules/medicos/pages/MedicosPage";
import MenusPage from "@features/admin/modules/menus/pages/MenusPage";
import { lazy, Suspense } from "react";

// Administracion
const ExpedientesAdminPage = lazy(
  () =>
    import("@/features/admin/modules/expedientes/pages/ExpedientesAdminPage"),
);
/**
 * Rutas del grupo Administracion.
 *
 * Razon industria:
 * - Agrupa la configuracion de usuarios/roles en un solo modulo.
 * - Facilita ownership y lazy loading por dominio.
 */
export const adminRoutes: RouteObject[] = [
  {
    index: true,
    element: <Navigate to="usuarios" replace />, // entrypoint por defecto
  },
  {
    path: "usuarios",
    element: (
      <ProtectedRoute
        requiredCapability="admin.users.read"
        fallbackRequirement={{ allOf: ["admin:gestion:usuarios:read"] }}
        dependencyAware
      >
        <UsersPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "roles",
    element: (
      <ProtectedRoute
        requiredCapability="admin.roles.read"
        fallbackRequirement={{ allOf: ["admin:gestion:roles:read"] }}
        dependencyAware
      >
        <RolesPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "conexiones",
    element: (
      <ProtectedRoute requiredPermission="admin:usuarios:sesiones:read">
        <SessionsPage />
      </ProtectedRoute>
    ),
  },
  {
    // Pantalla de gestion de menus (CRUD de `Modulo` -- crear accesos
    // directos/carpetas, ocultar, mover, reordenar). Requiere el permiso
    // MAS ESPECIFICO `admin:gestion:modulos:read` (no alcanza con
    // `admin:gestion:roles:read`, que solo habilita la lectura via la tab
    // "Modulos" del detalle de rol) -- ver `ModuleCatalogView` en el
    // backend.
    //
    // El nodo `administracion.panel.menus` esta dado de alta en
    // `navigation_seed.py` bajo `administracion.catalogos` -- clave sin
    // renombrar por compatibilidad, el item vive dentro de "Catalogos" en
    // el sidebar.
    path: "menus",
    element: (
      <ProtectedRoute
        requiredCapability="admin.menus.read"
        fallbackRequirement={{ allOf: ["admin:gestion:modulos:read"] }}
        dependencyAware
      >
        <MenusPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "medicos",
    element: (
      <ProtectedRoute
        requiredCapability="admin.medicos.read"
        fallbackRequirement={{ allOf: ["admin:gestion:medicos:read"] }}
        dependencyAware
      >
        <MedicosPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "catalogos",
    children: [
      {
        index: true,
        element: <CatalogosHubPage />,
      },
      {
        path: "areas",
        element: (
          <ProtectedRoute
            requiredCapability="admin.catalogs.areas.read"
            fallbackRequirement={{ allOf: ["admin:catalogos:areas:read"] }}
            dependencyAware
          >
            <AreasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "centros-atencion",
        element: (
          <ProtectedRoute
            requiredCapability="admin.catalogs.centers.read"
            fallbackRequirement={{
              allOf: ["admin:catalogos:centros_atencion:read"],
            }}
            dependencyAware
          >
            <CentrosAtencionPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "autorizadores",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:autorizadores:read">
            <AutorizadoresPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "bajas",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:bajas:read">
            <BajasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "calidad-laboral",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:calidad_laboral:read">
            <CalidadLaboralPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "edo-civil",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:edo_civil:read">
            <EdoCivilPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "sucursales",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:sucursales:read">
            <SucursalesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "enfermedades",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:enfermedades:read">
            <EnfermedadesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "escolaridad",
        element: (
          <ProtectedRoute
            requiredCapability="admin.catalogs.escolaridad.read"
            fallbackRequirement={{ allOf: ["admin:catalogos:escolaridad:read"] }}
            dependencyAware
          >
            <EscolaridadPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipo-personal",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tipo_personal:read">
            <TipoPersonalPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "escuelas",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:escuelas:read">
            <EscuelasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "discapacidades",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:discapacidades:read">
            <DiscapacidadesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "especialidades",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:especialidades:read">
            <EspecialidadesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipos-consulta",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tipo_consulta:read">
            <TiposConsultaPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "religiones",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:religion:read">
            <ReligionesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipos-residencia",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tipo_residencia:read">
            <TiposResidenciaPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "estudios-medicos",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:estudios_med:read">
            <EstudiosMedicosPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "grupos-medicamentos",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:grupos_medicamentos:read">
            <GruposMedicamentosPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "ocupaciones",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:ocupaciones:read">
            <OcupacionesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "origen-consulta",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:origen_cons:read">
            <OrigenConsultaPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "parentescos",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:parentescos:read">
            <ParentescosPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "pases",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:pases:read">
            <PasesPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipos-areas",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tipos_areas:read">
            <TiposAreasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipos-autorizacion",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tp_autorizacion:read">
            <TiposAutorizacionPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipos-citas",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tipo_citas:read">
            <TiposCitasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "licencias",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:licencias:read">
            <LicenciasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "tipos-sanguineo",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:tipos_sanguineo:read">
            <TiposSanguineoPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "turnos",
        element: (
          <ProtectedRoute
            requiredCapability="admin.catalogs.turnos.read"
            fallbackRequirement={{ allOf: ["admin:catalogos:turnos:read"] }}
            dependencyAware
          >
            <TurnosPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "vacunas",
        element: (
          <ProtectedRoute
            requiredCapability="admin.catalogs.vacunas.read"
            fallbackRequirement={{ allOf: ["admin:catalogos:vacunas:read"] }}
            dependencyAware
          >
            <VacunasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "areas-clinicas",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:areas_clinicas:read">
            <AreasClinicasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "centro-area-clinica",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:centro_area_clinica:read">
            <CentrosAreasClinicasPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "cies",
        element: (
          <ProtectedRoute requiredPermission="admin:catalogos:cies:upload">
            <CiesPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: "expedientes",
    element: (
      <ProtectedRoute requiredPermission="admin:gestion:expedientes:read">
        <Suspense fallback={<div>Cargando...</div>}>
          <ExpedientesAdminPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "reportes",
    children: [
      {
        index: true,
        element: <Navigate to="consultas-diario" replace />,
      },
      {
        path: "consultas-diario",
        element: (
          <ProtectedRoute
            requiredCapability="clinico.reportes.read"
            fallbackRequirement={{ allOf: ["clinico:reportes:read"] }}
            dependencyAware
          >
            <ReporteConsultasDiarioPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "pases",
        element: (
          <ProtectedRoute
            requiredCapability="clinico.pases.read"
            fallbackRequirement={{ allOf: ["clinico:pases:read"] }}
            dependencyAware
          >
            <ReportePasesPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: "estadisticas",
    element: (
      <ProtectedRoute requiredPermission="admin:estadisticas:read">
        <PlaceholderPage
          title="Estadisticas"
          description="Metricas globales y analisis historico"
          moduleName="Administracion"
        />
      </ProtectedRoute>
    ),
  },
  {
    path: "autorizacion/recetas",
    element: (
      <ProtectedRoute requiredPermission="admin:autorizacion:recetas:read">
        <PlaceholderPage
          title="Autorizacion de Recetas"
          description="Flujo de aprobacion y seguimiento de recetas"
          moduleName="Administracion"
        />
      </ProtectedRoute>
    ),
  },
  {
    path: "autorizacion/estudios",
    element: (
      <ProtectedRoute requiredPermission="admin:autorizacion:estudios:read">
        <PlaceholderPage
          title="Autorizacion de Estudios"
          description="Validacion y autorizacion de estudios clinicos"
          moduleName="Administracion"
        />
      </ProtectedRoute>
    ),
  },
  {
    path: "licencias",
    element: (
      <ProtectedRoute requiredPermission="admin:licencias:read">
        <PlaceholderPage
          title="Licencias"
          description="Gestion de licencias y control de accesos"
          moduleName="Administracion"
        />
      </ProtectedRoute>
    ),
  },
  {
    path: "conciliacion",
    element: (
      <ProtectedRoute requiredPermission="admin:conciliacion:read">
        <PlaceholderPage
          title="Conciliacion"
          description="Conciliacion operativa y financiera"
          moduleName="Administracion"
        />
      </ProtectedRoute>
    ),
  },
];
