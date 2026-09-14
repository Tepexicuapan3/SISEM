import { lazy } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@routes/guards/ProtectedRoute";
import { GuestRoute } from "@routes/guards/GuestRoute";
import { PortalGuestRoute } from "@features/portal-citas/guards/PortalGuestRoute";
import { PortalProtectedRoute } from "@features/portal-citas/guards/PortalProtectedRoute";
import { MainLayout } from "@shared/layouts/MainLayout";
import { RootLayout } from "@shared/layouts/RootLayout";
import { SuspenseWrapper } from "@shared/components/SuspenseWrapper";

// Core auth
const LoginPage = lazy(() =>
  import("@/domains/auth-access/pages/LoginPage").then((m) => ({
    default: m.LoginPage,
  })),
);
const OnboardingPage = lazy(() =>
  import("@/domains/auth-access/pages/OnboardingPage").then((m) => ({
    default: m.OnboardingPage,
  })),
);

// Portal de Citas (autoservicio del paciente) -- SIN relacion con el login
// de staff de arriba: sesion propia (Bearer token, ver portalSessionStore),
// rutas publicas montadas al mismo nivel que /login.
const PortalLoginPage = lazy(
  () => import("@features/portal-citas/pages/PortalLoginPage"),
);
const PortalMisCitasPage = lazy(
  () => import("@features/portal-citas/pages/PortalMisCitasPage"),
);
const PortalReservarCitaPage = lazy(
  () => import("@features/portal-citas/pages/PortalReservarCitaPage"),
);

/**
 * Modulos lazy por grupo.
 *
 * Razon industria:
 * - Centraliza la carga de modulos para evitar duplicacion en UI.
 * - Los modulos se cargan en lazy para reducir el bundle inicial.
 */
const CoreRoutes = lazy(() => import("@routes/modules/core.routes"));
const AdminRoutes = lazy(() => import("@routes/modules/admin.routes"));
const ClinicoRoutes = lazy(() => import("@routes/modules/clinico.routes"));
const RecepcionRoutes = lazy(() => import("@routes/modules/recepcion.routes"));
const FarmaciaRoutes = lazy(() => import("@routes/modules/farmacia.routes"));
const AlmacenRoutes = lazy(() => import("@routes/modules/almacen.routes"));
const ServiciosRoutes = lazy(() => import("@routes/modules/servicios.routes"));
const ComunicadosRoutes = lazy(() => import("@routes/modules/comunicados.routes"));
const UrgenciasRoutes = lazy(() =>
  import("@routes/modules/placeholders.routes").then((m) => ({
    default: m.UrgenciasRoutes,
  })),
);

/**
 * Router principal.
 *
 * Razon industria:
 * - Centraliza el arbol de rutas y mantiene el entrypoint liviano.
 */
export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: "/",
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: "/login",
        element: (
          <GuestRoute>
            <SuspenseWrapper fullScreen>
              <LoginPage />
            </SuspenseWrapper>
          </GuestRoute>
        ),
      },
      {
        path: "/onboarding",
        element: (
          <ProtectedRoute>
            <SuspenseWrapper fullScreen>
              <OnboardingPage />
            </SuspenseWrapper>
          </ProtectedRoute>
        ),
      },
      {
        path: "/portal/login",
        element: (
          <PortalGuestRoute>
            <SuspenseWrapper fullScreen>
              <PortalLoginPage />
            </SuspenseWrapper>
          </PortalGuestRoute>
        ),
      },
      {
        path: "/portal/mis-citas",
        element: (
          <PortalProtectedRoute>
            <SuspenseWrapper fullScreen>
              <PortalMisCitasPage />
            </SuspenseWrapper>
          </PortalProtectedRoute>
        ),
      },
      {
        path: "/portal/reservar",
        element: (
          <PortalProtectedRoute>
            <SuspenseWrapper fullScreen>
              <PortalReservarCitaPage />
            </SuspenseWrapper>
          </PortalProtectedRoute>
        ),
      },
      {
        element: (
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        ),
        children: [
          // Grupos de rutas por dominio
          {
            path: "/dashboard",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <CoreRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/admin/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <AdminRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/clinico/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <ClinicoRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/recepcion/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <RecepcionRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/farmacia/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <FarmaciaRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/servicios/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <ServiciosRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/comunicados/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <ComunicadosRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/almacen/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <AlmacenRoutes />
              </SuspenseWrapper>
            ),
          },
          {
            path: "/urgencias/*",
            element: (
              <SuspenseWrapper className="min-h-[calc(100dvh-4rem)]">
                <UrgenciasRoutes />
              </SuspenseWrapper>
            ),
          },
        ],
      },
      {
        path: "*",
        element: <Navigate to="/dashboard" replace />,
      },
    ],
  },
]);
