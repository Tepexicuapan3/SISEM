import { Navigate, type RouteObject } from "react-router-dom";
import { ProtectedRoute } from "@routes/guards/ProtectedRoute";
import RecepcionAgendaPage    from "@features/recepcion/modules/agenda/pages/RecepcionAgendaPage";
import RecepcionCheckinPage   from "@features/recepcion/modules/checkin/pages/RecepcionCheckinPage";
import QrCheckinPage          from "@features/recepcion/modules/checkin/pages/QrCheckinPage";
import RecepcionFichasPage    from "@features/recepcion/modules/fichas/pages/RecepcionFichasPage";
import RecepcionIncapacidadPage from "@features/recepcion/modules/incapacidad/pages/RecepcionIncapacidadPage";
import TurnosConfigPage       from "@features/recepcion/modules/turnos/pages/TurnosConfigPage";
import {
  INCAPACIDAD_READ_PERMISSIONS,
  RECEPCION_QUEUE_READ_PERMISSIONS,
} from "@features/recepcion/shared/domain/recepcion.permissions";

const agendaElement = (
  <ProtectedRoute
    requiredAnyPermissions={[...RECEPCION_QUEUE_READ_PERMISSIONS]}
    dependencyAware
  >
    <RecepcionAgendaPage />
  </ProtectedRoute>
);

export const recepcionRoutes: RouteObject[] = [
  {
    index: true,
    element: <Navigate to="agenda" replace />,
  },
  {
    path: "agenda",
    element: agendaElement,
  },
  {
    path: "agendar-cita",
    element: <RecepcionCheckinPage />,
  },
  {
    path: "checkin",
    element: <RecepcionCheckinPage />,
  },
  {
    path: "checkin/qr",
    element: (
      <ProtectedRoute
        requiredAnyPermissions={[...RECEPCION_QUEUE_READ_PERMISSIONS]}
        dependencyAware
      >
        <QrCheckinPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "fichas",
    element: (
      <ProtectedRoute
        requiredAnyPermissions={[...RECEPCION_QUEUE_READ_PERMISSIONS]}
        dependencyAware
      >
        <RecepcionFichasPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "turnos",
    element: <TurnosConfigPage />,
  },
  {
    path: "incapacidad",
    element: (
      <ProtectedRoute
        requiredAnyPermissions={[...INCAPACIDAD_READ_PERMISSIONS]}
        dependencyAware
      >
        <RecepcionIncapacidadPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "*",
    element: <Navigate to="/recepcion/agenda" replace />,
  },
];
