import { Navigate, type RouteObject } from "react-router-dom";
import { ProtectedRoute } from "@routes/guards/ProtectedRoute";
import ConsultasPage from "@features/consultas/pages/ConsultasPage";
import AgendaPage from "@features/consultas/pages/AgendaPage";
import NuevaConsultaPage from "@features/consultas/pages/NuevaConsultaPage";
import HistorialPage from "@features/consultas/pages/HistorialPage";
import ExpedientesListPage from "@features/expedientes/pages/ExpedientesListPage";
import ExpedienteDetailPage from "@features/expedientes/pages/ExpedienteDetailPage";
import DoctorConsultationPage from "@features/consulta-medica/modules/atencion/pages/DoctorConsultationPage";
import SomatometriaCapturePage from "@features/somatometria/modules/captura/pages/SomatometriaCapturePage";
import CirugiasPage from "@features/cirugias/pages/CirugiasPage";
import AmbulanciasPage from "@features/ambulancias/pages/AmbulanciasPage";
import PlaceholderPage from "@shared/components/PlaceholderPage";

// Clinico

const consultasRoutes: RouteObject[] = [
  {
    index: true,
    element: (
      <ProtectedRoute requiredPermission="clinico:consultas:read">
        <ConsultasPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "agenda",
    element: (
      <ProtectedRoute requiredPermission="clinico:consultas:read">
        <AgendaPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "nueva",
    element: (
      <ProtectedRoute requiredPermission="clinico:consultas:create">
        <NuevaConsultaPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "historial",
    element: (
      <ProtectedRoute requiredPermission="clinico:consultas:read">
        <HistorialPage />
      </ProtectedRoute>
    ),
  },
];

const expedientesRoutes: RouteObject[] = [
  {
    index: true,
    element: (
      <ProtectedRoute requiredPermission="clinico:expedientes:read">
        <ExpedientesListPage />
      </ProtectedRoute>
    ),
  },
  {
    path: ":folio",
    element: (
      <ProtectedRoute requiredPermission="clinico:expedientes:read">
        <ExpedienteDetailPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "nuevo",
    element: (
      <ProtectedRoute requiredPermission="clinico:expedientes:create">
        <PlaceholderPage
          title="Nuevo Expediente"
          description="Formulario para crear un nuevo expediente medico"
          moduleName="Expedientes"
        />
      </ProtectedRoute>
    ),
  },
];

/**
 * Rutas del grupo Clinico (consultas + expedientes).
 *
 * Razon industria:
 * - Mantiene la jerarquia de dominio clinico en un solo modulo.
 * - Permite escalar submodulos sin fragmentar el router principal.
 */
export const clinicoRoutes: RouteObject[] = [
  {
    path: "consultas",
    children: consultasRoutes,
  },
  {
    path: "expedientes",
    children: expedientesRoutes,
  },
  {
    path: "somatometria",
    element: (
      <ProtectedRoute requiredPermission="clinico:somatometria:read">
        <SomatometriaCapturePage />
      </ProtectedRoute>
    ),
  },
  {
    path: "cirugias",
    element: (
      <ProtectedRoute requiredPermission="clinico:cirugias:read">
        <CirugiasPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "ambulancias",
    element: (
      <ProtectedRoute requiredPermission="clinico:ambulancias:read">
        <AmbulanciasPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "consultas/doctor",
    element: (
      <ProtectedRoute requiredPermission="clinico:consultas:read">
        <DoctorConsultationPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "consultas/doctor/:visitId",
    element: (
      <ProtectedRoute requiredPermission="clinico:consultas:read">
        <DoctorConsultationPage />
      </ProtectedRoute>
    ),
  },
  {
    index: true,
    element: <Navigate to="consultas" replace />,
  },
];
