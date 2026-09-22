import { Navigate, type RouteObject } from "react-router-dom";
import { lazy, Suspense } from "react";
import { ProtectedRoute } from "@routes/guards/ProtectedRoute";

const InventarioVacunasPage = lazy(
  () => import("@features/farmacia/modules/vacunas/pages/InventarioVacunasPage"),
);
const DispensacionFarmaciaPage = lazy(
  () => import("@features/farmacia/modules/recetas/pages/DispensacionFarmaciaPage"),
);
const InventarioFarmaciaPage = lazy(
  () => import("@features/farmacia/modules/inventario/pages/InventarioFarmaciaPage"),
);

export const farmaciaRoutes: RouteObject[] = [
  {
    index: true,
    element: <Navigate to="vacunas" replace />,
  },
  {
    path: "vacunas",
    element: (
      <ProtectedRoute
        requiredCapability="farmacia.vacunas.read"
        fallbackRequirement={{ allOf: ["farmacia:vacunas:read"] }}
        dependencyAware
      >
        <Suspense fallback={<div>Cargando...</div>}>
          <InventarioVacunasPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "recetas",
    element: (
      <ProtectedRoute requiredPermission="farmacia:recetas:dispensar">
        <Suspense fallback={<div>Cargando...</div>}>
          <DispensacionFarmaciaPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "inventario",
    element: (
      <ProtectedRoute requiredPermission="farmacia:inventario:update">
        <Suspense fallback={<div>Cargando...</div>}>
          <InventarioFarmaciaPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
];
